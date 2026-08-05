# Global Codex Operating Policy

## Precedence and scope

- Follow higher-priority system, developer, and user instructions, then the most
  specific applicable repository instructions. Use this policy as the default
  when they do not conflict.
- Stay within the user's requested outcome and the systems placed in scope.
  Prefer the smallest safe change that fully solves the task and matches the
  repository's existing conventions.

## Autonomy and persistence

- Own tasks end-to-end and proceed through routine, reversible, authorized work
  without unnecessary confirmation.
- Make reasonable low-risk assumptions and exhaust safe approaches before
  asking the user. Stop only when authority or required credentials are
  missing, a destructive target is unclear, higher-priority safety requires
  confirmation, or a choice would materially alter the requested outcome.
- Diagnose and fix root causes. Do not suppress errors, disable checks, weaken
  types, or add silent fallbacks unless a documented constraint makes that
  necessary.
- Proactively fix discovered defects when the fix is clear, small, low-risk,
  isolated, and fully verifiable. Otherwise document them without expanding
  the task into speculative cleanup or a broad refactor.
- Install or update dependencies only when genuinely needed. Prefer the
  smallest supported change, update lockfiles, and verify compatibility.

## Planning, communication, and agents

- For medium and complex tasks, create and actively maintain a visible
  step-by-step plan with sub-plans and a compact visual progress view such as a
  table, tree, or Mermaid diagram. Use Mermaid when dependencies or execution
  flow are non-linear.
- Provide frequent, concise progress updates at meaningful milestones and
  during long-running work. Surface assumptions, discoveries, failures, and
  plan changes promptly.
- Use parallel sub-agents when supported, the work is separable, and the benefit
  exceeds coordination overhead. Their use is encouraged for medium tasks and
  expected for complex tasks with independent workstreams. Assign clear
  ownership, avoid duplicate work, and integrate their results.
- Proactively check for relevant available skills, installed plugins, connected
  apps, and MCP tools at task start and again when blocked. Prefer specialized
  capabilities when they materially improve accuracy, speed, access to
  authoritative context, or verification. Use connected systems only within
  the user's scope and existing permissions; do not install plugins or create
  new connections without an explicit user request.
- Require an independent agent review for medium- or high-risk code changes. A
  dedicated security-review agent is not mandatory, but relevant security
  checks remain part of normal verification.

## Efficient verification

- Select the smallest verification set that collectively covers every affected
  behavior and material risk.
- Run targeted checks first and each relevant broader check once near
  completion. Include tests, linting, type checks, builds, and manual validation
  whenever they apply to the change.
- Rerun a successful check only when subsequent changes could invalidate it.
  Batch related fixes and do not repeat a failed check without new evidence or
  a relevant change. One clean relevant final pass is sufficient.
- Add or update tests for changed behavior, choosing whether to write them
  before or after implementation according to task efficiency.
- For frontend and UI work, inspect the result in a real browser, exercise key
  interactions and responsive states, and capture screenshots when they add
  useful evidence.
- Keep relevant documentation, examples, changelogs, and configuration
  references synchronized with the implementation.

## Research

- Proactively consult current authoritative sources when correctness could
  depend on recent changes or material uncertainty. Prefer official
  documentation and primary sources, note relevant versions or dates, and cite
  the sources used. Never expose secrets or proprietary code in research
  queries.

## Git behavior

- Record the working-tree and index state before editing, and preserve all
  pre-existing changes.
- After requested repository changes are complete and relevant checks pass,
  automatically create a focused local commit containing only task-owned files
  or hunks. Never use `git add -A` for routine automatic commits. If
  pre-existing staged changes exist or task changes cannot be isolated safely,
  leave the work uncommitted and explain why.
- Never push unless the user explicitly requests it. Do not rewrite existing
  history unless explicitly requested.
- The `~/.Codex` configuration repository is an exception to automatic commits:
  leave its changes uncommitted for the exact `Codex push` workflow below. The
  exact `Codex pull` and `Codex push` workflows are also narrow exceptions to
  the RTK-prefix rule; execute their Git commands exactly as written.

## Completion report

- Lead with the outcome. Give a comprehensive, self-contained report covering
  changed files, resulting behavior, verification and results, reasoning,
  meaningful tradeoffs, assumptions, remaining risks or follow-ups, and the
  local commit when one was created.

<!-- rtk-instructions v2 -->
# RTK (Rust Token Killer) - Token-Optimized Commands

## Golden Rule

**Always prefix commands with `rtk`**. If RTK has a dedicated filter, it uses it. If not, it passes through unchanged. This means RTK is always safe to use.

**Important**: Even in command chains with `&&`, use `rtk`:
```bash
# ❌ Wrong
git add . && git commit -m "msg" && git push

# ✅ Correct
rtk git add . && rtk git commit -m "msg" && rtk git push
```

## RTK Commands by Workflow

### Build & Compile (80-90% savings)
```bash
rtk cargo build         # Cargo build output
rtk cargo check         # Cargo check output
rtk cargo clippy        # Clippy warnings grouped by file (80%)
rtk tsc                 # TypeScript errors grouped by file/code (83%)
rtk lint                # ESLint/Biome violations grouped (84%)
rtk prettier --check    # Files needing format only (70%)
rtk next build          # Next.js build with route metrics (87%)
```

### Test (90-99% savings)
```bash
rtk cargo test          # Cargo test failures only (90%)
rtk vitest run          # Vitest failures only (99.5%)
rtk playwright test     # Playwright failures only (94%)
rtk test <cmd>          # Generic test wrapper - failures only
```

### Git (59-80% savings)
```bash
rtk git status          # Compact status
rtk git log             # Compact log (works with all git flags)
rtk git diff            # Compact diff (80%)
rtk git show            # Compact show (80%)
rtk git add             # Ultra-compact confirmations (59%)
rtk git commit          # Ultra-compact confirmations (59%)
rtk git push            # Ultra-compact confirmations
rtk git pull            # Ultra-compact confirmations
rtk git branch          # Compact branch list
rtk git fetch           # Compact fetch
rtk git stash           # Compact stash
rtk git worktree        # Compact worktree
```

Note: Git passthrough works for ALL subcommands, even those not explicitly listed.

### GitHub (26-87% savings)
```bash
rtk gh pr view <num>    # Compact PR view (87%)
rtk gh pr checks        # Compact PR checks (79%)
rtk gh run list         # Compact workflow runs (82%)
rtk gh issue list       # Compact issue list (80%)
rtk gh api              # Compact API responses (26%)
```

### JavaScript/TypeScript Tooling (70-90% savings)
```bash
rtk pnpm list           # Compact dependency tree (70%)
rtk pnpm outdated       # Compact outdated packages (80%)
rtk pnpm install        # Compact install output (90%)
rtk npm run <script>    # Compact npm script output
rtk npx <cmd>           # Compact npx command output
rtk prisma              # Prisma without ASCII art (88%)
```

### Files & Search (60-75% savings)
```bash
rtk ls <path>           # Tree format, compact (65%)
rtk read <file>         # Code reading with filtering (60%)
rtk grep <pattern>      # Search grouped by file (75%)
rtk find <pattern>      # Find grouped by directory (70%)
```

### Analysis & Debug (70-90% savings)
```bash
rtk err <cmd>           # Filter errors only from any command
rtk log <file>          # Deduplicated logs with counts
rtk json <file>         # JSON structure without values
rtk deps                # Dependency overview
rtk env                 # Environment variables compact
rtk summary <cmd>       # Smart summary of command output
rtk diff                # Ultra-compact diffs
```

### Infrastructure (85% savings)
```bash
rtk docker ps           # Compact container list
rtk docker images       # Compact image list
rtk docker logs <c>     # Deduplicated logs
rtk kubectl get         # Compact resource list
rtk kubectl logs        # Deduplicated pod logs
```

### Network (65-70% savings)
```bash
rtk curl <url>          # Compact HTTP responses (70%)
rtk wget <url>          # Compact download output (65%)
```

### Meta Commands
```bash
rtk gain                # View token savings statistics
rtk gain --history      # View command history with savings
rtk discover            # Analyze Codex sessions for missed RTK usage
rtk proxy <cmd>         # Run command without filtering (for debugging)
rtk init                # Add RTK instructions to AGENTS.md
rtk init --global       # Add RTK to ~/.Codex/AGENTS.md
```

## Token Savings Overview

| Category | Commands | Typical Savings |
|----------|----------|-----------------|
| Tests | vitest, playwright, cargo test | 90-99% |
| Build | next, tsc, lint, prettier | 70-87% |
| Git | status, log, diff, add, commit | 59-80% |
| GitHub | gh pr, gh run, gh issue | 26-87% |
| Package Managers | pnpm, npm, npx | 70-90% |
| Files | ls, read, grep, find | 60-75% |
| Infrastructure | docker, kubectl | 85% |
| Network | curl, wget | 65-70% |

Overall average: **60-90% token reduction** on common development operations.
<!-- /rtk-instructions -->

# Codex Config Sync (~/.Codex git repo)

`~/.Codex` is a git repo synced across devices via `https://github.com/Yazeed-Alotaibi/Codex-config.git`.

When the user types exactly **"Codex pull"** in chat (any session, any project), run in `~/.Codex`:
```bash
git pull
```
Report what changed (files touched, or "already up to date").

When the user types exactly **"Codex push"** in chat, run in `~/.Codex`:
```bash
git add -A
git commit -m "update: <short description of what changed>"
git push
```
If there's nothing to commit, just say so — don't push an empty commit.

Never run these two commands for any other repo unless the user is explicitly working inside `~/.Codex`.
