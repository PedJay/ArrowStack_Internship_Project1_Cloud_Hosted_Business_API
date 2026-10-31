# Ships new application code without touching infrastructure:
# runs /opt/app/deploy.sh on the instance through SSM (git pull -> docker build -> restart -> readiness check).
param(
    [string]$StackName = "brightmart-api",
    [string]$Region = "ap-south-1"
)
$ErrorActionPreference = "Stop"

$instanceId = aws cloudformation describe-stacks --stack-name $StackName --region $Region `
    --query "Stacks[0].Outputs[?OutputKey=='InstanceId'].OutputValue" --output text

$commandId = aws ssm send-command --region $Region --instance-ids $instanceId `
    --document-name AWS-RunShellScript `
    --comment "redeploy $StackName" `
    --parameters "commands=/opt/app/deploy.sh" `
    --query "Command.CommandId" --output text

Write-Host "Command $commandId sent to $instanceId; waiting..."
aws ssm wait command-executed --region $Region --command-id $commandId --instance-id $instanceId
aws ssm get-command-invocation --region $Region --command-id $commandId --instance-id $instanceId `
    --query "{Status:Status,Output:StandardOutputContent,Errors:StandardErrorContent}" --output json
