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
  --agent-command-template "codex exec --auto --prompt-file {prompt_file}"
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

## Development

Run tests:

```bash
pytest -q
```

## Security and Automation Boundary

The loop is autonomous at application logic level but still bounded by host permissions, sandbox policy, and tool confirmations.
