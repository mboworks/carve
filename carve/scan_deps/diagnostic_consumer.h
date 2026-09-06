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

#ifndef CARVE_SCAN_DEPS_DIAGNOSTIC_CONSUMER_H_
#define CARVE_SCAN_DEPS_DIAGNOSTIC_CONSUMER_H_

#include <string>

#include "clang/Basic/Diagnostic.h"

namespace carve::scan_deps::scan_deps_internal {

// Captures error diagnostics emitted by Clang's dependency scanner while
// deliberately ignoring warnings and notes.
class CapturingDiagnosticConsumer : public clang::DiagnosticConsumer {
 public:
  explicit CapturingDiagnosticConsumer(std::string& sink) : sink_(sink) {}

  void HandleDiagnostic(clang::DiagnosticsEngine::Level level, const clang::Diagnostic& info) override;

 private:
  std::string& sink_;
};

}  // namespace carve::scan_deps::scan_deps_internal

#endif  // CARVE_SCAN_DEPS_DIAGNOSTIC_CONSUMER_H_
