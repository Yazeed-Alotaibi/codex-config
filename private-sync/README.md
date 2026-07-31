# Encrypted Codex private-state sync

This directory stores an `age`-encrypted snapshot of sensitive Codex state.
Git never receives the plaintext credentials, sessions, attachments, or
databases. The encrypted output is split into 45 MiB parts so each tracked file
stays below GitHub's per-file limit.

The private decryption identity is intentionally outside this repository:

```text
~/.codex-sync/age-identity.txt
```

Transfer that identity to another device through a separate secure channel,
such as an encrypted password manager or an offline encrypted drive. Never add
it to this repository or send it in chat.

## Export a new snapshot

From `~/.codex`, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\private-sync\Export-CodexPrivateSnapshot.ps1
```

The export uses SQLite's backup API for consistent database copies, encrypts
the full snapshot, splits the ciphertext, and deletes the temporary plaintext
staging directory. Then use `codex push` to review, commit, and publish the new
encrypted parts.

Because `age` encryption is randomized, every export replaces the full
ciphertext and increases Git history by roughly the snapshot size. Export only
when private state genuinely needs to move to another device.

## Restore on another Windows device

1. Install `age`:

   ```powershell
   winget install --id FiloSottile.age --exact
   ```

2. Securely place the same private identity at:

   ```text
   ~/.codex-sync/age-identity.txt
   ```

3. Run `codex pull`, then close Codex completely.

4. From a separate PowerShell window in `~/.codex`, run:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\private-sync\Import-CodexPrivateSnapshot.ps1
   ```

The import verifies every encrypted part before decrypting and asks for
confirmation before overwriting matching private-state files. It merges
directories and does not delete unrelated local files.
