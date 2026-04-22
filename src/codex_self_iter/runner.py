from __future__ import annotations

import datetime as dt
import fcntl
import json
import re
import shlex
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .config import LoopConfig, load_config, read_text
from .prompts import autonomous_goal_prompt


def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def now_dt() -> dt.datetime:
    return dt.datetime.now()


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def write_status(path: Path, payload: dict[str, Any]) -> None:
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


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


def git_porcelain(workspace: Path) -> str:
    proc = subprocess.run(["git", "status", "--porcelain"], cwd=workspace, capture_output=True, text=True)
    return (proc.stdout or "").strip()


def history_tail(history_path: Path, n: int) -> str:
    if not history_path.exists():
        return "[]"
    lines = read_text(history_path).splitlines()
    tail = lines[-n:] if n > 0 else lines
    return "[\n" + ",\n".join(tail) + "\n]"


def should_stop(config: LoopConfig, workspace: Path, state_dir: Path) -> bool:
    return (state_dir / config.stop_file_name).exists() or (workspace / config.global_stop_file_name).exists()


def read_runtime(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"consecutive_no_change": 0, "consecutive_errors": 0, "backoff_until": "", "current_goal": ""}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"consecutive_no_change": 0, "consecutive_errors": 0, "backoff_until": "", "current_goal": ""}
    if not isinstance(data, dict):
        return {"consecutive_no_change": 0, "consecutive_errors": 0, "backoff_until": "", "current_goal": ""}
    return {
        "consecutive_no_change": int(data.get("consecutive_no_change", 0)),
        "consecutive_errors": int(data.get("consecutive_errors", 0)),
        "backoff_until": str(data.get("backoff_until", "")),
        "current_goal": str(data.get("current_goal", "")),
    }


def write_runtime(path: Path, runtime: dict[str, Any]) -> None:
    write_text(path, json.dumps(runtime, ensure_ascii=False, indent=2))


def parse_iso(ts: str) -> dt.datetime | None:
    if not ts:
        return None
    try:
        return dt.datetime.fromisoformat(ts)
    except Exception:
        return None


def compute_backoff_sec(base: int, cap: int, streak: int) -> int:
    b = max(1, base)
    c = max(b, cap)
    exp = max(0, streak - 1)
    return min(c, b * (2**exp))


def apply_backoff(runtime: dict[str, Any], seconds: int) -> str:
    until = now_dt() + dt.timedelta(seconds=max(0, seconds))
    runtime["backoff_until"] = until.isoformat(timespec="seconds")
    return runtime["backoff_until"]


@contextmanager
def single_instance_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        f.write(str(now()) + "\n")
        f.flush()
        yield True
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


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
    runtime_path = state_dir / "runtime.json"

    cfg = load_config(config_path, agent_command_template)
    if "{prompt_file}" not in cfg.agent_command_template:
        raise ValueError("agent_command_template must include {prompt_file}.")

    task_text = read_text(task_file).strip()
    plan_text = read_text(plan_file).strip()
    if not task_text:
        task_text = "No TASK.md found. Infer the main goal from plan.md and repository context."
    if not plan_text:
        raise FileNotFoundError(f"plan file missing or empty: {plan_file}")

    runtime = read_runtime(runtime_path)
    backoff_until = parse_iso(runtime.get("backoff_until", ""))
    if backoff_until and now_dt() < backoff_until:
        row = {
            "ts": now(),
            "phase": "backoff_active",
            "state": "backoff",
            "reason": "backoff_window_open",
            "backoff_until": runtime.get("backoff_until", ""),
        }
        append_jsonl(history_path, row)
        write_status(status_path, row)
        return 0

    with single_instance_lock(state_dir / cfg.lock_file_name) as acquired:
        if not acquired:
            row = {
                "ts": now(),
                "phase": "already_running",
                "state": "idle",
                "reason": "single_instance_lock_busy",
            }
            append_jsonl(history_path, row)
            write_status(status_path, row)
            return 0

        iteration = 0
        current_goal = runtime.get("current_goal", "").strip()
        if not current_goal:
            current_goal = f"Start from task intent and make one measurable improvement.\n\nTask:\n{task_text}\n\nPlan:\n{plan_text}"

        while True:
            if cfg.max_iterations > 0 and iteration >= cfg.max_iterations:
                break
            if should_stop(cfg, workspace, state_dir):
                break

            iteration += 1
            iter_tag = f"iter_{iteration:04d}"
            git_before = git_porcelain(workspace)

            prompt_text = autonomous_goal_prompt(
                task_text=task_text,
                plan_text=plan_text,
                current_goal=current_goal,
                history_jsonl_tail=history_tail(history_path, cfg.history_tail),
                model_hint=cfg.planner_model_hint,
                completion_promise=cfg.completion_promise,
            )
            prompt_file = prompts_dir / f"{iter_tag}.goal.md"
            write_text(prompt_file, prompt_text)

            code, out = run_command(cfg.agent_command_template, workspace, prompt_file, cfg.command_timeout_sec)
            if code != 0:
                runtime["consecutive_errors"] = int(runtime.get("consecutive_errors", 0)) + 1
                backoff_sec = compute_backoff_sec(
                    cfg.backoff_base_sec, cfg.backoff_max_sec, int(runtime["consecutive_errors"])
                )
                backoff_until_ts = apply_backoff(runtime, backoff_sec)
                write_runtime(runtime_path, runtime)
                append_jsonl(
                    history_path,
                    {
                        "ts": now(),
                        "iteration": iteration,
                        "phase": "agent_error",
                        "state": "error",
                        "return_code": code,
                        "backoff_until": backoff_until_ts,
                        "output": out,
                    },
                )
                break

            try:
                step = extract_json(out)
            except Exception as exc:
                runtime["consecutive_errors"] = int(runtime.get("consecutive_errors", 0)) + 1
                backoff_sec = compute_backoff_sec(
                    cfg.backoff_base_sec, cfg.backoff_max_sec, int(runtime["consecutive_errors"])
                )
                backoff_until_ts = apply_backoff(runtime, backoff_sec)
                write_runtime(runtime_path, runtime)
                append_jsonl(
                    history_path,
                    {
                        "ts": now(),
                        "iteration": iteration,
                        "phase": "agent_parse_error",
                        "state": "error",
                        "error": str(exc),
                        "backoff_until": backoff_until_ts,
                        "output": out,
                    },
                )
                break

            summary = str(step.get("summary", "")).strip() or str(step.get("objective", "")).strip() or "No summary"
            reason = str(step.get("reason", "")).strip() or str(step.get("rationale", "")).strip()
            evidence = str(step.get("evidence", "")).strip()
            completed = bool(step.get("completed", False))
            stop = bool(step.get("stop", False))
            next_goal = str(step.get("next_goal", "")).strip()
            git_after = git_porcelain(workspace)
            has_new_changes = git_after != git_before

            runtime["consecutive_errors"] = 0
            runtime["current_goal"] = next_goal or current_goal

            row: dict[str, Any] = {
                "ts": now(),
                "iteration": iteration,
                "phase": "goal_iteration",
                "state": "running",
                "goal_in": current_goal,
                "summary": summary,
                "reason": reason,
                "evidence": evidence,
                "next_goal": runtime["current_goal"],
                "has_new_changes": has_new_changes,
                "completed": completed,
                "stop": stop,
            }

            completion_by_token = bool(cfg.completion_promise and (cfg.completion_promise in out))
            if completed or stop or completion_by_token:
                row["state"] = "idle"
                row["reason"] = "completed_or_stop"
                runtime["backoff_until"] = ""
                append_jsonl(history_path, row)
                write_status(status_path, row)
                write_runtime(runtime_path, runtime)
                break

            if not has_new_changes and cfg.no_change_gate:
                runtime["consecutive_no_change"] = int(runtime.get("consecutive_no_change", 0)) + 1
                wait_sec = compute_backoff_sec(
                    cfg.no_change_backoff_sec, cfg.backoff_max_sec, int(runtime["consecutive_no_change"])
                )
                row["state"] = "backoff"
                row["reason"] = "no_new_changes"
                row["backoff_until"] = apply_backoff(runtime, wait_sec)
            else:
                runtime["consecutive_no_change"] = 0
                runtime["backoff_until"] = ""

            append_jsonl(history_path, row)
            write_status(status_path, row)
            write_runtime(runtime_path, runtime)

            current_goal = str(runtime.get("current_goal", "")).strip() or current_goal

    return 0

