# Test & Validation Evidence

## 1. Automated tests (local)

Command: `pytest -v --cov=app`. Full output: [`evidence/pytest-report.txt`](../evidence/pytest-report.txt)

**Result (2026-10-15): 35 passed, 0 failed. Statement coverage 97%.**

| Area | Tests | What is proven |
|---|---|---|
| Health | 4 | Liveness, readiness checks the DB, request-ID propagation and generation |
| Products | 17 | CRUD, API key required for writes, duplicate SKU → 409, 6 invalid-input cases → 422, low-stock filter, pagination bounds, FK-protected delete → 409 |
| Orders | 8 | Stock decrement + totals, price captured at order time, **all-or-nothing oversell rejection**, unknown product → 404, validation (empty, qty 0, bad email, duplicate lines), auth, ordering |
| Config / secrets | 4 | Secrets loaded from (moto-mocked) Secrets Manager, password never in URL, rotation picked up on refresh, non-local env refuses to start without a key |
| DB rotation | 2 | Connection retries once with refreshed credentials after an auth failure, and gives up after a second failure |

Lines not covered: SQLite-only branches in `get_engine`, the DB-down branch of readiness, and the
generic-500 path. The last two are exercised manually in §3.

## 2. Infrastructure validation

| Check | Result |
|---|---|
| `cfn-lint infra/template.yaml` | ✅ 0 errors, 0 warnings (after D15: removed the invalid `EngineVersion: "16"`) |

## 3. Local end-to-end smoke test

`python scripts/smoke_test.py --base-url http://127.0.0.1:8000 --api-key local-dev-key`.
Report: `evidence/smoke-20261015T070710Z.json`

**13 / 13 checks passed:** liveness, readiness, 401 without key, 422 invalid input, create ×2, duplicate SKU 409,
place order, oversell 409, read order, stock 5 → 3, low-stock report, unknown route 404.

## 4. Cloud validation (fill in after `deploy.ps1`)

| # | Evidence to capture | Result / file |
|---|---|---|
| C1 | `deploy.ps1` output table (stack outputs) | `evidence/c1-stack-outputs.png` |
| C2 | `smoke_test.py` against the Elastic IP: 13/13 | `evidence/smoke-<timestamp>.json` + screenshot |
| C3 | Swagger UI at `http://<ip>/docs` | screenshot |
| C4 | CloudWatch dashboard with traffic from C2 | screenshot |
| C5 | Logs Insights query tracing one `request_id` | screenshot |
| C6 | Alarm test email (`set-alarm-state`) | screenshot |
| C7 | IAM role policy (shows only 2 secrets + 1 log group) | screenshot |
| C8 | RDS: "Publicly accessible: No", encryption, backup retention (1 day, free plan), engine version | screenshot |
| C9 | `curl http://<ip>:5432` / `nc` from laptop **fails**, i.e. the DB is not reachable from the internet | screenshot |
| C10 | Restore drill: start/end time, **measured RTO = ___ min** | runbook §Restore drill |
| C11 | Readiness returns **503** when the DB is stopped (`aws rds stop-db-instance`), then recovers | screenshot |
| C12 | Budget visible in Billing → Budgets | screenshot |

## 5. Known issues disclosed

- HTTP only (no TLS). See architecture §Limitations.
- `low_stock` filtering and pagination are not indexed for very large catalogues. That's fine at internship scale.
