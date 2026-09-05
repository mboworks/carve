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

#include "carve/io/io.h"

#include <sys/resource.h>

#include <csignal>
#include <filesystem>
#include <vector>

#include "absl/status/status.h"
#include "absl/status/statusor.h"
#include "gmock/gmock.h"
#include "gtest/gtest.h"
#include "mbo/testing/status.h"

namespace carve::io {
namespace {

using ::mbo::testing::IsOk;
using ::mbo::testing::IsOkAndHolds;
using ::mbo::testing::StatusIs;
using ::testing::Eq;
using ::testing::HasSubstr;
using ::testing::IsEmpty;
using ::testing::Not;
using ::testing::SizeIs;

struct IoFailureTest : ::testing::Test {};

TEST(WriteAtomicallyTest, CreatesParentsAndWritesContent) {
  const std::filesystem::path path =
      std::filesystem::path(::testing::TempDir()) / "carve_io_write" / "nested" / "out.bin";
  std::filesystem::remove_all(std::filesystem::path(::testing::TempDir()) / "carve_io_write");

  ASSERT_THAT(WriteAtomically(path, "hello\n"), IsOk());
  EXPECT_THAT(ReadFile(path), IsOkAndHolds(Eq("hello\n")));
}

TEST(WriteAtomicallyTest, OverwritesInPlaceWithoutLeavingTempFiles) {
  const std::filesystem::path dir = std::filesystem::path(::testing::TempDir()) / "carve_io_overwrite";
  std::filesystem::remove_all(dir);
  const std::filesystem::path path = dir / "out.bin";

  ASSERT_THAT(WriteAtomically(path, "first"), IsOk());
  ASSERT_THAT(WriteAtomically(path, "second"), IsOk());
  EXPECT_THAT(ReadFile(path), IsOkAndHolds(Eq("second")));

  std::vector<std::filesystem::path> entries;
  for (const auto& entry : std::filesystem::directory_iterator(dir)) {
    entries.push_back(entry.path());
  }
  EXPECT_THAT(entries, SizeIs(1)) << "temp files were left behind";
}

TEST(WriteAtomicallyTest, ReportsParentCreationFailure) {
  const std::filesystem::path dir = std::filesystem::path(::testing::TempDir()) / "carve_io_parent_failure";
  std::filesystem::remove_all(dir);
  const std::filesystem::path blocker = dir / "not_a_directory";
  ASSERT_THAT(WriteAtomically(blocker, "blocker"), IsOk());

  EXPECT_THAT(WriteAtomically(blocker / "out.bin", "content"), StatusIs(absl::StatusCode::kUnknown));
}

TEST(WriteAtomicallyTest, RenameFailureRemovesTemporaryFile) {
  const std::filesystem::path dir = std::filesystem::path(::testing::TempDir()) / "carve_io_rename_failure";
  std::filesystem::remove_all(dir);
  const std::filesystem::path destination = dir / "out.bin";
  ASSERT_THAT(WriteAtomically(destination / "occupied", "blocker"), IsOk());

  EXPECT_THAT(WriteAtomically(destination, "content"), StatusIs(absl::StatusCode::kUnknown));
  std::vector<std::filesystem::path> entries;
  for (const auto& entry : std::filesystem::directory_iterator(dir)) {
    entries.push_back(entry.path());
  }
  EXPECT_THAT(entries, SizeIs(1)) << "temp files were left behind";
}

TEST_F(IoFailureTest, ReportsTemporaryFileOpenFailure) {
  const std::filesystem::path dir = std::filesystem::path(::testing::TempDir()) / "carve_io_open_failure";
  std::filesystem::remove_all(dir);
  std::filesystem::create_directories(dir);
  std::filesystem::permissions(
      dir, std::filesystem::perms::owner_read | std::filesystem::perms::owner_exec,
      std::filesystem::perm_options::replace);

  const absl::Status status = WriteAtomically(dir / "out.bin", "content");
  std::filesystem::permissions(dir, std::filesystem::perms::owner_all, std::filesystem::perm_options::replace);

  if (status.ok()) {
    GTEST_SKIP() << "the current user can write to a non-writable directory";
  }
  EXPECT_THAT(status, StatusIs(absl::StatusCode::kUnknown, HasSubstr("failed to open temp file")));
}

TEST_F(IoFailureTest, ReportsWriteFailureAndRemovesTemporaryFile) {
  const std::filesystem::path dir = std::filesystem::path(::testing::TempDir()) / "carve_io_write_failure";
  std::filesystem::remove_all(dir);
  std::filesystem::create_directories(dir);

  struct rlimit original_limit{};
  ASSERT_THAT(getrlimit(RLIMIT_FSIZE, &original_limit), Eq(0));
  const auto previous_handler = std::signal(SIGXFSZ, SIG_IGN);
  ASSERT_THAT(previous_handler, Not(Eq(SIG_ERR)));
  struct rlimit zero_limit = original_limit;
  zero_limit.rlim_cur = 0;
  if (setrlimit(RLIMIT_FSIZE, &zero_limit) != 0) {
    std::signal(SIGXFSZ, previous_handler);
    GTEST_SKIP() << "the file-size resource limit cannot be lowered";
  }

  const absl::Status status = WriteAtomically(dir / "out.bin", "content");

  const int restore_limit_result = setrlimit(RLIMIT_FSIZE, &original_limit);
  const auto restore_handler_result = std::signal(SIGXFSZ, previous_handler);
  ASSERT_THAT(restore_limit_result, Eq(0));
  ASSERT_THAT(restore_handler_result, Not(Eq(SIG_ERR)));
  EXPECT_THAT(status, StatusIs(absl::StatusCode::kUnknown, HasSubstr("failed to write temp file")));
  EXPECT_THAT(std::filesystem::directory_iterator(dir), IsEmpty());
}

TEST(ReadFileTest, MissingFileIsNotFound) {
  EXPECT_THAT(ReadFile("/no/such/carve/file"), StatusIs(absl::StatusCode::kNotFound));
}

TEST_F(IoFailureTest, ReportsExistingFileOpenFailure) {
  const std::filesystem::path path = std::filesystem::path(::testing::TempDir()) / "carve_io_read_failure.bin";
  ASSERT_THAT(WriteAtomically(path, "content"), IsOk());
  std::filesystem::permissions(path, std::filesystem::perms::none, std::filesystem::perm_options::replace);

  const absl::StatusOr<std::string> result = ReadFile(path);
  std::filesystem::permissions(path, std::filesystem::perms::owner_all, std::filesystem::perm_options::replace);

  if (result.ok()) {
    GTEST_SKIP() << "the current user can read a non-readable file";
  }
  EXPECT_THAT(result, StatusIs(absl::StatusCode::kUnknown, HasSubstr("cannot open")));
}

}  // namespace
}  // namespace carve::io
