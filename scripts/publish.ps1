param(
    [ValidateSet("patch", "minor", "major")]
    [string]$Bump = "patch",

    [string]$Message = "",

    [string]$Remote = "origin",

    [switch]$SkipTests,

    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$script:StartTime = Get-Date

function Write-Step {
    param([string]$Title)
    Write-Host "=== $Title ===" -ForegroundColor Cyan
}

function Write-Info {
    param([string]$Text)
    Write-Host "  -> $Text"
}

function Write-Success {
    param([string]$Text)
    Write-Host "  [OK] $Text" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Text)
    Write-Host "  [!] $Text" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Text)
    Write-Host "  [X] $Text" -ForegroundColor Red
}

function Get-NextVersion {
    # Fetch all tags and find the latest semver
    $tags = git tag --list "v*" 2>$null
    $latest = "v0.0.0"

    foreach ($tag in $tags) {
        $tag = $tag.Trim()
        if ($tag -match '^v?(\d+)\.(\d+)\.(\d+)$') {
            $candidate = "v{0}.{1}.{2}" -f $Matches[1], $Matches[2], $Matches[3]
            if ((Compare-Version $candidate $latest) -gt 0) {
                $latest = $candidate
            }
        }
    }

    $parts = $latest -replace '^v', '' -split '\.'
    $major = [int]$parts[0]
    $minor = [int]$parts[1]
    $patch = [int]$parts[2]

    Write-Info "Current latest tag: $latest"

    switch ($Bump) {
        "major" {
            $major++
            $minor = 0
            $patch = 0
        }
        "minor" {
            $minor++
            $patch = 0
        }
        "patch" {
            $patch++
        }
    }

    return "v{0}.{1}.{2}" -f $major, $minor, $patch
}

function Compare-Version {
    param([string]$A, [string]$B)
    $aParts = @(($A -replace '^v', '' -split '\.' | ForEach-Object { [int]$_ }))
    $bParts = @(($B -replace '^v', '' -split '\.' | ForEach-Object { [int]$_ }))
    for ($i = 0; $i -lt [Math]::Max($aParts.Count, $bParts.Count); $i++) {
        $a = if ($i -lt $aParts.Count) { $aParts[$i] } else { 0 }
        $b = if ($i -lt $bParts.Count) { $bParts[$i] } else { 0 }
        if ($a -ne $b) { return $a - $b }
    }
    return 0
}

# --- Sanity checks ---

Write-Step "Checking repository"
git rev-parse --is-inside-work-tree 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Not inside a git repository."
    exit 1
}

$branch = (git branch --show-current).Trim()
if (-not $branch) {
    Write-Error "Detached HEAD - cannot publish."
    exit 1
}
Write-Info "Branch: $branch"

$remoteUrl = (git remote get-url $Remote 2>$null).Trim()
if (-not $remoteUrl) {
    Write-Error "Remote '$Remote' not found."
    exit 1
}
Write-Info "Remote: $remoteUrl"

# Ensure local is in sync with remote
Write-Info "Fetching from $Remote ..."
git fetch $Remote --tags --quiet 2>$null

$behind = git rev-list --count "HEAD..$Remote/$branch" 2>$null
if ($behind -gt 0) {
    Write-Warn "Local is $behind commit(s) behind $Remote/$branch. Consider pulling first."
}

# --- Determine version ---

Write-Step "Versioning"
$version = Get-NextVersion
$versionPlain = $version -replace '^v', ''

if (-not $Message) {
    $Message = "chore: release $version"
}
Write-Info "Next version:  $version"
Write-Info "Commit message: $Message"

# --- Update version in index.html ---

Write-Step "Updating index.html version"
$indexPath = Join-Path $PSScriptRoot "..\static\index.html"
if (Test-Path $indexPath) {
    $content = Get-Content $indexPath -Raw
    # Replace both the placeholder and any existing semantic version
    $newContent = $content -replace 'v=AUTO_VERSION|v=\d+\.\d+\.\d+', "v=$versionPlain"
    
    if (-not $DryRun) {
        Set-Content $indexPath $newContent -NoNewline
        Write-Success "Updated index.html to v=$versionPlain"
    } else {
        Write-Info "[DryRun] Would update index.html to v=$versionPlain"
    }
} else {
    Write-Warn "index.html not found at $indexPath"
}

# --- Tests ---

if (-not $SkipTests) {
    Write-Step "Running unit tests"

    $pythonExe = $null
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:ProgramFiles\Python312\python.exe",
        "$env:ProgramFiles\Python311\python.exe",
        "python3",
        "python"
    )
    foreach ($candidate in $candidates) {
        $found = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($found) {
            $pythonExe = $found.Source
            break
        }
    }

    if ($pythonExe) {
        & $pythonExe -m unittest tests.test_analysis -v
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Tests failed. Use -SkipTests to bypass (not recommended)."
            exit 1
        }
        Write-Success "Tests passed"
    } else {
        Write-Warn "Python not found - skipping local tests. CI will run them."
    }
} else {
    Write-Warn "Tests skipped via -SkipTests"
}

# --- Dry-run bailout ---

if ($DryRun) {
    Write-Step "DRY RUN - no changes made"
    Write-Info "Version that would be created: $version"
    Write-Info "Would push to: $Remote/$branch"
    $elapsed = [Math]::Round(((Get-Date) - $script:StartTime).TotalSeconds, 1)
    Write-Info "Took ${elapsed}s"
    exit 0
}

# --- Staging & commit ---

$hasChanges = (git status --porcelain).Length -gt 0

if ($hasChanges) {
    Write-Step "Staging changes"
    git add -A
    Write-Info "Changed files:"
    git diff --cached --name-only | ForEach-Object { Write-Info "  $_" }

    Write-Step "Creating commit"
    git commit -m $Message
    Write-Success "Commit created"
} else {
    Write-Info "No local changes to commit - creating tag on current HEAD"
}

# --- Tag & push ---

Write-Step "Creating tag $version"
git tag -a $version -m $Message
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to create tag."
    exit 1
}
Write-Success "Tag $version created"

Write-Step "Pushing to $Remote"
git push -u $Remote $branch
if ($LASTEXITCODE -ne 0) {
    Write-Error "Push failed. Tag $version exists locally but was not pushed."
    exit 1
}
Write-Success "Branch pushed"

git push $Remote $version
if ($LASTEXITCODE -ne 0) {
    Write-Error "Tag push failed. Run: git push $Remote $version"
    exit 1
}
Write-Success "Tag $version pushed"

# --- Summary ---

$elapsed = [Math]::Round(((Get-Date) - $script:StartTime).TotalSeconds, 1)
Write-Host "===========================================" -ForegroundColor Green
Write-Host "  Published $version" -ForegroundColor Green
Write-Host "  Image: ghcr.io/virgooooox/ota-analyzor:$versionPlain" -ForegroundColor Green
Write-Host "  Took: ${elapsed}s" -ForegroundColor Green
Write-Host "===========================================" -ForegroundColor Green
Write-Host ""
Write-Host "GitHub Actions build" -ForegroundColor DarkGray
