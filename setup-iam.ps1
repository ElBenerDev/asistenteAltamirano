$ErrorActionPreference = "Stop"

# Configuration
$config = @{
    RetryCount = 3
    RetryDelay = 60
    ProjectID = $(gcloud config get-value project)
}

Write-Host "Project ID: $($config.ProjectID)" -ForegroundColor Green

$ServiceAccountName = "asistente-altamirano-sa"
$ServiceAccountEmail = "$ServiceAccountName@$($config.ProjectID).iam.gserviceaccount.com"

# Create Service Account
Write-Host "`nCreating Service Account..." -ForegroundColor Cyan
try {
    gcloud iam service-accounts create $ServiceAccountName `
        --description="Service Account for Asistente Altamirano" `
        --display-name="Asistente Altamirano SA"
    Start-Sleep -Seconds 10
} catch {
    Write-Host "Service account might already exist, continuing..." -ForegroundColor Yellow
}

# Required roles
$roles = @(
    "roles/run.invoker",
    "roles/iam.serviceAccountUser",
    "roles/run.developer"
)

# Grant roles with delay between each
foreach ($role in $roles) {
    Write-Host "`nAssigning role: $role" -ForegroundColor Cyan
    try {
        gcloud projects add-iam-policy-binding $config.ProjectID `
            --member="serviceAccount:$ServiceAccountEmail" `
            --role=$role
        Start-Sleep -Seconds 30  # Avoid rate limits
    } catch {
        Write-Host "Error assigning role $role. Continuing..." -ForegroundColor Red
    }
}

# Update Cloud Run service
Write-Host "`nUpdating Cloud Run service..." -ForegroundColor Cyan
try {
    gcloud run services update asistente-altamirano `
        --region=us-central1 `
        --service-account=$ServiceAccountEmail `
        --platform=managed
} catch {
    Write-Host "Error updating Cloud Run service" -ForegroundColor Red
    Write-Host $_.Exception.Message
}

Write-Host "`nSetup completed!" -ForegroundColor Green