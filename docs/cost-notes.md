# Cost-Awareness Notes

> Prices are approximate on-demand rates (us-east-1 / ap-south-1, 2025–26) and vary by region. Check the
> [AWS Pricing Calculator](https://calculator.aws/) before deploying. **Free-tier note:** accounts created
> **before 15 July 2025** get the classic 12-month free tier (750 h/month of t2/t3.micro EC2 and of RDS
> micro instances). Accounts created **after** that date get the *Free Plan* with up to $200 credits for 6 months
> instead. Either way this stack should cost you little or nothing during the internship.

## Monthly estimate (running 24×7)

| Resource | Sizing | Without free tier | With free tier |
|---|---|---|---|
| EC2 | t3.micro, 730 h | ~$7.60–8.20 | $0 (750 h) |
| EBS root volume | 10 GB gp3 | ~$0.80 | $0 (30 GB) |
| Public IPv4 (Elastic IP) | 1 address, 730 h | ~$3.65 | $0 (750 h, EC2 free tier) |
| RDS PostgreSQL | db.t4g.micro single-AZ, 730 h | ~$11.70–12.40 | $0 (750 h) |
| RDS storage | 20 GB gp3 | ~$2.30–2.60 | $0 (20 GB) |
| RDS backups | 7 days, ≤ 20 GB | $0 (free up to DB size) | $0 |
| Secrets Manager | 2 secrets | $0.80 | $0.80 (30-day trial per secret) |
| CloudWatch | 7 alarms, 3 custom metrics, 1 dashboard, < 1 GB logs | ~$0–1 | $0 (10 alarms, 10 metrics, 3 dashboards, 5 GB logs) |
| SNS email, Budgets | | $0 | $0 |
| Data transfer out | < 1 GB | ~$0 | $0 (100 GB) |
| **Total** | | **≈ $27–30 / month** | **≈ $0.80 / month** |

## Cost decisions taken

| Decision | Saving | Trade-off accepted |
|---|---|---|
| **No NAT gateway.** The DB needs no internet access and the app sits in a public subnet | ~$32/month + data processing | The app instance has a public IP (mitigated by an SG allowing only port 80, no SSH) |
| EC2 + Docker instead of ECS Fargate / App Runner / ALB | ALB alone is ~$16/month, App Runner ~$5–25 | No managed load balancing or HTTPS (on the roadmap) |
| Single-AZ RDS | ~50% of DB cost | RTO ≈ 30 min on AZ failure instead of ~2 min |
| Graviton `db.t4g.micro` | ~10–20% cheaper than t3 | None for Postgres |
| gp3 volumes | ~20% cheaper than gp2 at the same baseline | None |
| 14-day log retention (the default is *never expire*) | Prevents log storage growing forever | Older logs are lost (export to S3 if needed) |
| Metric filters instead of the CloudWatch agent / custom SDK metrics | Within the 10 free custom metrics | Metrics are derived from logs (slight delay) |
| RDS-managed secret instead of a self-managed rotation Lambda | No Lambda or extra code | $0.40/month per secret |
| `AWS::Budgets::Budget` at $5 with forecast alerts | Catches mistakes (e.g. forgotten resources) early | |
| Everything tagged `Project=brightmart-api` | Enables Cost Explorer filtering by tag (activate the cost-allocation tag in Billing) | |

## What would increase cost (watch out)

- Leaving the stack running after the internship. **Run `scripts/teardown.ps1`.**
- RDS final snapshots after deletion are billed per GB-month (small, but delete them when no longer needed).
- Switching to Multi-AZ, larger instance classes, or enabling Performance Insights long-term retention.
- Unexpected traffic or log volume. The budget alert and the 14-day retention limit the damage.
- A t3 instance in "unlimited" credit mode that runs at high CPU for long periods (CPU alarm at 80%).

## Cost at 10× scale (rough)

ALB (~$18), 2–3 × t3.small in an ASG (~$30–45), RDS db.t4g.small Multi-AZ (~$50), RDS Proxy (~$22),
NAT gateway if instances move to private subnets (~$35). That comes to roughly **$150–170/month**, which
is still cheap for a production retail API.
