from __future__ import annotations


def autonomous_goal_prompt(
    task_text: str,
    plan_text: str,
    current_goal: str,
    history_jsonl_tail: str,
    model_hint: str,
    completion_promise: str,
) -> str:
    return f"""You are an autonomous coding agent in an endless explore-and-improve loop.
Model style hint: {model_hint}

Primary task:
{task_text}

Plan context:
{plan_text}

Current goal for this iteration:
{current_goal}

Recent iteration history:
{history_jsonl_tail}

You must do real work in the repository (code/tests/docs/commands), then decide the next goal.

Output exactly one JSON object with keys:
- summary: short string, what you did this round
- completed: boolean, true only if overall task is truly complete
- next_goal: short string, required when completed=false
- reason: short string, why next_goal is the right continuation
- evidence: short string, key checks or observations
- stop: boolean (true only if no meaningful next action exists)

Rules:
1) Be self-directed: choose the most valuable next step based on actual repo state.
2) Prefer measurable progress (tests, reproducibility, correctness).
3) If not complete, always provide a concrete next_goal.
4) If complete, include completion token "{completion_promise}" in summary.
"""


def planner_prompt(task_text: str, plan_text: str, history_jsonl_tail: str, model_hint: str) -> str:
    return f"""You are the planner in a self-iterating coding loop.
Model style hint: {model_hint}

Task:
{task_text}

Plan document:
{plan_text}

Recent iteration history:
{history_jsonl_tail}

Output exactly one JSON object with keys:
- objective: short string, one small step
- execution_prompt: detailed prompt for an executor agent to implement the step
- done_if: a concrete verification condition
- stop: boolean (true only if no meaningful next action exists)
- rationale: short string

Rules:
1) Keep the step small and atomic.
2) Prefer code/test/document changes that produce measurable improvement.
3) If task is effectively complete, set stop=true.
"""


def executor_prompt(objective: str, execution_prompt_text: str, done_if: str) -> str:
    return f"""You are the executor in a self-iterating coding loop.
Implement exactly one small step.

Objective:
{objective}

Execution requirements:
{execution_prompt_text}

Done condition:
{done_if}

Constraints:
1) Make practical code changes directly in repository files.
2) Run focused checks/tests when relevant.
3) Return a concise summary:
   - changed_files
   - checks_run
   - result_against_done_condition
   - remaining_risk
"""


def reviewer_prompt(
    objective: str,
    done_if: str,
    execution_output: str,
    git_state: str,
    model_hint: str,
) -> str:
    return f"""You are the reviewer in a self-iterating coding loop.
Model style hint: {model_hint}

Objective:
{objective}

Done condition:
{done_if}

Executor output:
{execution_output}

Git snapshot:
{git_state}

Output exactly one JSON object with keys:
- continue: boolean
- confidence: number (0 to 1)
- next_focus: short string
- reason: short string

Rules:
1) continue=false only when no meaningful next action exists for the user goal.
2) Be strict about quality and verification.
"""
