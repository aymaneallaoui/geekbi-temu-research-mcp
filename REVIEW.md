# Code review and deployment validation

Reviewed the original checkout and the English/remote-server changes on 2026-10-01.

## Findings addressed

| Finding | Fix |
| --- | --- |
| Existing HTTP mode exposed tools without owner authentication | HTTP startup now requires a configured email, scrypt password hash, and public URL. Added SDK-based OAuth authorization-code/PKCE flow and protected bearer-token transport. No user signup. |
| HTTP Basic alone does not implement Claude.ai's OAuth connector flow | Added discovery, restricted OAuth client registration, sign-in/consent, code exchange, refresh rotation, revocation, and resource validation. |
| Remote image inputs could read server files or access private services/cloud metadata | Local files are disabled remotely. HTTP(S) downloads validate all DNS results, pin a public IP, restrict ports, recheck redirects, disable environment proxies for images, and verify TLS against the original hostname. Multicast/reserved/private addresses are rejected. |
| Content-Type could label arbitrary bytes as an image | Require a recognized image signature; a supplied image MIME type is insufficient. |
| Local image size check had an unbounded read after stat | Read at most 10 MB + 1 and revalidate. |
| Upstream authentication headers could follow a redirect to another origin | Reject redirects that change scheme, hostname, or effective port; this also rejects HTTPS-to-HTTP downgrade. Remote upstream API configuration requires HTTPS. |
| Upstream responses were read without a size limit | Cap successful JSON responses at 20 MB and error bodies at 1 MB. HTTP/MCP body limit is 15 MB; image payload limit remains 10 MB. |
| Nonfinite timeout/filter values could bypass validation | Reject NaN/infinity and enforce timeout range. |
| Comparing a naive datetime with an aware datetime raised an unhandled TypeError | Return a Pydantic validation error when range bounds have inconsistent timezone awareness. |
| Concurrent unauthenticated requests could overwrite the shared device-login challenge | Serialize the device-login handshake; allow authenticated research requests to execute concurrently. |
| Generic SDK worker concurrency could permit excessive simultaneous upstream work | Added an explicit eight-call limiter. The SDK already offloaded synchronous tools; this change bounds resource usage rather than fixing an existing event-loop blocking defect. CLI also limits HTTP concurrency to 16. |
| Remote state would be lost on ephemeral deployments | Added persistent SQLite connector OAuth state and a persistent GeekBI auth file under the configured state directory. Owner credential/public-URL changes invalidate connector authorizations. Tokens/codes are indexed by hashes, not stored as raw bearer strings. |
| Login lacked abuse/CSRF protections | Added bounded request rates, login-attempt limits, browser cookie/form CSRF binding, origin checks, password hashing off the event loop, exact callback restrictions, and response security headers. |
| Original interface instructed the assistant to answer exclusively in Chinese | Translated README, package description, CLI, tool descriptions, input schemas, instructions, and locally generated errors. Preserve upstream field names and Chinese country aliases. Raw upstream messages/reviews/names remain intact; the assistant translates them for presentation. |

## Deployment files

- `Dockerfile`: Python 3.12, pinned production dependencies, non-root account, health check.
- `compose.yaml` / `Caddyfile`: HTTPS proxy, internal MCP service, durable state volumes, resource limits, read-only application filesystem.
- `.env.example`: owner account/domain settings without credentials.
- `requirements.lock`: resolved production dependency versions for Python 3.12.
- `.github/workflows/test.yml`: Python tests and Docker image build on pushes/PRs.
- `README.md`: setup, password hash generation, Claude.ai connection, GeekBI device login, upgrades, and persistent-state guidance.

## Validation performed

- **39 tests passed**, plus six unittest subtests. Coverage includes all seven tools and their schemas, query serialization, range validation, stdio protocol discovery, login/CSRF/invalid credentials, OAuth PKCE and one-time-code replay protection, foreign resource rejection, refresh rotation/replay rejection, token persistence/revocation, credential-change invalidation, authenticated HTTP tool discovery and calls, image restrictions, and GeekBI device login/authenticated retry.
- Python wheel and source distribution built successfully with `uv build --offline`.
- `docker compose --env-file .env.example config --quiet` succeeded.
- CLI help is English; missing owner/public-URL settings prevent remote startup.
- `git diff --check` and Python compilation passed.

The execution sandbox blocks asyncio's socket-based wakeup. Tests ran with a temporary selector heartbeat and propagation of that helper to the SDK's filtered stdio subprocess environment. This helper lives outside the repository and does not modify deployment behavior. Its early import causes one harmless pytest assertion-rewrite warning. The same suite is configured to run normally in GitHub Actions.

## Remaining external checks and limits

Docker image execution/Caddy certificate issuance were not tested here because access to the Docker daemon socket is denied. Only Compose configuration and Python packaging were validated locally. GitHub Actions has been added but has not run. No public endpoint has been deployed and no changes have been pushed to GitHub.

A live Claude.ai connection and real GeekBI data queries require a reachable public HTTPS domain and your GeekBI account/entitlement. Protocol-level HTTP tests use an in-process ASGI client and a mocked upstream; they do not establish real API availability, DNS/TLS behavior, image download throughput, or production latency.

This is a single-owner deployment: GeekBI credentials are shared, rate limits/device-login locking are process-local, and OAuth state uses one SQLite database. Run one worker/replica with a durable volume. Scale-out would require shared rate limiting and device-login coordination. Upstream requests still use separate urllib connections, so there is no connection pool or measured claim of reduced real API latency. Increasing parallelism blindly would increase memory and upstream load.
