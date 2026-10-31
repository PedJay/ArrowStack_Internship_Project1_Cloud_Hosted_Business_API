# Presentation & Demo Outline (10 minutes)

1. **Problem** (1 min): BrightMart oversells stock and has no low-stock visibility. The stakeholder is the store-operations manager. Success means zero overselling, an instant low-stock list, and ≤ $5/month.
2. **Architecture** (2 min): the diagram from the README. Walk the request flow: EIP → EC2/Docker → RDS in a private subnet, with secrets, logs and alarms.
3. **Live demo** (3 min):
   - Swagger `/docs`: create 2 products, place an order, then try to oversell → 409 with details.
   - Run `smoke_test.py` against the cloud URL: 13/13.
   - CloudWatch dashboard: the traffic just generated. Logs Insights: trace the request ID from the 409.
4. **Security** (1.5 min): IAM policy screenshot (2 secrets, 1 log group), no SSH, DB not public, IMDSv2, non-root container, auto-rotated DB password.
5. **Reliability & cost** (1.5 min): backups/PITR (RPO 5 min), restore drill result (RTO), auto-recovery, budget. Cost table: ≈$0.80/month on free tier vs ≈$28 without, and why there's no NAT gateway.
6. **Limitations & next steps** (1 min): TLS via ALB/CloudFront, multi-AZ, least-privilege DB role, CI/CD to ECR.

## Viva preparation (handbook questions)

**What problem does it solve, and how did you define success?** It prevents overselling and gives the operations manager a live
low-stock list. Success metrics are in `requirements.md` §5: zero oversell (proven by a test plus row locking), p95 < 300 ms,
RPO 5 min / RTO 30 min, ≤ $5/month, ≥ 90% coverage.

**Biggest-impact decision?** Locking product rows with `SELECT … FOR UPDATE` (sorted to avoid deadlocks) inside one
transaction. That guarantees correctness under concurrency. Close second: discovering that RDS rotates its managed password
weekly, and making the app refresh credentials on auth failure.

**How did you validate?** 35 pytest tests (97% coverage), including mocked Secrets Manager and rotation. `cfn-lint`
on the IaC. A scripted 13-check smoke test run locally and against AWS. An alarm-fire test. A restore drill.

**Edge cases / risks?** See requirements §6. Main risks: plain HTTP, single instance, single AZ, app using the DB master user.
All are documented with mitigations.

**10× users?** ALB + Auto Scaling group (or ECS Fargate) across 2 AZs, RDS Multi-AZ + RDS Proxy + read replica,
caching for catalogue reads, CI/CD to ECR, load testing with k6. About $150–170/month.

**Explain it to a non-technical stakeholder.** "It's the shop's single source of truth for stock. When someone places
an order, it checks and reserves the stock in one step, so two people can never sell the last item. Every morning it
can tell you what to reorder. It runs in Amazon's cloud, backs itself up every day, and emails us if anything goes wrong."

**Most independent problem-solving?** Making credential rotation safe without restarts, and making the deployment
self-verifying (`cfn-signal` only after `/health/ready` passes), so a broken deploy fails the stack instead of looking green.
