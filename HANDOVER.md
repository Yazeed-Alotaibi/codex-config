# Kev integration checkpoint

- Objective: share Kev instructions and a reusable local skill through Yazeed-Alotaibi/codex-config; install for Codex and Claude Code on each computer.
- Authorized: implement, validate and publish this scoped repository change. No user-device access is available in this session.
- Lead: Codex. Claims: LOCKS.md. Do not send messages to third parties.
- Inspected remote main: c7e6aecc20d596a37ab842cd1bbdbad5f0d319d9; base tree beaee9c02eef4e48fd7df488c349a6b8a4e05ee2. No existing AGENTS.md, CLAUDE.md, sync scripts or handover files in this snapshot.
- Access: authenticated GitHub connector read works. Shell git clone authentication is unavailable; use GitHub tree/commit/ref APIs and preserve the complete remote base tree. Current directory is a candidate-file workspace, not a full checkout.
- Plan: (1) verify Kev local/hosted interfaces; (2) add shared skill, global trigger and idempotent installer; (3) test installation preservation and client failures; (4) publish atomic non-force update; (5) verify remote files and report per-device rollout still pending.
- Local candidate files: /workspace/scratch/5f094c0f581c/codex-config-kev.
- Implemented: root AGENTS.md Kev routing block, CLAUDE.md import, portable kev-decisions skill with native/hosted stdlib client, idempotent per-computer installer and setup/recovery documentation.
- Verified candidate on Linux: `python3 -B -m unittest discover -s tests -v` passed all 41 tests; skill-creator quick_validate passed; API JSON examples parsed; actual bundle passed isolated dry-run/install/check/unchanged-reinstall. Independent final review approved with no material blockers. Windows execution remains untested.
- Live service verification: hosted schema succeeded; bundled client processed only the synthetic supplier example with Kev-0.8B and calibration enabled. Result choice: delivery_delay (0.9317 returned probability; not an accuracy benchmark). No user documents were uploaded.
- Local model execution: upstream source/API inspected at badd506d71399f536a09bba7ad5dd663adb104d2. Native HTTP contract tested against a local fake server only; real local inference, CUDA performance and user-PC installs remain unverified. No weights downloaded; no user computers modified.
- Scope boundary: model execution must be distinguished from local skill installation. No implicit cloud fallback and no secrets in version control.
- Published and verified: implementation commit 094894595f624fbbeb5488682b7f3e2eef6ce987 is on main. The non-force update preserved all 280 pre-existing remote files; all 15 added file blobs matched the tested local candidate byte-for-byte. This follow-up checkpoint records that completed publication. No user-device deployment is implied.
- Next on each actual device: follow docs/kev-setup.md; install global skill/instructions, run `scripts/install_kev.py --check`, start local runtime from the pinned-source guide, verify `/v1/models` and one synthetic request, then record that device's verified status separately.
- Recovery: per-device installer makes timestamped .bak backups of changed existing files; see docs/kev-setup.md. Repository rollback must be scoped to this commit and preserve later/concurrent changes; never force-reset a user checkout.


# Cloud global setup checkpoint — 2026-11-05

- Objective: user requested cloning codex-config and making the setup global. Current scope is the ChatGPT cloud environment and account skill directory; no PC or VPS installation is implied.
- Lead: Codex/root; no delegated agents or outstanding coordination claims.
- Source cloned successfully: main at 5db4a4d214256d441ca2f92a6b8dd6d56b25f30f. Full checkout: /workspace/scratch/a8fe38070b2d/codex-config; source files unchanged at this milestone.
- Global instructions: preserved existing /root/.codex/AGENTS.md preferences, backed up the file, appended the repository Kev block and cloud skill-discovery note. This local file does not establish account-wide Custom Instructions persistence.
- Personal skills: installation in progress through the account skill directory. Academy guide, algorithmic art, brand guidelines, canvas design and Claude API saved and remotely verified; discernment-nudge saved, verification pending. Remaining 10 skills pending.
- Validation: bundled skill validator passed each saved skill. Claude API trigger description shortened in the installed copy to fit validation limits; source repository copy unchanged. Runtime functionality and external dependencies have not been tested.
- A transient HTTP 500 occurred during skill verification; retry succeeded. Continue installation with /workspace/scratch/a8fe38070b2d/install_repo_skills.py and inspect skill-install-results.json. Verify exact installed skill names and resources before claiming completion.
- Existing system skills retained; archived .system copies and Windows-specific approval rules are not imported. No config.toml, MCP definitions, or plugin manifest exists in this repository snapshot. Kev runtime and service authentication remain unverified.
- Recovery: restore the timestamped AGENTS.md backup to undo local instruction changes; disable only newly installed personal skills to undo their installation. Do not reset unrelated setup or force-push.
