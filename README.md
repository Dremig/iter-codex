# codex-self-iter

`codex-self-iter` is a plugin-style repository that runs a continuous autonomous loop for coding tasks:

1. Read `TASK.md` + `plan.md`
2. Generate one small next step
3. Execute the step via agent command
4. Review result and decide whether to continue
5. Repeat until no meaningful next action exists or user stops it

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

## Configuration

See `config.example.toml`.

Important fields:

- `agent_command_template` must include `{prompt_file}`
- `max_iterations = 0` means unbounded loop
- `max_stagnation` prevents infinite cycling on identical `next_focus`

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

## Development

Run tests:

```bash
pytest -q
```

## Security and Automation Boundary

The loop is autonomous at application logic level but still bounded by host permissions, sandbox policy, and tool confirmations.
