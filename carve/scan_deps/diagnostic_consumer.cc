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

#include "carve/scan_deps/diagnostic_consumer.h"

#include "llvm/ADT/SmallString.h"

namespace carve::scan_deps::scan_deps_internal {

void CapturingDiagnosticConsumer::HandleDiagnostic(
    clang::DiagnosticsEngine::Level level,
    const clang::Diagnostic& info) {
  clang::DiagnosticConsumer::HandleDiagnostic(level, info);
  if (level < clang::DiagnosticsEngine::Error) {
    return;
  }
  constexpr unsigned kMessageInlineCapacity = 256;
  llvm::SmallString<kMessageInlineCapacity> message;
  info.FormatDiagnostic(message);
  if (!sink_.empty()) {
    sink_.push_back('\n');
  }
  sink_.append(message.data(), message.size());
}

}  // namespace carve::scan_deps::scan_deps_internal
