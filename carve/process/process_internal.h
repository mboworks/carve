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

#ifndef CARVE_PROCESS_PROCESS_INTERNAL_H_
#define CARVE_PROCESS_PROCESS_INTERNAL_H_

#include <poll.h>
#include <sys/types.h>

#include <cstddef>
#include <string>

#include "absl/status/statusor.h"
#include "absl/types/span.h"
#include "carve/process/process.h"

namespace carve::process::process_internal {

// Narrow POSIX seam used to exercise parent-side failures deterministically.
class SystemCalls {
 public:
  virtual ~SystemCalls() = default;

  virtual int Pipe(int* descriptors) = 0;
  virtual pid_t Fork() = 0;
  virtual int Poll(pollfd* descriptors, nfds_t count, int timeout) = 0;
  virtual ssize_t Read(int descriptor, void* buffer, std::size_t count) = 0;
  virtual pid_t WaitPid(pid_t pid, int* status, int options) = 0;
  virtual int Close(int descriptor) = 0;
};

[[nodiscard]] absl::StatusOr<CommandResult> RunWithSystemCalls(
    absl::Span<const std::string> argv,
    SystemCalls& system_calls);

}  // namespace carve::process::process_internal

#endif  // CARVE_PROCESS_PROCESS_INTERNAL_H_
