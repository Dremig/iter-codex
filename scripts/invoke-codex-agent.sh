#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: $0 <prompt-file> <workspace>" >&2
  exit 2
fi

prompt_file="$1"
workspace="$2"

# Default mode: auto-confirm approval requests while keeping sandboxing.
if [[ "${CODEX_SELF_ITER_AGENT_MODE:-}" == "bypass" ]]; then
  # Extremely dangerous: no approval prompts and no sandbox.
  cat "$prompt_file" | codex --dangerously-bypass-approvals-and-sandbox exec -C "$workspace" -
else
  # No manual confirmation; command failures are returned directly to the model.
  cat "$prompt_file" | codex -a never exec -C "$workspace" -
fi
