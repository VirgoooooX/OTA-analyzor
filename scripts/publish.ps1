param(
    [string]$Message = "chore: publish ota analyzer",
    [string]$Remote = "origin",
    [switch]$NoVerify
)

$ErrorActionPreference = "Stop"

function Invoke-Step {
    param(
        [string]$Title,
        [scriptblock]$Command
    )

    Write-Host ""
    Write-Host "==> $Title"
    & $Command
}

Invoke-Step "Checking git repository" {
    git rev-parse --is-inside-work-tree | Out-Null
}

$branch = (git branch --show-current).Trim()
if (-not $branch) {
    throw "No current git branch found."
}

$remoteUrl = (git remote get-url $Remote).Trim()
Write-Host "Branch: $branch"
Write-Host "Remote: $remoteUrl"

if (-not $NoVerify) {
    $python = (Get-Command python -ErrorAction SilentlyContinue)
    if ($python) {
        Invoke-Step "Running unit tests" {
            python -m unittest tests.test_analysis -v
        }
    } else {
        Write-Host "Python was not found in PATH, skipping local tests. GitHub Actions will run them."
    }
}

$status = git status --short
if ($status) {
    Invoke-Step "Staging changes" {
        git add -A
    }

    Invoke-Step "Creating commit" {
        git commit -m $Message
    }
} else {
    Write-Host "No local changes to commit."
}

Invoke-Step "Pushing to GitHub" {
    git push -u $Remote $branch
}

Write-Host ""
Write-Host "Pushed successfully."
Write-Host "GitHub Actions will build and publish the Docker image to GHCR."
Write-Host "Image: ghcr.io/virgooooox/ota-analyzor:latest"

