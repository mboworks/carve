// SPDX-FileCopyrightText: Copyright (c) M. Boerger, the MBO Works authors
// SPDX-License-Identifier: Apache-2.0
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include "carve/process/process.h"

#include <poll.h>
#include <sys/wait.h>
#include <unistd.h>

#include <array>
#include <cerrno>
#include <cstddef>
#include <string>
#include <string_view>
#include <vector>

#include "absl/status/status.h"
#include "absl/status/statusor.h"
#include "absl/types/span.h"
#include "carve/process/process_internal.h"

namespace carve::process {
namespace {

// A process terminated by signal N is reported as 128 + N (shell convention).
constexpr int kSignalExitBase = 128;
// Exit status used when the child's exec fails (e.g. program not found); 127 is
// the shell convention for "command not found".
constexpr int kExecFailedExitCode = 127;
// Read chunk size when draining the child's pipes.
constexpr std::size_t kReadChunkBytes = 4'096;

// Builds a status from the current `errno`. Uses `absl::ErrnoToStatus`, which
// formats the message with a thread-safe `strerror` internally and maps the
// errno to the matching `absl::StatusCode` (`std::strerror` is not thread-safe).
absl::Status ErrnoError(std::string_view what) {
  return absl::ErrnoToStatus(errno, what);
}

class PosixSystemCalls final : public process_internal::SystemCalls {
 public:
  int Pipe(int* descriptors) override {
    // macOS has no pipe2(); the child closes every pipe fd before exec.
    // NOLINTNEXTLINE(android-cloexec-pipe)
    return ::pipe(descriptors);
  }

  pid_t Fork() override { return ::fork(); }

  int Poll(pollfd* descriptors, nfds_t count, int timeout) override { return ::poll(descriptors, count, timeout); }

  ssize_t Read(int descriptor, void* buffer, std::size_t count) override { return ::read(descriptor, buffer, count); }

  pid_t WaitPid(pid_t pid, int* status, int options) override { return ::waitpid(pid, status, options); }

  int Close(int descriptor) override { return ::close(descriptor); }
};

// Drains `out_fd` and `err_fd` into the result strings until both reach EOF,
// polling so neither pipe blocks the other.
absl::Status DrainPipes(int out_fd, int err_fd, CommandResult& result, process_internal::SystemCalls& system_calls) {
  std::array<pollfd, 2> fds = {
      pollfd{.fd = out_fd, .events = POLLIN, .revents = 0}, pollfd{.fd = err_fd, .events = POLLIN, .revents = 0}};
  std::array<std::string*, 2> sinks = {&result.stdout_data, &result.stderr_data};
  int open_fds = 2;
  absl::Status status;
  while (open_fds > 0) {
    if (system_calls.Poll(fds.data(), fds.size(), -1) < 0) {
      if (errno == EINTR) {
        continue;
      }
      status = ErrnoError("poll");
      break;
    }
    for (std::size_t i = 0; i < fds.size(); ++i) {
      // POSIX poll flags are signed int macros; the bitmask test is the idiomatic form.
      // NOLINTNEXTLINE(hicpp-signed-bitwise)
      if (fds.at(i).fd < 0 || (fds.at(i).revents & (POLLIN | POLLHUP | POLLERR)) == 0) {
        continue;
      }
      std::array<char, kReadChunkBytes> buffer{};
      const ssize_t got = system_calls.Read(fds.at(i).fd, buffer.data(), buffer.size());
      if (got > 0) {
        sinks.at(i)->append(buffer.data(), static_cast<std::size_t>(got));
      } else if (got == 0 || errno != EINTR) {
        if (got < 0 && status.ok()) {
          status = ErrnoError("read");
        }
        system_calls.Close(fds.at(i).fd);
        fds.at(i).fd = -1;
        --open_fds;
      }
    }
  }
  // Close anything still open (e.g. if poll() failed and broke the loop).
  for (const pollfd& entry : fds) {
    if (entry.fd >= 0) {
      system_calls.Close(entry.fd);
    }
  }
  return status;
}

}  // namespace

absl::StatusOr<CommandResult> process_internal::RunWithSystemCalls(
    absl::Span<const std::string> argv,
    process_internal::SystemCalls& system_calls) {
  if (argv.empty()) {
    return absl::InvalidArgumentError("Run requires a non-empty argv");
  }

  // Prepare execvp's mutable argv before fork: allocating in the child of a
  // potentially multithreaded process is unsafe until exec replaces the image.
  std::vector<char*> c_argv;
  c_argv.reserve(argv.size() + 1);
  for (const std::string& arg : argv) {
    // execvp wants char* const[]; argv outlives the call and is not modified.
    // NOLINTNEXTLINE(cppcoreguidelines-pro-type-const-cast)
    c_argv.push_back(const_cast<char*>(arg.c_str()));
  }
  c_argv.push_back(nullptr);

  std::array<int, 2> out_pipe{};
  std::array<int, 2> err_pipe{};
  if (system_calls.Pipe(out_pipe.data()) != 0) {
    return ErrnoError("pipe(stdout)");
  }
  if (system_calls.Pipe(err_pipe.data()) != 0) {
    absl::Status status = ErrnoError("pipe(stderr)");
    system_calls.Close(out_pipe.at(0));
    system_calls.Close(out_pipe.at(1));
    return status;
  }
  const std::array descriptors = {out_pipe.at(0), out_pipe.at(1), err_pipe.at(0), err_pipe.at(1)};

  const pid_t pid = system_calls.Fork();
  if (pid < 0) {
    absl::Status status = ErrnoError("fork");
    for (const int descriptor : descriptors) {
      system_calls.Close(descriptor);
    }
    return status;
  }

  if (pid == 0) {
    // Child: wire stdout/stderr to the pipes and exec.
    // A successful exec replaces the instrumented image, while _exit after a
    // failed exec intentionally cannot flush LLVM's coverage profile. Real
    // subprocess tests exercise both outcomes.
    // LCOV_EXCL_START
    ::dup2(out_pipe.at(1), STDOUT_FILENO);
    ::dup2(err_pipe.at(1), STDERR_FILENO);
    for (const int descriptor : descriptors) {
      ::close(descriptor);
    }
    ::execvp(c_argv.front(), c_argv.data());
    ::_exit(kExecFailedExitCode);  // Reached only if exec failed (e.g. program not found).
    // LCOV_EXCL_STOP
  }

  // Parent: close write ends, drain, and reap.
  system_calls.Close(out_pipe.at(1));
  system_calls.Close(err_pipe.at(1));
  CommandResult result;
  absl::Status drain_status = DrainPipes(out_pipe.at(0), err_pipe.at(0), result, system_calls);

  int status = 0;
  while (system_calls.WaitPid(pid, &status, 0) < 0) {
    if (errno != EINTR) {
      return ErrnoError("waitpid");
    }
  }
  if (!drain_status.ok()) {
    return drain_status;
  }
  if (WIFEXITED(status)) {
    result.exit_code = WEXITSTATUS(status);
  } else if (WIFSIGNALED(status)) {
    result.exit_code = kSignalExitBase + WTERMSIG(status);
  }
  return result;
}

absl::StatusOr<CommandResult> Run(absl::Span<const std::string> argv) {
  PosixSystemCalls system_calls;
  return process_internal::RunWithSystemCalls(argv, system_calls);
}

}  // namespace carve::process
