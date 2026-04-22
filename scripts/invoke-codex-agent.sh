#!/usr/bin/env bash
set -uo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: $0 <prompt-file> <workspace>" >&2
  exit 2
fi

prompt_file="$1"
workspace="$2"
state_dir="${CODEX_SELF_ITER_STATE_DIR:-$workspace/.codex-self-iter}"
session_file="${CODEX_SELF_ITER_SESSION_FILE:-$state_dir/codex-session-id}"

mkdir -p "$state_dir"

msg_file="$(mktemp)"
err_file="$(mktemp)"
trap 'rm -f "$msg_file" "$err_file"' EXIT

session_id=""
if [[ -f "$session_file" ]]; then
  session_id="$(tr -d '[:space:]' < "$session_file" 2>/dev/null || true)"
fi

resolve_codex_bin() {
  if [[ -n "${CODEX_BIN:-}" ]] && [[ -x "${CODEX_BIN:-}" ]]; then
    echo "$CODEX_BIN"
    return 0
  fi
  if command -v codex >/dev/null 2>&1; then
    command -v codex
    return 0
  fi
  local candidates=(
    "$HOME/.nvm/versions/node/v24.10.0/bin/codex"
    "$HOME/.nvm/versions/node/v*/bin/codex"
    "/opt/homebrew/bin/codex"
    "/usr/local/bin/codex"
  )
  local c
  for c in "${candidates[@]}"; do
    for m in $c; do
      if [[ -x "$m" ]]; then
        echo "$m"
        return 0
      fi
    done
  done
  return 1
}

CODEX_CMD="$(resolve_codex_bin || true)"
if [[ -z "$CODEX_CMD" ]]; then
  cat >&2 <<'EOF'
Error: codex binary not found.
Tips:
- Set CODEX_BIN to an absolute path (recommended for launchd/systemd)
- Or ensure codex is available in PATH
EOF
  exit 127
fi

run_codex_new() {
  if [[ "${CODEX_SELF_ITER_AGENT_MODE:-}" == "bypass" ]]; then
    cat "$prompt_file" | "$CODEX_CMD" --dangerously-bypass-approvals-and-sandbox exec -C "$workspace" -o "$msg_file" - >/dev/null 2>"$err_file"
  else
    cat "$prompt_file" | "$CODEX_CMD" -a never exec -C "$workspace" -o "$msg_file" - >/dev/null 2>"$err_file"
  fi
  return $?
}

run_codex_resume() {
  local sid="$1"
  if [[ "${CODEX_SELF_ITER_AGENT_MODE:-}" == "bypass" ]]; then
    cat "$prompt_file" | "$CODEX_CMD" --dangerously-bypass-approvals-and-sandbox exec resume "$sid" -o "$msg_file" - >/dev/null 2>"$err_file"
  else
    cat "$prompt_file" | "$CODEX_CMD" -a never exec resume "$sid" -o "$msg_file" - >/dev/null 2>"$err_file"
  fi
  return $?
}

rc=1
if [[ -n "$session_id" ]]; then
  run_codex_resume "$session_id"
  rc=$?
fi

if [[ $rc -ne 0 ]]; then
  run_codex_new
  rc=$?
fi

if [[ $rc -eq 0 ]]; then
  if [[ -z "$session_id" ]]; then
    sid="$(rg -o -N 'session id:\s*([0-9a-fA-F-]{36})' "$err_file" | head -n1 | awk '{print $3}' || true)"
    if [[ -n "$sid" ]]; then
      echo "$sid" > "$session_file"
    fi
  fi
  cat "$msg_file"
else
  cat "$err_file"
fi

exit $rc
