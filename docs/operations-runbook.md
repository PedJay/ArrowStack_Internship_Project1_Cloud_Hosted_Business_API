# Operations Runbook

Set these first (PowerShell):

```powershell
$STACK="brightmart-api"; $REGION="ap-south-1"
function out($k) { aws cloudformation describe-stacks --stack-name $STACK --region $REGION --query "Stacks[0].Outputs[?OutputKey=='$k'].OutputValue" --output text }
```

## Monitoring

| Signal | Source | Alarm | Threshold | Action |
|---|---|---|---|---|
| 5xx responses | Log metric filter `ServerErrors` | `<stack>-5xx-errors` | ≥ 5 in 5 min | Email |
| p95 latency | Log metric filter `LatencyMs` | `<stack>-p95-latency` | > 1000 ms for 15 min | Email |
| Host failure | `StatusCheckFailed_System` | `<stack>-instance-system-check` | ≥ 1 for 2 min | **EC2 auto-recover** + email |
| EC2 CPU | `AWS/EC2 CPUUtilization` | `<stack>-instance-cpu` | > 80% for 15 min | Email |
| DB CPU | `AWS/RDS CPUUtilization` | `<stack>-db-cpu` | > 80% for 15 min | Email |
| DB storage | `AWS/RDS FreeStorageSpace` | `<stack>-db-free-storage` | < 2 GiB | Email |
| Spend | AWS Budgets | `<stack>-monthly` | 80% actual / 100% forecast | Email |

**Dashboard:** the `DashboardUrl` stack output shows requests, 5xx, p50/p95 latency, EC2/RDS CPU, DB connections, storage and recent errors.

**Useful Logs Insights queries** (log group `/brightmart-api/app`):

```
# Slowest endpoints
fields path, duration_ms | filter msg = "request" | stats avg(duration_ms), pct(duration_ms, 95), count() by path | sort pct(duration_ms, 95) desc

# Trace one request end to end
fields @timestamp, level, msg, status | filter request_id = "<id from x-request-id header>"

# Error rate per 5 minutes
filter msg = "request" | stats sum(status >= 500) / count() * 100 as error_pct by bin(5m)
```

### Alarm test (do once, screenshot the email for evidence)

```powershell
aws cloudwatch set-alarm-state --alarm-name "$STACK-5xx-errors" --state-value ALARM --state-reason "Manual alarm test" --region $REGION
```

You should receive an email within about 1 minute. The alarm returns to OK at the next evaluation.

## Backup & recovery

| | Setting | Meaning |
|---|---|---|
| Automated backups | Daily, 00:00–00:30 IST, retained 7 days | Free up to the DB's storage size |
| Point-in-time restore (PITR) | Transaction logs every 5 min | **RPO ≤ 5 minutes** |
| Final snapshot | `DeletionPolicy: Snapshot` | Deleting the stack never silently destroys data |
| Encryption | Backups and snapshots inherit KMS encryption | |
| Application tier | Stateless. Rebuilt from Git by `deploy.sh` | No backup needed |
| **Target RTO** | ≤ 30 minutes | Measured in the restore drill below |

### Scenario A: bad data written (e.g. bulk wrong price update at 14:05)

1. Pick a restore time just **before** the incident (UTC). Check the logs for the first bad request.
2. Restore to a **new** instance (the original is untouched):
   ```powershell
   aws rds restore-db-instance-to-point-in-time --region $REGION `
     --source-db-instance-identifier "$STACK-db" `
     --target-db-instance-identifier "$STACK-db-restored" `
     --restore-time 2026-10-20T08:30:00Z `
     --db-subnet-group-name <DbSubnetGroup physical id> `
     --vpc-security-group-ids <DbSecurityGroup id> `
     --no-publicly-accessible --db-instance-class db.t4g.micro
   aws rds wait db-instance-available --db-instance-identifier "$STACK-db-restored" --region $REGION
   ```
   The subnet-group and SG IDs are on the stack's **Resources** tab.
3. Either copy only the affected rows back (`pg_dump -t products` from the restored DB, via SSM session on
   the instance), **or** fail over fully. To fail over, edit `DB_HOST` in `/opt/app/app.env` to the restored
   endpoint and run `/opt/app/deploy.sh`.
4. Credentials: the restored DB has the master password that was valid **at the restore time**. If
   RDS rotated the secret after that time, use the secret's `AWSPREVIOUS` version, or reset the password with
   `aws rds modify-db-instance --manage-master-user-password` on the restored DB and point `DB_SECRET_ARN` at its
   new secret (and allow the instance role to read it). Record the incident in the work log.

### Scenario B: database instance lost

Restore the latest snapshot (`aws rds restore-db-instance-from-db-snapshot …`) or PITR to "latest
restorable time", then point the app at it as above.

### Scenario C: EC2 instance lost

The auto-recover alarm handles host failure. If the instance is terminated, run `.\scripts\deploy.ps1`
again: CloudFormation recreates it, re-attaches the Elastic IP, and user-data rebuilds the app. No data is lost
because the instance is stateless.

### Restore drill (do once, record timings as evidence)

1. Note the row counts (`GET /products`) and the time T0.
2. Run Scenario A step 2 with `--use-latest-restorable-time`. Record when the instance is `available` (T1).
3. Connect from the instance (`aws ssm start-session`, then `docker exec -it api python`) and verify the row counts.
4. **RTO achieved = T1 − T0** (+ switch-over time). Record it in `docs/test-evidence.md`.
5. Delete the restored instance: `aws rds delete-db-instance --db-instance-identifier $STACK-db-restored --skip-final-snapshot`.

## Routine operations

| Task | How |
|---|---|
| Deploy new code | `.\scripts\redeploy_app.ps1`. Pulls Git, rebuilds, restarts, waits for readiness |
| Shell access | `aws ssm start-session --target (out InstanceId) --region $REGION` |
| App logs live | `aws logs tail /brightmart-api/app --follow --region $REGION` |
| Rotate API key | `aws secretsmanager put-secret-value --secret-id $STACK/api-key --secret-string <new>`, then `redeploy_app.ps1` |
| DB password rotation | Automatic (RDS-managed). The app re-reads it on login failure. Force one with `aws secretsmanager rotate-secret --secret-id <MasterUserSecret ARN>` |
| Lock API to your IP | Redeploy with `-AllowedHttpCidr <your.ip>/32` |

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Stack stuck at `AppInstance CREATE_IN_PROGRESS` then fails | User-data failed. Check `/var/log/cloud-init-output.log` through an SSM session. Usually the repo URL is wrong or private |
| `/health` OK but `/health/ready` 503 | DB unreachable or credentials. Check `docker logs api` for the error, and the SG and secret permissions |
| 401 on writes | Wrong key. Re-read it from Secrets Manager. The header name is `X-API-Key` |
| Redeploy with same name fails on secret | A deleted secret stays in a 7–30 day recovery window. Run `aws secretsmanager delete-secret --secret-id brightmart-api/api-key --force-delete-without-recovery` |
