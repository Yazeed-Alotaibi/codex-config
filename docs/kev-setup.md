# Kev on every computer: Codex + Claude Code

## What is shared

`codex-config` is the source of truth for the Kev skill and its short global routing rule. It does not synchronize passwords, OAuth sessions, model weights, or all local settings.

| Component | Per-computer destination |
| --- | --- |
| Codex global instructions | `$CODEX_HOME/AGENTS.md`, default `~/.codex/AGENTS.md` |
| Active Codex override, if present | `$CODEX_HOME/AGENTS.override.md` also receives the managed block |
| Codex user skill | `~/.agents/skills/kev-decisions/` |
| Claude Code global instructions | `$CLAUDE_CONFIG_DIR/CLAUDE.md`, default `~/.claude/CLAUDE.md` |
| Claude Code user skill | `$CLAUDE_CONFIG_DIR/skills/kev-decisions/` |

The root `CLAUDE.md` imports `AGENTS.md` for repository work. The installer copies only the marked Kev rule into each real global file, preserving other instructions. It does not alter Codex/Claude permissions, hooks, settings or authentication. Existing files it changes are backed up beside the originals as timestamped `.bak` files.

## First setup on each computer

Requires Git access to this private repository and Python 3.10+. Use a separate checkout first: some computers already keep this repository inside `~/.codex` and may have untracked local AGENTS.md files. A normal pull refuses to overwrite them. Do not force, reset, clean or overwrite those files.

Example in Windows PowerShell, using a new destination:

```powershell
git clone https://github.com/Yazeed-Alotaibi/codex-config.git "$HOME\agent-configs\codex-config"
if ($LASTEXITCODE -ne 0) { throw "Clone failed; inspect the existing destination or Git access." }
py -3 "$HOME\agent-configs\codex-config\scripts\install_kev.py"
if ($LASTEXITCODE -ne 0) { throw "Kev instruction/skill installation failed." }
py -3 "$HOME\agent-configs\codex-config\scripts\install_kev.py" --check
```

If the repository is already cloned at that destination, inspect its Git status and update it using the update steps below. If `py` is unavailable but `python --version` is 3.10+, use `python`. The installer can also run from an existing checkout at `~/.codex`; it preserves the canonical AGENTS.md source and handles an existing global override.

Linux/macOS, from a new checkout:

```bash
git clone https://github.com/Yazeed-Alotaibi/codex-config.git "$HOME/agent-configs/codex-config"
cd "$HOME/agent-configs/codex-config"
python3 scripts/install_kev.py
python3 scripts/install_kev.py --check
```

Run each step only after the preceding command succeeds. To inspect before writing, use `--dry-run`. Explicit `--codex-home` and `--claude-home` support custom locations. `--home` is for isolated installs/tests and ignores real HOME-based configuration variables unless explicit home overrides are passed.

A successful install/check verifies files on **that computer only**. It does not install on other computers or synchronize automatically. Repeat there. New Codex/Claude sessions should discover the updated instructions/skill; verify by asking the agent to locate `kev-decisions`. Claude Code can invoke `/kev-decisions`; this local setup does not install the skill in claude.ai/Cowork cloud sessions.

## Local model execution

The installer installs instructions and a stdlib client, **not model weights or the inference runtime**.

Follow [local setup](../skills/kev-decisions/references/local-setup.md) on each machine that should run its own model. Default: native server at `http://127.0.0.1:8009`; there is no automatic hosted fallback. The model server has a separate Python 3.12/3.13 environment.

After the server starts, run a synthetic check from the skill directory:

```powershell
py -3 "$HOME\.agents\skills\kev-decisions\scripts\kev_client.py" check
py -3 "$HOME\.agents\skills\kev-decisions\scripts\kev_client.py" decide --state-file "$HOME\.agents\skills\kev-decisions\references\example-state.txt" --questions-file "$HOME\.agents\skills\kev-decisions\references\example-questions.json"
```

For authorized cloud processing only, `--hosted` selects the Hugging Face Space. The hosted Gradio API differs from native Kev; the client implements both. Missing local inference never triggers a cloud request.

## Updating

Inspect the checkout before pulling; do not discard unrelated changes. In PowerShell:

```powershell
git -C "$HOME\agent-configs\codex-config" status --short
git -C "$HOME\agent-configs\codex-config" pull --ff-only
if ($LASTEXITCODE -ne 0) { throw "Update failed; preserve local changes and resolve the Git conflict." }
py -3 "$HOME\agent-configs\codex-config\scripts\install_kev.py"
py -3 "$HOME\agent-configs\codex-config\scripts\install_kev.py" --check
```

Re-run installation after pulling so both clients receive the same skill version. Python exit codes: 0 success, 1 check found drift, 2 installer error. Inspect any reported active override. No scheduled sync or background service is installed.

## Recovery and verification

- Restore a specific changed instruction/skill file from its timestamped `.bak` if needed; preserve any newer manual edits.
- To disable only this integration, remove the BEGIN/END CODEX-CONFIG KEV block from the global instruction files (including active override) and remove only the two `kev-decisions` skill directories after saving personal additions.
- Keep the repository copies if you want later reinstall. No model or credentials are removed by those steps.
- Tests: `python3 -B -m unittest discover -s tests -v`.
- Tested and untested deployment states are recorded in `HANDOVER.md`.

## References

- Codex user skills: https://learn.chatgpt.com/docs/build-skills
- Codex global instructions: https://learn.chatgpt.com/docs/agent-configuration/agents-md
- Claude Code skills: https://code.claude.com/docs/en/skills
- Claude global instructions/imports: https://code.claude.com/docs/en/memory
- Kev source and pin: https://github.com/jaredpalmer/kev/tree/badd506d71399f536a09bba7ad5dd663adb104d2
