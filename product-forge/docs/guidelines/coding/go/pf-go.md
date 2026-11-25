# PF-SB Go Coding Guidelines

**Scope:** all Go in the Product Forge self-build / PF-SB data plane and services.
**Status:** required for every Go item. Cite this file in the design `code_guidelines`.
**Sources:** Effective Go, Go Code Review Comments, Google Go Style, Go security guidance,
`database/sql`/pgx transaction guidance, and the Go memory model (links below).

## 1. Required toolchain checks

Run from the changed Go module:

```sh
gofmt -s -w .
go vet ./...
go test ./...
go test -race ./...
go build ./...
go mod tidy
go mod verify
```

When available in the environment:

```sh
goimports -w .
staticcheck ./...
golangci-lint run
govulncheck ./...
```

Do not commit generated `go.sum` churn without a real dependency change. Do not disable
`go vet` or race checks to make a test pass.

## 2. Package and module structure

- PF uses one module per `go/<component>` with local `replace` directives. Keep new code in
  the owning module.
- Keep `main` thin: configuration, dependency construction, serving, signal handling.
- Put domain/store logic behind the owning package; services depend on ports, not pgx.
- Reuse `productforge/datastore` and the existing `productforge/store` boundaries.
- No provider-specific imports in the service layer.
- Prefer small interfaces declared by the consumer; do not create broad “god” interfaces.
- Avoid package-level mutable state; pass dependencies explicitly.

## 3. Naming and clarity

- Package names are short, lowercase, and not repeated in selectors.
- Use `MixedCaps`, not underscores.
- Comment exported declarations and explain **why**, not what the code already says.
- Avoid stutter, unnecessary getters, and generic names (`Manager`, `Helper`, `Util`).
- Keep functions focused; extract only when it improves clarity or testability.
- Do not add comments that merely restate code.

## 4. Errors

- Handle every error; never ignore with `_` unless the reason is explicit and safe.
- Wrap with context: `fmt.Errorf("load backlog: %w", err)`.
- Use `errors.Is` / `errors.As` for sentinel and typed errors.
- Do not use `panic` for request, validation, DB, or configuration failures.
- Do not return raw DB/driver errors to clients; map to stable HTTP/error envelopes.
- Keep error messages free of secrets, SQL text, tokens, and tenant data.
- Fail closed: unknown, missing, timeout, and unreadable states are errors, not defaults.
- Validate caller input at the boundary: empty IDs, sizes, overflow, negative values,
  traversal, and oversized payloads.

## 5. Context, concurrency, and lifecycle

- `context.Context` is the first parameter; never store it in a struct.
- Propagate request context into DB queries, HTTP calls, and background work.
- Apply bounded timeouts to DB/HTTP calls; do not use `context.Background()` on a request path.
- Every goroutine must have an owner, a stop condition, and a way to wait.
- Never start unbounded goroutines per request without a cap.
- Protect shared state with `sync`/channels; run `go test -race`.
- Use `errgroup` only when its cancellation/error semantics fit.
- Handle `SIGTERM` with graceful shutdown and bounded drain.
- Avoid `time.Sleep` in request paths; use context cancellation or timers.
- Close rows, bodies, files, and idle connections; check `rows.Err()` after iteration.

## 6. HTTP services

- Use `http.Server` timeouts: `ReadHeaderTimeout`, `ReadTimeout`, `WriteTimeout`, `IdleTimeout`.
- Set request body limits; reject oversized input before decoding.
- Authenticate/authorize at the boundary, not in prompt text or comments.
- Return stable status codes and error envelopes; do not leak internal errors.
- Set rate/concurrency limits for public or expensive endpoints.
- Use `http.MethodGet`-style constants and explicit method checks.
- Admin-only routes must be explicitly registered and reviewed.

## 7. Database access

- Use parameterized queries only; never concatenate SQL with input.
- Use the `datastore` transaction boundary; do not run `BEGIN`/`COMMIT` as raw SQL.
- If a transaction fails, roll back; do not reuse the failed transaction.
- Respect RLS: `store.BindTenant` must set `app.tenant_id` before tenant tables.
- Never use `pf_admin`/`BYPASSRLS` on the runtime path.
- Use the existing context/timeout; do not introduce a second pool in a service.
- Close rows and check `rows.Err()`; return scan/iteration errors.
- For pgx, remember context generally governs `Begin`; do not assume auto-rollback on cancel.
- Migrations: up and down, idempotent, expand/contract, `lock_timeout`, no editing applied
  migrations. Test interrupted re-apply where relevant.
- Keep allocation/ID writes in one authority; no local counter fallback.

## 8. Security

- Validate all untrusted input at the boundary.
- Use `crypto/rand` for security randomness; never `math/rand` for tokens/keys.
- Do not log secrets, tokens, DSNs, PII, or full request bodies.
- Use least-privilege DB roles; no superuser/BYPASSRLS inheritance.
- Guard path joins against traversal and absolute paths.
- Use constant-time comparison for bearer/admin tokens.
- Run `govulncheck ./...` when available; track dependency vulnerabilities.
- TLS and auth are boundary concerns; do not implement ad-hoc crypto.

## 9. Observability

- Use structured logs with stable fields; never interpolate secrets/PII.
- Include request/correlation ID where the service already supports it.
- Emit metrics for success/error/latency on new runtime paths.
- Log actionable failure causes at the boundary; keep client responses fixed/safe.
- Distinguish auth, validation, dependency, and timeout failures.
- Add startup/readiness signals for dependencies where operationally relevant.

## 10. Testing

- Prefer table-driven tests with named subtests.
- Test the real entrypoint/adapter for runtime capabilities; fakes only for isolated units.
- Add negative tests: auth, missing tenant, missing schema/row, timeout, overflow, concurrency.
- Use `t.Helper()` for helpers.
- Integration tests must skip cleanly when the required DSN is absent.
- Do not use `assert.True(true)` or tests that cannot fail.
- Run `go test -race` for concurrent code.
- A runtime capability needs red evidence before implementation and green evidence after.

## 11. Performance

- Bound loops, queries, payloads, and allocations.
- Avoid N+1 queries; index predicates used by tenant/status/list paths.
- Measure before optimizing; use benchmarks/`pprof` and `EXPLAIN (ANALYZE, BUFFERS)`.
- Avoid holding locks across network calls.
- Do not add a cache or second source of truth without an owner and invalidation design.

## 12. Dependencies and compatibility

- Prefer the standard library and existing PF packages.
- Add a dependency only with a clear need, license check, and `go mod tidy`.
- Keep public behavior backward-compatible unless the design approves a change.
- Deprecate explicitly; do not silently change response/error semantics.
- No placeholders, stubs, dead code, unused imports, or “temporary” paths in shipped code.

## 13. Go review checklist

- Is the runtime entrypoint wired to the real mux/handler?
- Is every error handled, wrapped, and mapped?
- Are context, timeouts, cancellation, and shutdown correct?
- Are goroutines bounded and waitable?
- Are rows/bodies/files closed and checked?
- Is SQL parameterized and tenant/RLS scoped?
- Are auth, tenant, overflow, missing-row/schema, and timeout paths tested?
- Is the code race-tested and gofmt/go-vet clean?
- Are logs/metrics safe and actionable?
- Did the change remove unused imports/variables/dead code?
- Is the design’s exact call chain present, not just a helper?

## Sources

- Effective Go: https://go.dev/doc/effective_go
- Go Code Review Comments: https://go.dev/wiki/CodeReviewComments
- Google Go Style: https://google.github.io/styleguide/go/
- Go security best practices: https://go.dev/doc/security/best-practices
- Go vulnerability management: https://go.dev/doc/tutorial/govulncheck
- Go database transactions: https://go.dev/doc/database/execute-transactions
- Go database cancellation: https://go.dev/doc/database/cancel-operations
- `database/sql`: https://pkg.go.dev/database/sql
- pgx v5: https://pkg.go.dev/github.com/jackc/pgx/v5
- Go modules layout: https://go.dev/doc/modules/layout
- Go comments: https://go.dev/doc/comment
- Go memory model: https://go.dev/ref/mem
