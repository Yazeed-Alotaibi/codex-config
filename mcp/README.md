# MCP servers

`config.toml` is gitignored in this repo (it holds credentials), so MCP server
entries that contain no secrets are tracked in [`servers.toml`](servers.toml)
and applied to `~/.codex/config.toml` per machine.

## Servers

| Name | URL | Transport | Auth |
| --- | --- | --- | --- |
| `roicai` | `https://mcp.roic.ai/mcp` | streamable HTTP | OAuth — `codex mcp login roicai` |

**ROIC.ai** exposes 36 read-only tools over public-company financial data:
ticker search, company profiles and news, income statement / balance sheet /
cash flow, profitability–credit–liquidity ratios, valuation multiples and
enterprise value, historical prices and splits, forex, earnings calendar and
call transcripts.

## Apply on a machine

```bash
codex mcp add roicai --url https://mcp.roic.ai/mcp
codex mcp login roicai   # opens a browser for the ROIC.ai OAuth consent
codex mcp list           # verify it is registered and enabled
```

Or paste the matching block from `servers.toml` into `~/.codex/config.toml` and
run only the `login` step.

## Notes

- No token is stored in `config.toml`. Codex discovers the OAuth flow from the
  server's `/.well-known/oauth-protected-resource` metadata (authorization
  server `https://www.roic.ai`, dynamic client registration + PKCE) and keeps
  the resulting credentials in `~/.codex/auth.json`, which is gitignored.
  Adding `auth = "oauth"` to the server entry makes that explicit if a build
  ever fails to auto-discover it.
- On Codex builds that predate the native RMCP client, HTTP servers are ignored
  unless `experimental_use_rmcp_client = true` is set at the top level of
  `config.toml`. Not needed on current builds.
- ROIC.ai also ships a self-hosted MCP server that authenticates with a REST
  API key instead of OAuth — use that only if the hosted OAuth flow is
  unavailable, and keep the key in an env var referenced by
  `bearer_token_env_var`.
- Never commit `config.toml`, `auth.json`, or any token.
