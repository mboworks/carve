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

#include <sys/resource.h>
#include <unistd.h>

#include <algorithm>
#include <array>
#include <cerrno>
#include <csignal>
#include <string>
#include <vector>

#include "absl/status/status.h"
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

}  // namespace
}  // namespace carve::process
