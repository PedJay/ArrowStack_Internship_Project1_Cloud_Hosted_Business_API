# Architecture & Design

## Components

| Layer | AWS service | Why |
|---|---|---|
| Network | VPC with 1 public + 2 private subnets, Internet Gateway, **no NAT gateway** | The DB lives in private subnets with no internet route at all. Skipping NAT saves about $32/month |
| Compute | EC2 t3.micro (Amazon Linux 2023) running the API in **Docker** | Free-tier eligible. Docker gives the same runtime locally and in AWS |
| Public endpoint | Elastic IP | The URL stays stable if the instance is recovered |
| Database | RDS PostgreSQL db.t4g.micro, single-AZ, encrypted gp3 20 GB | A managed DB handles patching, backups and PITR. Free-tier eligible |
| Secrets | Secrets Manager: RDS-managed master secret (auto-rotated) + generated API key | No credentials anywhere in code, Git, AMI or CloudFormation parameters |
| Logs | CloudWatch Logs via Docker `awslogs` driver, 14-day retention | No agent to install. JSON logs are queryable in Logs Insights |
| Metrics & alerts | Log metric filters → custom metrics → CloudWatch alarms → SNS email | Request count, 5xx count and latency come from logs, at no agent cost |
| Self-healing | Docker `--restart unless-stopped` + container HEALTHCHECK + EC2 **auto-recover** alarm action | Covers process crashes and underlying host failures |
| Cost guardrail | AWS Budgets monthly budget with actual (80%) and forecast (100%) email alerts | |
| IaC | One CloudFormation template | The whole environment is reproducible and reviewable |

## Request flow

1. The client calls `http://<EIP>/orders` with the `X-API-Key` header.
2. The security group allows port 80 only (no 22). Docker maps 80 → container 8000.
3. Middleware assigns or propagates `x-request-id`, times the request, and writes one JSON log line.
4. The route validates input with Pydantic and compares the API key in constant time (`hmac.compare_digest`).
5. Order creation opens a transaction and runs `SELECT … FOR UPDATE` on the product rows (sorted by id to avoid
   deadlocks). It checks every line, decrements stock, inserts the order, then commits. If any line fails, it rolls back.
6. New DB connections get their username and password from Secrets Manager (cached for 5 minutes). If login fails
   because RDS rotated the password, the app re-reads the secret once and retries.

## Data model

```
products(id PK, sku UNIQUE, name, price_cents ≥0, stock ≥0, reorder_level, created_at, updated_at)
orders(id PK, customer_email, status, total_cents, created_at)
order_items(id PK, order_id FK→orders ON DELETE CASCADE, product_id FK→products ON DELETE RESTRICT,
            quantity, unit_price_cents)
```

The CHECK constraints and foreign keys enforce the business rules **in the database as well as the app**.

## Security & IAM

| Control | Implementation |
|---|---|
| Least-privilege instance role | `secretsmanager:GetSecretValue` on **exactly 2 secret ARNs**. `logs:CreateLogStream/PutLogEvents` on **one log group**. `AmazonSSMManagedInstanceCore` for keyless shell access |
| No SSH | Port 22 is closed and no key pair is attached. Admin access is SSM Session Manager (IAM-authenticated and audited in CloudTrail) |
| Network isolation | RDS is `PubliclyAccessible: false`, sits in subnets with no internet route, and its SG accepts 5432 **only from the app SG**. DB SG egress is blocked |
| Encryption at rest | RDS storage, automated backups, snapshots and the EBS root volume are all encrypted with KMS |
| Encryption in transit (DB) | `sslmode=require` on Postgres connections |
| IMDSv2 only | `HttpTokens: required` blocks SSRF-style credential theft through IMDSv1. Hop limit 2 lets the container use the role |
| Container hardening | Runs as non-root UID 10001, slim base image, no build tools or secrets in the image |
| App-level | Input validation on every field, constant-time key comparison, generic 500 bodies (no stack traces), parameterised SQL via SQLAlchemy |
| Secret rotation | The RDS-managed password rotates automatically (every 7 days by default). The app handles it with no restart |

## Key trade-offs

See [decision-log.md](decision-log.md). Summary: **EC2 + Docker** was chosen over App Runner/ECS Fargate (cost: free tier),
**single-AZ** RDS over Multi-AZ (cost: 2× price), and **API key** over Cognito/JWT (scope for a 1-month project).

## Limitations & roadmap

| Limitation | Risk | Next step |
|---|---|---|
| Plain HTTP, no TLS to the client | API key could be sniffed on untrusted networks | ALB + ACM certificate + custom domain, or CloudFront in front of the instance. Lock the SG to the ALB/CloudFront |
| Single EC2 instance | Downtime while it is recovered or redeployed (~1 min) | ALB + Auto Scaling group across 2 AZs, rolling deploys, or move to ECS Fargate |
| Single-AZ RDS | AZ outage → restore from backup (RTO ~30 min) | Multi-AZ (automatic failover ~60–120 s) |
| App uses the DB master user | Blast radius if the app is compromised | Create a limited `app_rw` role with only DML grants, and use IAM DB authentication |
| Schema created with `create_all` | No versioned migrations | Alembic migrations run as a deploy step |
| Image built on the instance from a public repo | Slower deploys, depends on GitHub/Docker Hub availability | CI (GitHub Actions) builds, scans and pushes to ECR. The instance pulls a pinned tag |
| Shared single API key | No per-user audit or revocation | Cognito / OIDC JWTs with roles (manager vs. order desk) |

### Supporting 10× load

Put an ALB in front of an Auto Scaling group (2–6 instances) or ECS Fargate service. Add RDS Proxy for
connection pooling, a read replica for reporting queries, and response caching for the catalogue (ElastiCache or
CloudFront). Then load-test with k6/Locust and add alarms on ALB `TargetResponseTime` and `HTTPCode_Target_5XX`.
