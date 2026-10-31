# Deletes the stack. RDS takes a FINAL SNAPSHOT first (DeletionPolicy: Snapshot) so data is recoverable.
# Snapshots cost a little per GB-month once the DB is gone; the script lists them so you can delete them.
param(
    [string]$StackName = "brightmart-api",
    [string]$Region = "ap-south-1"
)
$ErrorActionPreference = "Stop"

$answer = Read-Host "Delete stack '$StackName' in $Region? Type the stack name to confirm"
if ($answer -ne $StackName) { Write-Host "Aborted."; exit 1 }

aws cloudformation delete-stack --stack-name $StackName --region $Region
Write-Host "Waiting for deletion (RDS final snapshot takes several minutes)..."
aws cloudformation wait stack-delete-complete --stack-name $StackName --region $Region
Write-Host "Stack deleted. Remaining manual snapshots:"
aws rds describe-db-snapshots --region $Region --snapshot-type manual `
    --query "DBSnapshots[?starts_with(DBInstanceIdentifier, '$StackName')].[DBSnapshotIdentifier,SnapshotCreateTime,AllocatedStorage]" `
    --output table
Write-Host "Delete one with: aws rds delete-db-snapshot --db-snapshot-identifier <id> --region $Region"
