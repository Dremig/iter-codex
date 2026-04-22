# codex-self-iter

`codex-self-iter` is a plugin-style repository that runs a continuous autonomous goal loop:

1. Read `TASK.md` + `plan.md`
2. Execute one autonomous iteration in the repository
3. Require the agent to emit a concrete `next_goal`
4. Persist that goal and continue from it
5. Repeat until completion/stop condition

## Repository Layout

```text
.
├── .codex-plugin/plugin.json
├── src/codex_self_iter/
├── tests/
├── examples/
├── scripts/
├── pyproject.toml
└── .github/workflows/ci.yml
```

## Quick Start

1. Install locally:

```bash
pip install -e .[dev]
```

2. Prepare task files in your workspace:

- `TASK.md` (optional)
- `plan.md` (required)

3. Run:

```bash
python3 -m codex_self_iter \
  --workspace . \
  --task-file TASK.md \
  --plan-file plan.md \
  --state-dir .codex-self-iter \
  --agent-command-template "scripts/invoke-codex-agent.sh {prompt_file} {workspace}"
```

Or use:

```bash
./scripts/run-local.sh .
```

## Stop Conditions

- Create `.codex-self-iter/STOP`
- Or create workspace-level `.codex-stop`
- Or interrupt process manually

## Output Artifacts

- `.codex-self-iter/prompts/`: planner/executor/reviewer prompts
- `.codex-self-iter/logs/iterations.jsonl`: loop records
- `.codex-self-iter/status.json`: last iteration state
- `.codex-self-iter/runtime.json`: persisted backoff counters and window
- `.codex-self-iter/loop.lock`: single-instance guard file

## Configuration

See `config.example.toml`.

Important fields:

- `agent_command_template` must include `{prompt_file}`
- `max_iterations = 0` means unbounded loop
- `max_stagnation` prevents infinite cycling on identical `next_focus`
- `no_change_gate` throttles no-op loops when no new git changes appear
- `backoff_*` fields control exponential cooldown behavior
- `lock_file_name` controls the single-instance lock path under state-dir
- `completion_promise` marks completion when included in output

## Approval and Privilege Mode

Default wrapper `scripts/invoke-codex-agent.sh` uses:

- `codex -a never exec ...`  
  This means the run does not ask for manual approval prompts.

Optional bypass mode:

```bash
export CODEX_SELF_ITER_AGENT_MODE=bypass
```

In bypass mode, wrapper uses:

- `codex --dangerously-bypass-approvals-and-sandbox exec ...`  
  This disables approvals and sandboxing entirely. Use only in externally sandboxed environments.

## Binary Resolution (macOS launchd/system services)

When running under `launchd` (or other service managers), interactive shell `PATH` is often not inherited.
If `codex` is not found, set an explicit binary path:

```bash
export CODEX_BIN=/absolute/path/to/codex
```

The default wrapper checks in this order:
1. `CODEX_BIN` (if executable)
2. `PATH` via `command -v codex`
3. common fallback paths (nvm/Homebrew/local bin)

## Development

Run tests:

```bash
pytest -q
```

## Security and Automation Boundary

The loop is autonomous at application logic level but still bounded by host permissions, sandbox policy, and tool confirmations.
