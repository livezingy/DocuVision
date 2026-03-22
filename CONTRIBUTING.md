# Contributing guidelines — DocuVision

This document collects repository rules from `.cursor` that cannot be enforced by EditorConfig (editor formatting). Follow these rules when contributing code, documentation, or other changes.

## Purpose
These rules capture language, documentation, API, security and process constraints that are organizational or behavioral (cannot be enforced by text-editor settings).

## Key rules (non-EditorConfig)

- **Code comments and inline comments MUST be in English.**
- **All docstrings MUST be written in English** and follow a consistent style (Google or NumPy docstring style). Include usage examples for public APIs.
- **Public API documentation is required.** Any new public function/class/module must include docstrings and, when appropriate, update top-level docs.
- **Add type hints** for all function parameters and return values. Prefer full annotations over `Any` when reasonable.
- **Tests:** Update or add unit/integration tests when behaviour changes. New features should include tests demonstrating expected behavior.
- **Preserve backward compatibility** where possible; if a breaking change is unavoidable, document migration steps and bump versioning where applicable.
- **Error handling:** Provide meaningful error messages and log relevant context. Avoid exposing secrets in logs.
- **Security:** Validate and sanitize all user inputs, sanitize file paths, and use environment variables for secrets. Enforce reasonable size limits for uploaded files.
- **Naming & quality:** Use meaningful variable and function names, avoid magic numbers (use constants), and keep functions focused and single-purpose.
- **Performance:** Profile before optimizing. Use async for I/O-bound concurrency, cache expensive computations, and lazy-load heavy dependencies where appropriate.

## Project-specific guidelines

- **Model & engine selection:** Prefer open-source, offline-capable models. Implement primary/fallback engine patterns and log which engine is used.
- **UI & user-facing text:** All UI strings, error messages and user-facing text must be in English.
- **Language of responses (internal tooling/agents):** Agent responses to users in interactive/support scenarios are handled per team convention; contributors should focus on code/docs language rules above.

## Linting & checks

- EditorConfig is present at the repository root and covers whitespace, indentation, EOL and basic formatting.
- Run linters and formatters (project recommended tools) before submitting a PR. Add pre-commit hooks if appropriate.
- There is a validation script for `.cursor` rules at `.cursor/rules/validate_rules.py`; keep rule files well-formed if you edit them.

## How to submit

1. Fork/branch, implement changes and update/add tests.
2. Run linters/formatters and fix issues.
3. Add or update documentation (docstrings, README sections, or top-level docs) when behaviour or APIs change.
4. Create a PR with a clear description and list of changed files; mention any migration steps for breaking changes.

## Questions
If you're unsure about a rule or need an exception, open an issue or ask a maintainer in the project channel and document the decision in the PR.
