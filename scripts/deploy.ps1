# Deploys (or updates) the whole stack with CloudFormation, then prints the outputs.
# Usage:
#   .\scripts\deploy.ps1 -GitRepoUrl https://github.com/<you>/<repo>.git -AlertEmail you@example.com
# Optional:
#   -AppSubdir project1-cloud-business-api   if the repo root is the parent internship folder
#   -InstanceType t2.micro if t3.micro is not free-tier eligible / available in your region
#   -NoRollback           keep failed resources so you can read the instance logs (debugging only)
param(
    [Parameter(Mandatory = $true)][string]$GitRepoUrl,
    [Parameter(Mandatory = $true)][string]$AlertEmail,
    [string]$StackName = "brightmart-api",
    [string]$Region = "ap-south-1",
    [string]$GitBranch = "master",
    [string]$AppSubdir = ".",
    [string]$InstanceType = "t3.micro",
    [string]$AllowedHttpCidr = "0.0.0.0/0",
    [int]$BackupRetentionDays = 1,   # the AWS free plan rejects 7; use 7 on a paid plan
    [int]$MonthlyBudgetUsd = 5,
    [switch]$NoRollback
)
$ErrorActionPreference = "Stop"
$template = Join-Path $PSScriptRoot "..\infra\template.yaml"

$extra = @()
if ($NoRollback) { $extra += "--disable-rollback" }

Write-Host "Deploying stack '$StackName' to $Region (first deploy takes ~15 minutes: RDS creation is slow)..."
aws cloudformation deploy `
    --template-file $template `
    --stack-name $StackName `
    --region $Region `
    --capabilities CAPABILITY_IAM `
    --no-fail-on-empty-changeset `
    --tags Project=$StackName Owner=arrowstack-intern `
    @extra `
    --parameter-overrides `
        ProjectName=$StackName `
        GitRepoUrl=$GitRepoUrl `
        GitBranch=$GitBranch `
        AppSubdir=$AppSubdir `
        InstanceType=$InstanceType `
        AlertEmail=$AlertEmail `
        AllowedHttpCidr=$AllowedHttpCidr `
        BackupRetentionDays=$BackupRetentionDays `
        MonthlyBudgetUsd=$MonthlyBudgetUsd
if ($LASTEXITCODE -ne 0) { throw "CloudFormation deploy failed - check the Events tab in the console (see RUN-GUIDE troubleshooting)." }

aws cloudformation describe-stacks --stack-name $StackName --region $Region `
    --query "Stacks[0].Outputs[].[OutputKey,OutputValue]" --output table

Write-Host ""
Write-Host "Next: confirm the SNS subscription email, then run the smoke test:"
Write-Host "  `$key = aws secretsmanager get-secret-value --secret-id $StackName/api-key --region $Region --query SecretString --output text"
Write-Host "  .venv\Scripts\python scripts\smoke_test.py --base-url <ApiUrl> --api-key `$key"
