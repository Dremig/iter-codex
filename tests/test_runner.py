from pathlib import Path

from codex_self_iter.config import LoopConfig, load_config
from codex_self_iter.runner import compute_backoff_sec, extract_json, should_stop


def test_extract_json_direct():
    data = extract_json('{"a": 1, "b": "x"}')
    assert data["a"] == 1
    assert data["b"] == "x"


def test_extract_json_code_fence():
    data = extract_json("hello\n```json\n{\"ok\": true}\n```\nbye")
    assert data["ok"] is True


def test_should_stop_with_global_file(tmp_path: Path):
    cfg = LoopConfig(agent_command_template="codex exec --prompt-file {prompt_file}")
    (tmp_path / ".codex-stop").write_text("", encoding="utf-8")
    assert should_stop(cfg, workspace=tmp_path, state_dir=tmp_path / ".state")


def test_load_config(tmp_path: Path):
    p = tmp_path / "config.toml"
    p.write_text(
        "\n".join(
            [
                'agent_command_template = "x --prompt-file {prompt_file}"',
                "max_iterations = 9",
                "max_stagnation = 2",
                "no_change_gate = false",
                "backoff_base_sec = 7",
                'completion_promise = "ALL_DONE"',
            ]
        ),
        encoding="utf-8",
    )
    cfg = load_config(p, default_agent_cmd="fallback --prompt-file {prompt_file}")
    assert cfg.agent_command_template.startswith("x ")
    assert cfg.max_iterations == 9
    assert cfg.max_stagnation == 2
    assert cfg.no_change_gate is False
    assert cfg.backoff_base_sec == 7
    assert cfg.completion_promise == "ALL_DONE"


def test_compute_backoff_sec():
    assert compute_backoff_sec(5, 300, 1) == 5
    assert compute_backoff_sec(5, 300, 3) == 20
    assert compute_backoff_sec(5, 30, 5) == 30
