<!-- BEGIN CODEX-CONFIG KEV -->
## Document decisions with Kev

For document classification, explicitly defined choices, or rubric scoring, use the `kev-decisions` skill when it fits the user's task; do not wait for the user to name it. Prefer the local Kev server. Load the skill before invoking its client, verify the endpoint, and do not silently fall back to hosted inference. Keep returned probabilities distinct from verified accuracy and cite document evidence. Use other methods when Kev is unavailable or unsuitable, and disclose that it was not run. This rule does not replace live AI Model Benchmarks for model comparisons.

Codex user skill: `~/.agents/skills/kev-decisions/SKILL.md`. Claude Code user skill: `~/.claude/skills/kev-decisions/SKILL.md` (under `CLAUDE_CONFIG_DIR` when configured). Source and portable installer: `codex-config/skills/kev-decisions/` and `codex-config/scripts/install_kev.py`. Preserve unrelated local instructions. Distinguish locally installed instructions, a running local model and hosted execution.
<!-- END CODEX-CONFIG KEV -->

## Preferred browser automation: Jev Ultrafast

- User preference: use Jev Ultrafast as the default for browser automation to
  accelerate work whenever the task and available browser access support it.
- Local checkout: `~/.codex/tools/jev-ultrafast`.
  Read its `AGENTS.md` and `README.md` before using it. On a new machine, run `uv sync --frozen --python 3.12 --link-mode copy` there first.
  Dependencies live in its `.venv`; use `uv run --no-sync` from that directory.
- Screenshots and local browser recordings are disabled by user preference.
  Run Jev with `screenshots=False` and without `record_dir`; avoid the demo
  inspector, which enables screenshots. Do not start recordings or capture
  screenshots unless the user explicitly requests them again.
- Text-entry model preference: `inception/mercury-2.5` through OpenRouter,
  with `TEXT_MODEL_BASE_URL=https://openrouter.ai/api/v1` and
  `TEXT_MODEL_REASONING=none`. The checkout's ignored `.env` holds these
  non-secret settings; use `uv run --no-sync --env-file .env` for library runs.
- Jev selects operations and indexed targets; Browser Harness executes them.
  This preference does not replace Codex's built-in browser tool implementation.
- Use existing `TYPESAFE_API_KEY` and `TEXT_MODEL_API_KEY`. If the latter is absent
  and the text helper uses the documented OpenRouter endpoint, map the existing
  `OPENROUTER_API_KEY` to `TEXT_MODEL_API_KEY` in the child process only. On Windows,
  saved user environment variables may need loading into that process. Never
  print keys or write their values to instructions, logs, or tracked files.
- Verify browser connectivity before execution; installation alone does not
  establish a working browser connection. Use bounded runs and independently
  verify the final browser outcome, even when Jev reports DONE.
- If the task needs unsupported controls, an explicitly selected browser/tab
  that the harness cannot access, unavailable credentials/connectivity, or a
  workflow that cannot preserve required action-time approvals, use the available
  browser/computer tools and briefly state the fallback. Higher-priority tool
  restrictions and user-specified browser/session choices still apply.
- This preference grants no additional authority for transactions, messages,
  account changes, sensitive-data transmission, or other protected actions.
