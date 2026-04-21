from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore


@dataclass
class LoopConfig:
    agent_command_template: str
    max_iterations: int = 0
    max_stagnation: int = 4
    command_timeout_sec: int = 1200
    stop_file_name: str = "STOP"
    global_stop_file_name: str = ".codex-stop"
    planner_model_hint: str = "balanced"
    reviewer_model_hint: str = "strict"
    history_tail: int = 8


def read_text(path: Path, default: str = "") -> str:
    if not path.exists():
        return default
    return path.read_text(encoding="utf-8")


def load_config(config_path: Path | None, default_agent_cmd: str) -> LoopConfig:
    if config_path is None:
        return LoopConfig(agent_command_template=default_agent_cmd)
    if tomllib is None:
        raise RuntimeError("tomllib not available, cannot read TOML config.")
    raw = tomllib.loads(read_text(config_path))
    return LoopConfig(
        agent_command_template=raw.get("agent_command_template", default_agent_cmd),
        max_iterations=int(raw.get("max_iterations", 0)),
        max_stagnation=int(raw.get("max_stagnation", 4)),
        command_timeout_sec=int(raw.get("command_timeout_sec", 1200)),
        stop_file_name=str(raw.get("stop_file_name", "STOP")),
        global_stop_file_name=str(raw.get("global_stop_file_name", ".codex-stop")),
        planner_model_hint=str(raw.get("planner_model_hint", "balanced")),
        reviewer_model_hint=str(raw.get("reviewer_model_hint", "strict")),
        history_tail=int(raw.get("history_tail", 8)),
    )
