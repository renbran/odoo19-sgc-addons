# LLM Lead Scoring - Google Custom Search Integration Deployment
# Target: 139.84.163.11 (scholarixv2 database)
# Date: November 29, 2025

param(
    [string]$SSHKey = "C:\Users\branm\.ssh\scholarix_vultr",
    [string]$Server = "root@139.84.163.11",
    [string]$ModuleName = "llm_lead_scoring",
    [string]$Database = "scholarixv2",
    [switch]$SkipBackup = $false
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "LLM Lead Scoring Deployment" -ForegroundColor Cyan
Write-Host "Google Custom Search Integration" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Validation
Write-Host "[1/7] Validating files..." -ForegroundColor Yellow
$ModulePath = Split-Path -Parent $PSCommandPath
$RequiredFiles = @("models/web_research_service.py", "wizards/google_search_setup_wizard.py", "__manifest__.py")
foreach ($file in $RequiredFiles) {
    if (-not (Test-Path (Join-Path $ModulePath $file))) {
        Write-Host "ERROR: Missing $file" -ForegroundColor Red
        exit 1
    }
}
Write-Host "Success: All files present" -ForegroundColor Green
Write-Host ""

# SSH Test
Write-Host "[2/7] Testing SSH..." -ForegroundColor Yellow
$test = ssh -i $SSHKey -o ConnectTimeout=10 $Server "echo OK" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Cannot connect to $Server" -ForegroundColor Red
    exit 1
}
Write-Host "Success: Connected" -ForegroundColor Green
Write-Host ""

# Backup DB
if (-not $SkipBackup) {
    Write-Host "[3/7] Backing up database..." -ForegroundColor Yellow
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $backupFile = "/tmp/${Database}_${timestamp}.sql"
    ssh -i $SSHKey $Server "sudo -u postgres pg_dump $Database > $backupFile"
    Write-Host "Success: Backup at $backupFile" -ForegroundColor Green
} else {
    Write-Host "[3/7] Skipping backup" -ForegroundColor Yellow
}
Write-Host ""

# Backup Module
Write-Host "[4/7] Backing up module..." -ForegroundColor Yellow
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
ssh -i $SSHKey $Server "cd /var/odoo/scholarixv2/src/addons && tar -czf /tmp/${ModuleName}_${timestamp}.tar.gz $ModuleName 2>/dev/null || true"
Write-Host "Success" -ForegroundColor Green
Write-Host ""

# Upload
Write-Host "[5/7] Uploading files..." -ForegroundColor Yellow
$targetPath = "/var/odoo/scholarixv2/src/addons/$ModuleName/"
ssh -i $SSHKey $Server "mkdir -p $targetPath"
scp -i $SSHKey -r "$ModulePath/*" "${Server}:${targetPath}" 2>$null
ssh -i $SSHKey $Server "chown -R odoo:odoo $targetPath"
Write-Host "Success: Uploaded to $targetPath" -ForegroundColor Green
Write-Host ""

# Update Module
Write-Host "[6/7] Updating Odoo module (1-2 minutes)..." -ForegroundColor Yellow
Write-Host "  Stopping Odoo..." -ForegroundColor Gray
ssh -i $SSHKey $Server "systemctl stop odoo"
Start-Sleep -Seconds 2

Write-Host "  Updating module..." -ForegroundColor Gray
$updateLog = "/tmp/odoo_update_${ModuleName}.log"
ssh -i $SSHKey $Server "cd /var/odoo/scholarixv2 && sudo -u odoo venv/bin/python3 src/odoo-bin -c odoo.conf --no-http --stop-after-init -u $ModuleName -d $Database > $updateLog 2>&1"

if ($LASTEXITCODE -eq 0) {
    Write-Host "Success: Module updated" -ForegroundColor Green
} else {
    Write-Host "ERROR: Update failed - check log: ssh -i $SSHKey $Server 'cat $updateLog'" -ForegroundColor Red
}

Write-Host "  Starting Odoo..." -ForegroundColor Gray
ssh -i $SSHKey $Server "systemctl start odoo"
Start-Sleep -Seconds 3

$status = ssh -i $SSHKey $Server "systemctl is-active odoo" 2>$null
Write-Host "  Service status: $status" -ForegroundColor $(if ($status -eq "active") { "Green" } else { "Yellow" })
Write-Host ""

# Verify
Write-Host "[7/7] Verifying..." -ForegroundColor Yellow
$modelCheck = ssh -i $SSHKey $Server "sudo -u postgres psql -d $Database -t -c `"SELECT COUNT(*) FROM ir_model WHERE model IN ('web.research.service', 'google.search.setup.wizard');`"" 2>$null
Write-Host "Models registered: $($modelCheck.Trim())/2" -ForegroundColor $(if ($modelCheck -ge 2) { "Green" } else { "Yellow" })
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "NEXT STEPS:" -ForegroundColor Cyan
Write-Host "1. Login: https://stagingtry.cloudpepper.site/" -ForegroundColor White
Write-Host "2. Go to: Settings -> CRM -> LLM Lead Scoring" -ForegroundColor White
Write-Host "3. Enable 'Live Web Research'" -ForegroundColor White
Write-Host "4. Click 'Setup Guide' button" -ForegroundColor White
Write-Host "5. Test on a lead" -ForegroundColor White
Write-Host ""
Write-Host "LOGS:" -ForegroundColor Cyan
Write-Host "ssh -i $SSHKey $Server 'tail -f /var/odoo/scholarixv2/logs/odoo-server.log'" -ForegroundColor Gray
Write-Host ""
