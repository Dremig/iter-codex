#!/usr/bin/env bash
set -euo pipefail

python3 -m codex_self_iter \
  --workspace "${1:-.}" \
  --task-file "${2:-TASK.md}" \
  --plan-file "${3:-plan.md}" \
  --state-dir "${4:-.codex-self-iter}" \
  --config "${5:-config.example.toml}"
