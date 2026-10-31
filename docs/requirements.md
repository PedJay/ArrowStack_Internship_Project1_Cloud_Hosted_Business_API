# Requirements — BrightMart Inventory & Orders API

## 1. Stakeholders & problem

| Role | Need |
|---|---|
| **Store-operations manager** (primary) | Knows what is low on stock before it runs out; no overselling |
| Order-desk staff | Places orders quickly and gets a clear error when an item is unavailable |
| Finance | Order totals use the price *at the time of the order*, even if the price changes later |
| IT / cloud engineer (me) | A secure, observable, recoverable and cheap deployment |

**Problem statement.** BrightMart (a fictional business with simulated data) tracks stock in spreadsheets. Two
staff members can sell the last unit at the same time, prices get overwritten, and nobody is alerted
about low stock. The business needs a single, always-available system of record exposed as an API.

**Decision enabled.** Daily reorder decisions come from `GET /products?low_stock=true`.
**Measurable benefit.** Zero oversold orders, and the low-stock list available instantly instead of after a manual spreadsheet check.

## 2. Scope

**In scope:** product catalogue CRUD, order placement with stock control, low-stock report, health
checks, API-key protection for writes, AWS deployment with secrets, logging, alarms, backups and a budget.

**Out of scope (documented as roadmap):** user accounts/roles, payments, HTTPS custom domain,
multi-region, order cancellation/refunds, a front-end UI.

## 3. Inputs, outputs, constraints

| | |
|---|---|
| Inputs | JSON over HTTP: products (SKU, name, price in paise/cents, stock, reorder level) and orders (customer email + 1–50 lines) |
| Outputs | JSON resources, standard HTTP status codes, `x-request-id` header for tracing |
| Constraints | AWS free tier (≤ $5/month budget), simulated data only, no real customer PII, deployable by a mentor from the README |

## 4. Functional requirements

| ID | Requirement |
|---|---|
| F1 | Create / read / update / delete products. SKU is unique, uppercase `A-Z 0-9 -`, 3–32 chars |
| F2 | Prices are stored as integers in the smallest currency unit (no floating-point rounding) |
| F3 | An order is **all-or-nothing**: if any line lacks stock, nothing is deducted and the API returns 409 with details |
| F4 | Concurrent orders for the same product must never drive stock below zero |
| F5 | An order stores each line's unit price at the time of purchase |
| F6 | `low_stock=true` lists products where stock ≤ reorder level |
| F7 | Write operations require a valid `X-API-Key`. Reads are open (internal network assumption) |
| F8 | A product that appears in past orders cannot be deleted (409) |
| F9 | Liveness (`/health`) and readiness (`/health/ready`, checks DB) endpoints |

## 5. Non-functional requirements & success metrics

| ID | Requirement | Target / measure |
|---|---|---|
| N1 | Security | No credentials in code, images, env vars or Git. Least-privilege IAM. DB not internet-reachable |
| N2 | Observability | Every request logged as JSON with request ID, status and latency. Alarms for 5xx, latency, CPU, storage, host failure |
| N3 | Recoverability | RPO ≤ 5 minutes (point-in-time restore), RTO ≤ 30 minutes (runbook) |
| N4 | Performance | p95 latency < 300 ms for single-resource calls at demo load |
| N5 | Cost | ≤ $5/month on free tier, with a budget alert at 80% |
| N6 | Quality | ≥ 90% automated test coverage. All smoke checks pass against the cloud deployment |
| N7 | Reproducibility | Whole environment created by one command from the README |

## 6. Edge cases considered

Blank or whitespace names · negative price/stock · lowercase or injection-style SKU · duplicate SKU (incl.
race → DB unique constraint) · unknown product in an order · same product twice in one order · quantity 0 ·
empty order · oversell on the 2nd line of a multi-line order · two simultaneous orders for the last unit ·
price changed after an order · deleting a product with order history · pagination limit 0 / >100 / negative offset ·
DB unreachable (readiness returns 503) · DB password rotated while app is running · unhandled exception
(returns a generic 500 with request ID, no stack trace leaked).

## 7. Acceptance criteria (mapped to evidence)

| Criterion | Evidence |
|---|---|
| All F1–F9 implemented | `tests/test_products.py`, `tests/test_orders.py`, `tests/test_health.py` |
| Secrets never in plain config | `tests/test_config.py`, `infra/template.yaml` (only ARNs in `app.env`) |
| Deployed stack passes smoke test | `evidence/smoke-*.json` from the AWS run + screenshot |
| Alarms reach email | Screenshot of SNS alarm email (see runbook §Alarm test) |
| Restore procedure works | Screenshot/log of the point-in-time restore drill (runbook §Restore drill) |
| Mentor can reproduce | README "Run locally" and "Deploy to AWS" sections |
