# Changelog

## Unreleased

- Fixed default agent invocation to use valid Codex CLI arguments.
- Added `scripts/invoke-codex-agent.sh` wrapper.
- Added support for two execution modes:
  - `-a never` default (no manual approvals)
  - `--dangerously-bypass-approvals-and-sandbox` via `CODEX_SELF_ITER_AGENT_MODE=bypass`

## 0.1.0 - 2026-04-21

- Initial public repository structure for `codex-self-iter`.
- Added Python package layout (`src/`), CLI entrypoint, and tests.
- Added plugin manifest at `.codex-plugin/plugin.json`.
- Added GitHub Actions CI for lint-free test run.
