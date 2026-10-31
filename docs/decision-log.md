# Decision Log

| # | Date | Decision | Options considered | Rationale |
|---|---|---|---|---|
| D1 | 2026-10-15 | **AWS** as the cloud provider | AWS, Azure, GCP | Largest free tier for EC2/RDS, most common in job descriptions, mature IaC (CloudFormation) |
| D2 | 2026-10-15 | **Python 3.12 + FastAPI** | Flask, Node/Express | Automatic request validation + OpenAPI docs, type hints, fast to test |
| D3 | 2026-10-15 | **EC2 + Docker** (single instance) for compute | App Runner, ECS Fargate + ALB, Elastic Beanstalk, Lambda | Free-tier eligible. Docker keeps it portable to ECS later. Lambda is a poor fit for a pooled-connection SQL API without RDS Proxy |
| D4 | 2026-10-15 | **RDS PostgreSQL**, single-AZ, db.t4g.micro | DynamoDB, Aurora Serverless v2, self-managed Postgres on EC2 | Relational data with transactions and row locks (needed for stock). Managed backups/PITR. Aurora has no free tier |
| D5 | 2026-10-15 | **No NAT gateway**. App in public subnet, DB in isolated private subnets | NAT gateway, VPC endpoints | Saves ~$32/mo. Risk is controlled by SGs (port 80 only, no SSH) |
| D6 | 2026-10-15 | **RDS-managed master secret** (`ManageMasterUserPassword`) | Password as CFN parameter, SSM SecureString, self-managed Secrets Manager rotation Lambda | Password is never seen by a human or stored in CFN. Rotation is built in |
| D7 | 2026-10-15 | App fetches DB creds **per new connection** with a 5-min cache and a retry on auth failure | Read once at startup | Found during design: RDS rotates managed passwords every 7 days by default, so read-once would break the app weekly. Covered by `tests/test_db_rotation.py` |
| D8 | 2026-10-15 | **Money as integer minor units** (`price_cents`) | `float`, `Decimal`/NUMERIC | Avoids float rounding errors, and integers are simple across JSON and SQL |
| D9 | 2026-10-15 | **Pessimistic row locking** (`SELECT … FOR UPDATE`, ids sorted) for orders | Optimistic version column, `UPDATE … WHERE stock >= n` | Simple and correct for low-concurrency retail. Sorted locking prevents deadlocks |
| D10 | 2026-10-15 | **API key** in header for writes | Cognito user pools, IAM auth, no auth | Proportionate for an internal internship API. Cognito/JWT is on the roadmap |
| D11 | 2026-10-15 | **CloudFormation** (single template) | Terraform, CDK, console clicks | No extra tool to install. Native to AWS. A mentor can deploy with only the AWS CLI |
| D12 | 2026-10-15 | Build image **on the instance** from Git | ECR + CI pipeline | Docker isn't on the dev laptop. Keeps the setup simple. ECR + GitHub Actions is on the roadmap |
| D13 | 2026-10-15 | Metrics from **log metric filters** | CloudWatch agent, embedded metric format, Prometheus | Zero extra software, stays within free-tier custom metrics |
| D14 | 2026-10-15 | `CreationPolicy` + `cfn-signal` after `/health/ready` | Fire-and-forget user data | The deployment only "succeeds" when the app actually serves traffic, so broken deploys fail loudly |
| D15 | 2026-10-15 | Omit RDS `EngineVersion` (use the RDS default) | Pin `16` / a specific minor | `cfn-lint` flagged a bare major version as invalid for new instances. Pinned minors get retired. Record the actual version from the console in the evidence |
| D16 | 2026-10-31 | RDS backup retention is a parameter, **default 1 day** | Keep 7 days, upgrade the account plan | The first real deploy failed: the AWS free plan rejects a 7-day retention ("exceeds the maximum available to free tier customers"). 1 day still gives daily backups, point-in-time restore and the final snapshot. RPO is unchanged (~5 min); only the restore window is shorter. `-BackupRetentionDays 7` restores the original design on a paid plan |
