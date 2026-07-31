# Codex Config Sync (~/.codex git repo)

`~/.codex` is a git repo synced across devices via
`https://github.com/Yazeed-Alotaibi/codex-config.git`.

When I type exactly **"codex pull"** in chat (any session, any project), run
in `~/.codex`:

```bash
git pull
```

Report what changed (files touched, or "already up to date").

The exact phrase **"codex pull"** is authorization to pull immediately. Do not
ask for a separate confirmation.

When I type exactly **"codex push"** in chat, run in `~/.codex`:

```bash
git add -A
git commit -m "update: <short description of what changed>"
git push
```

If there's nothing to commit, just say so — don't push an empty commit.

The exact phrase **"codex push"** is authorization to stage, commit, and push
immediately. Do not ask for a separate confirmation.

Never run these two commands for any other repo unless I'm explicitly
working inside `~/.codex`.
