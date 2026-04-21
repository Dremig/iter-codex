from __future__ import annotations

import datetime as dt
import json
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any

from .config import LoopConfig, load_config, read_text
from .prompts import executor_prompt, planner_prompt, reviewer_prompt


def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        raise ValueError("empty output")
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    code_fence = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if code_fence:
        return json.loads(code_fence.group(1))

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])

    raise ValueError("cannot parse JSON object from agent output")


def run_command(command_template: str, workspace: Path, prompt_file: Path, timeout_sec: int) -> tuple[int, str]:
    cmd_str = command_template.format(
        prompt_file=str(prompt_file),
        workspace=str(workspace),
    )
    args = shlex.split(cmd_str)
    proc = subprocess.run(
        args,
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )
    out = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    return proc.returncode, out.strip()


def git_snapshot(workspace: Path) -> str:
    cmds = [
        ["git", "status", "--short"],
        ["git", "diff", "--stat"],
    ]
    chunks: list[str] = []
    for cmd in cmds:
        proc = subprocess.run(cmd, cwd=workspace, capture_output=True, text=True)
        content = (proc.stdout or "").strip()
        if content:
            chunks.append(f"$ {' '.join(cmd)}\n{content}")
    return "\n\n".join(chunks) if chunks else "No git changes detected."


def history_tail(history_path: Path, n: int) -> str:
    if not history_path.exists():
        return "[]"
    lines = read_text(history_path).splitlines()
    tail = lines[-n:] if n > 0 else lines
    return "[\n" + ",\n".join(tail) + "\n]"


def should_stop(config: LoopConfig, workspace: Path, state_dir: Path) -> bool:
    return (state_dir / config.stop_file_name).exists() or (workspace / config.global_stop_file_name).exists()


def run(
    workspace: Path,
    task_file_name: str = "TASK.md",
    plan_file_name: str = "plan.md",
    state_dir_name: str = ".codex-self-iter",
    agent_command_template: str = "scripts/invoke-codex-agent.sh {prompt_file} {workspace}",
    config_path: Path | None = None,
) -> int:
    task_file = workspace / task_file_name
    plan_file = workspace / plan_file_name
    state_dir = workspace / state_dir_name
    prompts_dir = state_dir / "prompts"
    logs_dir = state_dir / "logs"
    history_path = logs_dir / "iterations.jsonl"
    status_path = state_dir / "status.json"

    cfg = load_config(config_path, agent_command_template)
    if "{prompt_file}" not in cfg.agent_command_template:
        raise ValueError("agent_command_template must include {prompt_file}.")

    task_text = read_text(task_file).strip()
    plan_text = read_text(plan_file).strip()
    if not task_text:
        task_text = "No TASK.md found. Infer the main goal from plan.md and repository context."
    if not plan_text:
        raise FileNotFoundError(f"plan file missing or empty: {plan_file}")

    stagnation = 0
    last_next_focus = ""
    iteration = 0

    while True:
        if cfg.max_iterations > 0 and iteration >= cfg.max_iterations:
            break
        if should_stop(cfg, workspace, state_dir):
            break

        iteration += 1
        iter_tag = f"iter_{iteration:04d}"

        planner_text = planner_prompt(
            task_text=task_text,
            plan_text=plan_text,
            history_jsonl_tail=history_tail(history_path, cfg.history_tail),
            model_hint=cfg.planner_model_hint,
        )
        planner_prompt_file = prompts_dir / f"{iter_tag}.planner.md"
        write_text(planner_prompt_file, planner_text)
        p_code, p_out = run_command(cfg.agent_command_template, workspace, planner_prompt_file, cfg.command_timeout_sec)
        if p_code != 0:
            append_jsonl(
                history_path,
                {"ts": now(), "iteration": iteration, "phase": "planner_error", "return_code": p_code, "output": p_out},
            )
            break
        try:
            plan_step = extract_json(p_out)
        except Exception as exc:
            append_jsonl(
                history_path,
                {"ts": now(), "iteration": iteration, "phase": "planner_parse_error", "error": str(exc), "output": p_out},
            )
            break

        objective = str(plan_step.get("objective", "")).strip()
        exec_prompt_text = str(plan_step.get("execution_prompt", "")).strip()
        done_if = str(plan_step.get("done_if", "")).strip()
        planner_stop = bool(plan_step.get("stop", False))
        rationale = str(plan_step.get("rationale", "")).strip()

        if planner_stop:
            append_jsonl(
                history_path,
                {
                    "ts": now(),
                    "iteration": iteration,
                    "phase": "planner_stop",
                    "objective": objective,
                    "rationale": rationale,
                },
            )
            break

        exec_text = executor_prompt(objective, exec_prompt_text, done_if)
        exec_prompt_file = prompts_dir / f"{iter_tag}.executor.md"
        write_text(exec_prompt_file, exec_text)
        e_code, e_out = run_command(cfg.agent_command_template, workspace, exec_prompt_file, cfg.command_timeout_sec)

        gstate = git_snapshot(workspace)
        review_text = reviewer_prompt(
            objective=objective,
            done_if=done_if,
            execution_output=e_out if e_out else f"(executor exited with code {e_code} and no output)",
            git_state=gstate,
            model_hint=cfg.reviewer_model_hint,
        )
        review_prompt_file = prompts_dir / f"{iter_tag}.reviewer.md"
        write_text(review_prompt_file, review_text)
        r_code, r_out = run_command(cfg.agent_command_template, workspace, review_prompt_file, cfg.command_timeout_sec)
        if r_code != 0:
            append_jsonl(
                history_path,
                {"ts": now(), "iteration": iteration, "phase": "reviewer_error", "return_code": r_code, "output": r_out},
            )
            break

        try:
            review = extract_json(r_out)
        except Exception as exc:
            append_jsonl(
                history_path,
                {"ts": now(), "iteration": iteration, "phase": "reviewer_parse_error", "error": str(exc), "output": r_out},
            )
            break

        next_focus = str(review.get("next_focus", "")).strip()
        do_continue = bool(review.get("continue", True))
        confidence = float(review.get("confidence", 0))
        reason = str(review.get("reason", "")).strip()

        if next_focus and next_focus == last_next_focus:
            stagnation += 1
        else:
            stagnation = 0
        last_next_focus = next_focus

        row = {
            "ts": now(),
            "iteration": iteration,
            "objective": objective,
            "done_if": done_if,
            "rationale": rationale,
            "executor_return_code": e_code,
            "review_continue": do_continue,
            "review_confidence": confidence,
            "review_next_focus": next_focus,
            "review_reason": reason,
        }
        append_jsonl(history_path, row)
        write_text(status_path, json.dumps(row, ensure_ascii=False, indent=2))

        if not do_continue:
            break
        if stagnation >= cfg.max_stagnation:
            append_jsonl(
                history_path,
                {
                    "ts": now(),
                    "iteration": iteration,
                    "phase": "stop_stagnation",
                    "stagnation": stagnation,
                    "next_focus": next_focus,
                },
            )
            break
        if should_stop(cfg, workspace, state_dir):
            break

    return 0
