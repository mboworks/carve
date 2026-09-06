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

#include "carve/scan_deps/scan_deps.h"

#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

#include "absl/status/status.h"
#include "carve/scan_deps/diagnostic_consumer.h"
#include "clang/Basic/Diagnostic.h"
#include "clang/Basic/DiagnosticIDs.h"
#include "clang/Basic/DiagnosticOptions.h"
#include "gmock/gmock.h"
#include "gtest/gtest.h"
#include "llvm/ADT/IntrusiveRefCntPtr.h"
#include "mbo/testing/status.h"

namespace carve::scan_deps {
namespace {

using ::mbo::testing::IsOkAndHolds;
using ::mbo::testing::StatusIs;
using ::testing::AllOf;
using ::testing::Contains;
using ::testing::Eq;
using ::testing::HasSubstr;

void EmitDiagnostic(clang::DiagnosticsEngine::Level level, clang::DiagnosticConsumer& consumer) {
  auto ids = llvm::makeIntrusiveRefCnt<clang::DiagnosticIDs>();
  clang::DiagnosticOptions options;
  clang::DiagnosticsEngine diagnostics(ids, options, &consumer, /*ShouldOwnClient=*/false);
  diagnostics.Report(diagnostics.getCustomDiagID(level, "test diagnostic"));
}

void Write(const std::filesystem::path& path, std::string_view content) {
  std::ofstream(path) << content;
}

TEST(ScanDependenciesTest, ReportsSourceAndIncludedHeader) {
  const std::filesystem::path dir = std::filesystem::path(::testing::TempDir()) / "carve_scan";
  std::filesystem::remove_all(dir);
  std::filesystem::create_directories(dir);
  Write(dir / "dep.h", "#pragma once\nint dep();\n");
  Write(dir / "main.cc", "#include \"dep.h\"\nint main() { return dep(); }\n");

  const std::vector<std::string> args = {"clang", "-c", (dir / "main.cc").string()};
  EXPECT_THAT(
      ScanDependencies(args, dir.string()),
      IsOkAndHolds(AllOf(Contains(HasSubstr("main.cc")), Contains(HasSubstr("dep.h")))));
}

TEST(ScanDependenciesTest, MissingHeaderIsAnError) {
  const std::filesystem::path dir = std::filesystem::path(::testing::TempDir()) / "carve_scan_missing";
  std::filesystem::remove_all(dir);
  std::filesystem::create_directories(dir);
  Write(dir / "main.cc", "#include \"nope.h\"\nint main() { return 0; }\n");

  const std::vector<std::string> args = {"clang", "-c", (dir / "main.cc").string()};
  EXPECT_THAT(ScanDependencies(args, dir.string()), StatusIs(absl::StatusCode::kInvalidArgument));
}

TEST(ScanDependenciesTest, NonErrorDiagnosticDoesNotFailScan) {
  const std::filesystem::path dir = std::filesystem::path(::testing::TempDir()) / "carve_scan_warning";
  std::filesystem::remove_all(dir);
  std::filesystem::create_directories(dir);
  Write(dir / "main.cc", "#warning carve dependency-scan warning\nint main() { return 0; }\n");

  const std::vector<std::string> args = {"clang", "-c", (dir / "main.cc").string()};
  EXPECT_THAT(ScanDependencies(args, dir.string()), IsOkAndHolds(Contains(HasSubstr("main.cc"))));
}

TEST(CapturingDiagnosticConsumerTest, IgnoresWarningsAndCombinesErrors) {
  std::string captured;
  scan_deps_internal::CapturingDiagnosticConsumer consumer(captured);

  EmitDiagnostic(clang::DiagnosticsEngine::Warning, consumer);
  EXPECT_THAT(captured, Eq(""));
  EmitDiagnostic(clang::DiagnosticsEngine::Error, consumer);
  EmitDiagnostic(clang::DiagnosticsEngine::Error, consumer);
  EXPECT_THAT(captured, Eq("test diagnostic\ntest diagnostic"));
}

}  // namespace
}  // namespace carve::scan_deps
