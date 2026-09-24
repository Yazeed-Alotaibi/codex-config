<!-- BEGIN CODEX-CONFIG KEV -->
## Document decisions with Kev

For document classification, explicitly defined choices, or rubric scoring, use the `kev-decisions` skill when it fits the user's task; do not wait for the user to name it. Prefer the local Kev server. Load the skill before invoking its client, verify the endpoint, and do not silently fall back to hosted inference. Keep returned probabilities distinct from verified accuracy and cite document evidence. Use other methods when Kev is unavailable or unsuitable, and disclose that it was not run. This rule does not replace live AI Model Benchmarks for model comparisons.

Codex user skill: `~/.agents/skills/kev-decisions/SKILL.md`. Claude Code user skill: `~/.claude/skills/kev-decisions/SKILL.md` (under `CLAUDE_CONFIG_DIR` when configured). Source and portable installer: `codex-config/skills/kev-decisions/` and `codex-config/scripts/install_kev.py`. Preserve unrelated local instructions. Distinguish locally installed instructions, a running local model and hosted execution.
<!-- END CODEX-CONFIG KEV -->
