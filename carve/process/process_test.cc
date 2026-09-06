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
#include <sys/resource.h>
#include <unistd.h>

#include <algorithm>
#include <array>
#include <cerrno>
#include <csignal>
#include <cstddef>
#include <string>
#include <vector>

#include "absl/status/status.h"
#include "carve/process/process_internal.h"
#include "gmock/gmock.h"
#include "gtest/gtest.h"
#include "mbo/testing/status.h"

namespace carve::process {
namespace {

using ::mbo::testing::IsOkAndHolds;
using ::mbo::testing::StatusIs;
using ::testing::AllOf;
using ::testing::Eq;
using ::testing::Field;
using ::testing::Ge;
using ::testing::HasSubstr;
using ::testing::SizeIs;
using ::testing::UnorderedElementsAre;

class FakeSystemCalls final : public process_internal::SystemCalls {
 public:
  enum class Failure { kNone, kFork, kPoll, kRead, kBothReads, kWaitPid };

  void SetFailure(Failure failure) { failure_ = failure; }

  void InterruptPoll() { interrupt_poll_ = true; }

  void InterruptRead() { interrupt_read_ = true; }

  void InterruptWaitPid() { interrupt_wait_pid_ = true; }

  int PollCalls() const { return poll_calls_; }

  int ReadCalls() const { return read_calls_; }

  int WaitPidCalls() const { return wait_pid_calls_; }

  const std::vector<int>& ClosedDescriptors() const { return closed_descriptors_; }

  int Pipe(int* descriptors) override {
    descriptors[0] = next_descriptor_++;
    descriptors[1] = next_descriptor_++;
    return 0;
  }

  pid_t Fork() override {
    if (failure_ == Failure::kFork) {
      errno = EAGAIN;
      return -1;
    }
    return kChildPid;
  }

  int Poll(pollfd* descriptors, nfds_t count, int /*timeout*/) override {
    ++poll_calls_;
    if (interrupt_poll_ && poll_calls_ == 1) {
      errno = EINTR;
      return -1;
    }
    if (failure_ == Failure::kPoll) {
      errno = EIO;
      return -1;
    }
    int ready = 0;
    for (nfds_t index = 0; index < count; ++index) {
      if (descriptors[index].fd >= 0) {
        descriptors[index].revents = POLLIN;
        ++ready;
      }
    }
    return ready;
  }

  ssize_t Read(int /*descriptor*/, void* /*buffer*/, std::size_t /*count*/) override {
    ++read_calls_;
    if (interrupt_read_ && read_calls_ == 1) {
      errno = EINTR;
      return -1;
    }
    if (failure_ == Failure::kRead && read_calls_ == 1) {
      errno = EIO;
      return -1;
    }
    if (failure_ == Failure::kBothReads && read_calls_ <= 2) {
      errno = read_calls_ == 1 ? EIO : EBADF;
      return -1;
    }
    return 0;
  }

  pid_t WaitPid(pid_t pid, int* status, int /*options*/) override {
    ++wait_pid_calls_;
    if (interrupt_wait_pid_ && wait_pid_calls_ == 1) {
      errno = EINTR;
      return -1;
    }
    if (failure_ == Failure::kWaitPid) {
      errno = EIO;
      return -1;
    }
    *status = 0;
    return pid;
  }

  int Close(int descriptor) override {
    closed_descriptors_.push_back(descriptor);
    return 0;
  }

 private:
  static constexpr pid_t kChildPid = 123;
  int next_descriptor_ = 10;
  Failure failure_ = Failure::kNone;
  bool interrupt_poll_ = false;
  bool interrupt_read_ = false;
  bool interrupt_wait_pid_ = false;
  int poll_calls_ = 0;
  int read_calls_ = 0;
  int wait_pid_calls_ = 0;
  std::vector<int> closed_descriptors_;
};

class ProcessSystemCallsTest : public ::testing::Test {
 protected:
  static absl::StatusOr<CommandResult> Execute(FakeSystemCalls& system_calls) {
    return process_internal::RunWithSystemCalls(std::vector<std::string>{"unused"}, system_calls);
  }

  FakeSystemCalls& SystemCalls() { return system_calls_; }

 private:
  FakeSystemCalls system_calls_;
};

class ProcessFailureTest : public ::testing::Test {
 protected:
  void SetUp() override {
    ASSERT_THAT(getrlimit(RLIMIT_NOFILE, &original_limit_), Eq(0));
    struct rlimit test_limit = original_limit_;
    test_limit.rlim_cur = std::min<rlim_t>(test_limit.rlim_cur, 256);
    ASSERT_THAT(setrlimit(RLIMIT_NOFILE, &test_limit), Eq(0));
    limit_changed_ = true;

    std::array<int, 2> pipe_descriptors{};
    // macOS has no pipe2(); every descriptor remains inside this test process.
    // NOLINTNEXTLINE(android-cloexec-pipe)
    while (pipe(pipe_descriptors.data()) == 0) {
      descriptors_.push_back(pipe_descriptors.at(0));
      descriptors_.push_back(pipe_descriptors.at(1));
    }
    ASSERT_THAT(errno, Eq(EMFILE));
    ASSERT_THAT(descriptors_.size(), Ge(2));
  }

  void TearDown() override {
    for (const int descriptor : descriptors_) {
      EXPECT_THAT(close(descriptor), Eq(0));
    }
    if (limit_changed_) {
      EXPECT_THAT(setrlimit(RLIMIT_NOFILE, &original_limit_), Eq(0));
    }
  }

  static void ReleaseDescriptors(std::vector<int>& descriptors, std::size_t count) {
    ASSERT_THAT(descriptors.size(), Ge(count));
    while (count > 0) {
      EXPECT_THAT(close(descriptors.back()), Eq(0));
      descriptors.pop_back();
      --count;
    }
  }

  std::vector<int>& Descriptors() { return descriptors_; }

 private:
  struct rlimit original_limit_{};
  std::vector<int> descriptors_;
  bool limit_changed_ = false;
};

TEST(RunTest, CapturesStdoutAndZeroExit) {
  EXPECT_THAT(
      ::carve::process::Run(std::vector<std::string>{"/bin/echo", "hello"}),
      IsOkAndHolds(AllOf(Field(&CommandResult::exit_code, Eq(0)), Field(&CommandResult::stdout_data, Eq("hello\n")))));
}

TEST(RunTest, CapturesStderrAndNonZeroExitSeparately) {
  EXPECT_THAT(
      ::carve::process::Run(std::vector<std::string>{"/bin/sh", "-c", "printf oops >&2; exit 3"}),
      IsOkAndHolds(AllOf(
          Field(&CommandResult::exit_code, Eq(3)), Field(&CommandResult::stdout_data, Eq("")),
          Field(&CommandResult::stderr_data, Eq("oops")))));
}

TEST(RunTest, MissingProgramReportsExit127) {
  EXPECT_THAT(
      ::carve::process::Run(std::vector<std::string>{"/no/such/program/carve"}),
      IsOkAndHolds(Field(&CommandResult::exit_code, Eq(127))));
}

TEST(RunTest, SignalTerminationReportsShellConventionExitCode) {
  EXPECT_THAT(
      ::carve::process::Run(std::vector<std::string>{"/bin/sh", "-c", "kill -TERM $$"}),
      IsOkAndHolds(Field(&CommandResult::exit_code, Eq(128 + SIGTERM))));
}

TEST(RunTest, LargeOutputDoesNotDeadlock) {
  // 200000 'x' bytes exceeds a pipe buffer, so concurrent draining is required.
  EXPECT_THAT(
      ::carve::process::Run(std::vector<std::string>{"/bin/sh", "-c", "yes x | head -c 200000"}),
      IsOkAndHolds(
          AllOf(Field(&CommandResult::exit_code, Eq(0)), Field(&CommandResult::stdout_data, SizeIs(200'000)))));
}

TEST(RunTest, EmptyArgvIsInvalidArgument) {
  EXPECT_THAT(::carve::process::Run(std::vector<std::string>{}), StatusIs(absl::StatusCode::kInvalidArgument));
}

TEST_F(ProcessFailureTest, ReportsStdoutPipeFailure) {
  EXPECT_THAT(
      ::carve::process::Run(std::vector<std::string>{"/bin/true"}),
      StatusIs(absl::StatusCode::kResourceExhausted, HasSubstr("pipe(stdout)")));
}

TEST_F(ProcessFailureTest, ReportsStderrPipeFailure) {
  ReleaseDescriptors(Descriptors(), 2);
  EXPECT_THAT(
      ::carve::process::Run(std::vector<std::string>{"/bin/true"}),
      StatusIs(absl::StatusCode::kResourceExhausted, HasSubstr("pipe(stderr)")));
}

TEST_F(ProcessSystemCallsTest, ReportsForkFailureAndClosesEveryPipeDescriptor) {
  SystemCalls().SetFailure(FakeSystemCalls::Failure::kFork);

  EXPECT_THAT(Execute(SystemCalls()), StatusIs(absl::StatusCode::kUnavailable, HasSubstr("fork")));
  EXPECT_THAT(SystemCalls().ClosedDescriptors(), UnorderedElementsAre(10, 11, 12, 13));
}

TEST_F(ProcessSystemCallsTest, RetriesInterruptedPoll) {
  SystemCalls().InterruptPoll();

  EXPECT_THAT(Execute(SystemCalls()), IsOkAndHolds(Field(&CommandResult::exit_code, Eq(0))));
  EXPECT_THAT(SystemCalls().PollCalls(), Eq(2));
}

TEST_F(ProcessSystemCallsTest, ReportsPollFailureAfterReapingChild) {
  SystemCalls().SetFailure(FakeSystemCalls::Failure::kPoll);

  EXPECT_THAT(Execute(SystemCalls()), StatusIs(absl::StatusCode::kUnknown, HasSubstr("poll")));
  EXPECT_THAT(SystemCalls().WaitPidCalls(), Eq(1));
  EXPECT_THAT(SystemCalls().ClosedDescriptors(), UnorderedElementsAre(10, 11, 12, 13));
}

TEST_F(ProcessSystemCallsTest, RetriesInterruptedRead) {
  SystemCalls().InterruptRead();

  EXPECT_THAT(Execute(SystemCalls()), IsOkAndHolds(Field(&CommandResult::exit_code, Eq(0))));
  EXPECT_THAT(SystemCalls().ReadCalls(), Eq(3));
}

TEST_F(ProcessSystemCallsTest, ReportsReadFailureAfterReapingChild) {
  SystemCalls().SetFailure(FakeSystemCalls::Failure::kRead);

  EXPECT_THAT(Execute(SystemCalls()), StatusIs(absl::StatusCode::kUnknown, HasSubstr("read")));
  EXPECT_THAT(SystemCalls().WaitPidCalls(), Eq(1));
}

TEST_F(ProcessSystemCallsTest, PreservesFirstFailureWhenBothPipeReadsFail) {
  SystemCalls().SetFailure(FakeSystemCalls::Failure::kBothReads);

  EXPECT_THAT(Execute(SystemCalls()), StatusIs(absl::StatusCode::kUnknown, HasSubstr("read")));
  EXPECT_THAT(SystemCalls().ReadCalls(), Eq(2));
  EXPECT_THAT(SystemCalls().ClosedDescriptors(), UnorderedElementsAre(10, 11, 12, 13));
}

TEST_F(ProcessSystemCallsTest, RetriesInterruptedWaitPid) {
  SystemCalls().InterruptWaitPid();

  EXPECT_THAT(Execute(SystemCalls()), IsOkAndHolds(Field(&CommandResult::exit_code, Eq(0))));
  EXPECT_THAT(SystemCalls().WaitPidCalls(), Eq(2));
}

TEST_F(ProcessSystemCallsTest, ReportsWaitPidFailure) {
  SystemCalls().SetFailure(FakeSystemCalls::Failure::kWaitPid);

  EXPECT_THAT(Execute(SystemCalls()), StatusIs(absl::StatusCode::kUnknown, HasSubstr("waitpid")));
  EXPECT_THAT(SystemCalls().WaitPidCalls(), Eq(1));
}

}  // namespace
}  // namespace carve::process
