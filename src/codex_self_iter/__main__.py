from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .runner import run


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Codex-style self-iteration loop.")
    parser.add_argument("--workspace", default=".", help="Repository root")
    parser.add_argument("--task-file", default="TASK.md", help="Task brief file")
    parser.add_argument("--plan-file", default="plan.md", help="Plan file")
    parser.add_argument("--state-dir", default=".codex-self-iter", help="State/log directory")
    parser.add_argument(
        "--agent-command-template",
        default="scripts/invoke-codex-agent.sh {prompt_file} {workspace}",
        help="Command template; supports {prompt_file} and {workspace}",
    )
    parser.add_argument("--config", default="", help="TOML config path (optional)")
    args = parser.parse_args()

    return run(
        workspace=Path(args.workspace).resolve(),
        task_file_name=args.task_file,
        plan_file_name=args.plan_file,
        state_dir_name=args.state_dir,
        agent_command_template=args.agent_command_template,
        config_path=Path(args.config).resolve() if args.config else None,
    )


if __name__ == "__main__":
    sys.exit(main())
