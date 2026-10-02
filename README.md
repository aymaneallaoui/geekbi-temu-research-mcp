# GeekBI Temu Research MCP

An English-language MCP server for Temu product and market research, backed by [GeekBI](https://www.geekbi.com). Connect it to Claude.ai over HTTPS or run locally over stdio.

| Tool | Purpose |
| --- | --- |
| `temu_goods_search` | Research products, sales, prices, reviews, listing dates, and competition |
| `temu_image_search` | Find visual matches and apply product filters |
| `temu_mall_search` | Compare stores, growth, reputation, and sell-through |
| `temu_category_search` | Discover category IDs, market size, demand, and supply |
| `temu_keyword_search` | Research keyword demand, growth, and competition |
| `temu_review_search` | Analyze a product's reviews, specifications, strengths, and complaints |
| `temu_site_list` | Look up country sites, IDs, and currencies |

The default site is the United States (ID 48). Supply prices are always CNY; sale prices and revenue use the selected site's currency. Tool names and upstream field names are preserved for API compatibility. Documentation, tool schemas, instructions, login, and locally generated errors are English. Upstream data and GeekBI pages can contain Chinese; Claude is instructed to explain them in English without altering raw records.

## Authentication

The remote server has **one configured email/password account and no user signup**. Claude.ai uses an OAuth authorization-code flow with S256 PKCE to open the sign-in page, then sends bearer tokens to `/mcp`. HTTP Basic authentication alone does not implement that connector flow.

OAuth client registration at `/register` registers connector software, **not user accounts**. It accepts only exact callback URLs from `MCP_OAUTH_REDIRECT_URIS`. Both documented Claude callback domains are allowed by default. Passwords use salted scrypt hashes; access tokens last one hour; refresh tokens rotate and last 30 days. OAuth state survives restarts in SQLite. Changing the email, password hash, or public URL invalidates existing authorizations on startup; a restart with the same stored password does not. SDK handlers validate client credentials, PKCE, code expiry, and redirect matching.

Your server login is separate from **GeekBI's own account and subscription**. After connecting, the first data query may return a GeekBI sign-in or purchase link. Open that link, finish the required action, then ask Claude to repeat the same query. This deployment shares one GeekBI account across the configured owner account; it is not a multi-user service.

## Deploy with Docker Compose

Requirements: a Linux host with Docker Compose, a domain pointing to its public IP, and inbound TCP ports 80 and 443 open. Caddy provisions and renews HTTPS certificates. If you publish an AAAA DNS record, its IPv6 address must also reach the host.

1. Clone the repository, copy `.env.example` to `.env`, and set your domain and login email. Protect the file:

   ```sh
   git clone https://github.com/aymaneallaoui/geekbi-temu-research-mcp.git
   cd geekbi-temu-research-mcp
   cp .env.example .env
   chmod 600 .env
   ```

   Edit `.env` using an editor; no password or secret is included in this repository. Leave `MCP_PASSWORD_HASH` unset to let the server generate the owner password (step 3). To choose your own instead, install locally (`uv venv --python 3.12 && uv pip install -r requirements.lock && uv pip install --no-deps -e .`), run `.venv/bin/geekbi-password-hash`, and set the printed hash in `.env` **inside single quotes** so Compose preserves its dollar signs.

2. Start the server:

   ```sh
   docker compose up -d --build
   docker compose ps
   curl --fail https://YOUR_DOMAIN/healthz
   curl -i https://YOUR_DOMAIN/mcp
   ```

   Health returns `{"status":"ok"}`. An unauthenticated MCP request returns **401** and a `WWW-Authenticate` header pointing to resource metadata. This is expected. The service binds only inside Docker; Caddy is the public entry point. Authentication and GeekBI login persist in the `mcp_data` volume. Use a single replica/worker; rate limits and device-login synchronization are process-local. Tool execution is capped at eight concurrent calls, and the CLI limits simultaneous HTTP connections/tasks to 16.

3. If `MCP_PASSWORD_HASH` is unset, the first start generates a random owner password, stores only its scrypt hash in `/data/owner-password.json` (mode 600), and prints the password once:

   ```sh
   docker compose logs mcp | grep "GENERATED OWNER PASSWORD"
   ```

   Save it in a password manager. Later starts reuse the stored hash and print nothing secret. If you lose it or want a new one, rotate it: run `docker compose exec mcp rm /data/owner-password.json`, then `docker compose restart mcp`, and read the new password from the logs. Rotation signs out existing connector sessions.

4. In Claude.ai, open **Settings → Connectors → Add custom connector** (organization owners use Organization settings). Enter `https://YOUR_DOMAIN/mcp`, add it, and complete the sign-in page with your configured email/password. Leave advanced client ID/secret empty; the connector registers its OAuth client automatically. Enable the connector for your conversation and ask Claude to list Temu sites or research a product.

5. If a tool returns a GeekBI action link, complete that separately and retry the same tool. A successful connector login does not grant a GeekBI subscription.

Do not delete the persistent volume during upgrades; it also holds the generated owner password hash. Update with `git pull` and `docker compose up -d --build`. Back up the `mcp_data` volume with the MCP service stopped so SQLite and upstream credentials form a consistent snapshot; protect backups as secrets. To revoke all connector sessions without changing the password, stop the service, delete only `/data/oauth.sqlite3` inside the volume, and start it again (clients must reconnect). Preserve `/data/geekbi-auth.json`.

## Other hosting platforms

Build the Dockerfile, attach a persistent writable volume at `/data`, publish port 8000 behind the platform's HTTPS proxy, and configure:

| Variable | Meaning |
| --- | --- |
| `MCP_PUBLIC_URL` | Exact HTTPS origin, e.g. `https://mcp.example.com`, without `/mcp` |
| `MCP_LOGIN_EMAIL` | The single account's email |
| `MCP_PASSWORD_HASH` | Optional literal `geekbi-password-hash` scrypt hash; no shell quotes in a hosting dashboard. When unset, the server generates a password, stores its hash in `MCP_STATE_DIR/owner-password.json`, and prints the password once to the startup log; delete that file and restart to rotate |
| `MCP_STATE_DIR` | Writable persistent directory; defaults to `/data` |
| `MCP_OAUTH_REDIRECT_URIS` | Comma-separated exact callbacks; defaults to Claude's two callbacks |
| `GEEKBI_REQUEST_TIMEOUT` | Upstream timeout in seconds, greater than 0 and at most 300; default 30 |
| `GEEKBI_BASE_URL` | Optional upstream API override; default `https://openapi.geekbi.com`; remote mode requires HTTPS |
| `GEEKBI_AUTH_PATH` | Upstream credential path in stdio mode; remote mode uses `MCP_STATE_DIR/geekbi-auth.json` |

Remote startup fails if account settings are missing or invalid, or if a stored `owner-password.json` is unreadable. HTTP public URLs are accepted only on loopback for development. The health endpoint is `/healthz`; OAuth discovery is `/.well-known/oauth-authorization-server` and `/.well-known/oauth-protected-resource/mcp`. Avoid adding another proxy login in front of these routes: Claude must reach discovery, registration, and OAuth endpoints.

## Local stdio

After installation, configure an MCP-compatible desktop client with an absolute executable path:

```json
{
  "mcpServers": {
    "geekbi-temu-research": {
      "command": "/absolute/path/geekbi-temu-research-mcp/.venv/bin/geekbi-temu-mcp"
    }
  }
}
```

Stdio uses GeekBI's existing device login and does not require the remote owner account. Local image paths are supported only in stdio mode. Remote images accept public HTTP(S) URLs on ports 80/443, Data URIs, or `base64:` data up to 10 MB. Private/nonpublic addresses, redirects to private networks, and local files are blocked remotely. Remote requests resolve and pin the validated public IP and verify TLS certificates.

## Development and verification

Python 3.12 is the tested deployment runtime. `requirements.lock` pins production dependencies for that runtime; `pyproject.toml` retains library version ranges.

```sh
uv pip install -e '.[dev]'
.venv/bin/pytest -q
uv pip compile --python-version 3.12 pyproject.toml -o requirements.lock
```

Tests cover tool schemas, stdio discovery, query serialization, validation, images, and the remote login/OAuth/MCP flow. See [REVIEW.md](REVIEW.md) for fixes and validation limits. Do a live Claude.ai connection after deployment; local protocol tests cannot verify public DNS, TLS, hosting configuration, or your GeekBI entitlement.

## Documentation consulted

- [Claude custom remote connectors](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp)
- [Building Claude MCP connectors and callback URLs](https://support.anthropic.com/en/articles/11503834-building-custom-connectors-via-remote-mcp-servers)
- [MCP authorization, PKCE, resource metadata, and audience validation](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization)
- [Official Python SDK deployment guidance](https://py.sdk.modelcontextprotocol.io/run/deploy/)

- [Caddy request body limits](https://caddyserver.com/docs/caddyfile/directives/request_body)
- [Docker Compose environment quoting](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/)
