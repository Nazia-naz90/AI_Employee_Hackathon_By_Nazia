# vault_sync_local.ps1 — Run on LOCAL machine (Windows)
# Synchronizes vault with GitHub repo for Cloud↔Local coordination

$ErrorActionPreference = "Stop"
$VaultDir = ".\vault"

Push-Location $VaultDir
try {
    Write-Host "Pulling from remote..."
    git pull origin main --no-edit
    
    $status = git status --porcelain
    if ($status) {
        git add -A
        git commit -m "local-sync: $(Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ')"
        git push origin main
        Write-Host "Pushed local changes"
    } else {
        Write-Host "No local changes to push"
    }
} catch {
    Write-Host "Sync error: $_" -ForegroundColor Red
} finally {
    Pop-Location
}
