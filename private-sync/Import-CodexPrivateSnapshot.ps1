[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [string]$CodexHome,
    [string]$IdentityFile = (Join-Path ([System.Environment]::GetFolderPath('UserProfile')) '.codex-sync\age-identity.txt')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$restoreWhatIfPreference = $WhatIfPreference
$WhatIfPreference = $false

if ([string]::IsNullOrWhiteSpace($CodexHome)) {
    $CodexHome = Split-Path -Parent $PSScriptRoot
}

function Resolve-RequiredTool {
    param([Parameter(Mandatory)][string]$Name)

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    if ($Name -eq 'age' -and $env:LOCALAPPDATA) {
        $wingetPackages = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages'
        if (Test-Path -LiteralPath $wingetPackages) {
            $candidate = Get-ChildItem -LiteralPath $wingetPackages -Filter 'age.exe' -File -Recurse -ErrorAction SilentlyContinue |
                Where-Object { $_.FullName -match 'FiloSottile\.age_' } |
                Select-Object -First 1
            if ($candidate) {
                return $candidate.FullName
            }
        }
    }

    throw "Required tool '$Name' was not found."
}

function Get-RelativePathCompat {
    param(
        [Parameter(Mandatory)][string]$BasePath,
        [Parameter(Mandatory)][string]$ChildPath
    )

    $base = [System.IO.Path]::GetFullPath($BasePath).TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
    $child = [System.IO.Path]::GetFullPath($ChildPath)
    $baseUri = [System.Uri]$base
    $childUri = [System.Uri]$child
    return [System.Uri]::UnescapeDataString($baseUri.MakeRelativeUri($childUri).ToString()).Replace('/', [System.IO.Path]::DirectorySeparatorChar)
}

function Remove-ValidatedTempTree {
    param(
        [Parameter(Mandatory)][string]$TempRoot,
        [Parameter(Mandatory)][string]$TempBase
    )

    if (-not (Test-Path -LiteralPath $TempRoot)) {
        return
    }

    $resolvedRoot = [System.IO.Path]::GetFullPath($TempRoot)
    $resolvedBase = [System.IO.Path]::GetFullPath($TempBase).TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
    $leaf = Split-Path -Leaf $resolvedRoot
    if (-not $resolvedRoot.StartsWith($resolvedBase, [System.StringComparison]::OrdinalIgnoreCase) -or
        $leaf -notmatch '^codex-private-import-[0-9a-f-]{36}$') {
        throw "Refusing to remove unvalidated temporary path: $resolvedRoot"
    }

    Remove-Item -LiteralPath $resolvedRoot -Recurse -Force -WhatIf:$false
}

$codexRoot = [System.IO.Path]::GetFullPath($CodexHome)
if (-not (Test-Path -LiteralPath $IdentityFile -PathType Leaf)) {
    throw "age identity not found: $IdentityFile"
}

$age = Resolve-RequiredTool -Name 'age'
$tar = Resolve-RequiredTool -Name 'tar'
$manifestPath = Join-Path $PSScriptRoot 'snapshot-manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw 'snapshot-manifest.json was not found. Pull the repository before restoring.'
}

$manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
if ($manifest.format -ne 1 -or -not $manifest.parts) {
    throw 'Unsupported or incomplete snapshot manifest.'
}

$tempBase = [System.IO.Path]::GetTempPath()
$tempRoot = Join-Path $tempBase ("codex-private-import-{0}" -f [System.Guid]::NewGuid())
$encryptedPath = Join-Path $tempRoot 'codex-private.tar.gz.age'
$archivePath = Join-Path $tempRoot 'codex-private.tar.gz'
$payloadRoot = Join-Path $tempRoot 'payload'
New-Item -ItemType Directory -Path $payloadRoot -Force -WhatIf:$false | Out-Null

try {
    $combined = [System.IO.File]::Create($encryptedPath)
    try {
        foreach ($part in $manifest.parts) {
            if ($part.name -notmatch '^codex-private\.tar\.gz\.age\.part[0-9]{3,}$') {
                throw "Invalid snapshot part name: $($part.name)"
            }
            $partPath = Join-Path $PSScriptRoot $part.name
            if (-not (Test-Path -LiteralPath $partPath -PathType Leaf)) {
                throw "Missing snapshot part: $($part.name)"
            }
            $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $partPath).Hash.ToLowerInvariant()
            if ($actualHash -ne ([string]$part.sha256).ToLowerInvariant()) {
                throw "Snapshot part checksum failed: $($part.name)"
            }
            $partStream = [System.IO.File]::OpenRead($partPath)
            try {
                $partStream.CopyTo($combined)
            }
            finally {
                $partStream.Dispose()
            }
        }
    }
    finally {
        $combined.Dispose()
    }

    & $age -d -i $IdentityFile -o $archivePath $encryptedPath
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $archivePath)) {
        throw 'Snapshot decryption failed.'
    }

    & $tar -xzf $archivePath -C $payloadRoot
    if ($LASTEXITCODE -ne 0) {
        throw 'Snapshot extraction failed.'
    }

    $privateManifestPath = Join-Path $payloadRoot 'snapshot-files.json'
    if (-not (Test-Path -LiteralPath $privateManifestPath -PathType Leaf)) {
        throw 'The decrypted snapshot does not contain its private file manifest.'
    }
    $privateManifest = Get-Content -Raw -LiteralPath $privateManifestPath | ConvertFrom-Json
    $payloadPrefix = [System.IO.Path]::GetFullPath($payloadRoot).TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
    foreach ($record in $privateManifest.files) {
        $relative = [string]$record.path
        if ([string]::IsNullOrWhiteSpace($relative) -or [System.IO.Path]::IsPathRooted($relative) -or
            $relative.Split(@('\', '/'), [System.StringSplitOptions]::RemoveEmptyEntries) -contains '..') {
            throw "Unsafe path in the private snapshot manifest: $relative"
        }
        $payloadFile = [System.IO.Path]::GetFullPath((Join-Path $payloadRoot $relative))
        if (-not $payloadFile.StartsWith($payloadPrefix, [System.StringComparison]::OrdinalIgnoreCase) -or
            -not (Test-Path -LiteralPath $payloadFile -PathType Leaf)) {
            throw "Snapshot file is missing or outside the payload: $relative"
        }
        $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $payloadFile).Hash.ToLowerInvariant()
        if ($actualHash -ne ([string]$record.sha256).ToLowerInvariant()) {
            throw "Decrypted snapshot checksum failed: $relative"
        }
    }

    $WhatIfPreference = $restoreWhatIfPreference
    if (-not $PSCmdlet.ShouldProcess($codexRoot, 'Restore encrypted Codex credentials, sessions, attachments, and database snapshots')) {
        return
    }

    $databasePayloads = @(
        Get-ChildItem -Force -LiteralPath $payloadRoot -File -Filter '*.sqlite' -Recurse -ErrorAction SilentlyContinue
    )
    foreach ($database in $databasePayloads) {
        $relative = Get-RelativePathCompat -BasePath $payloadRoot -ChildPath $database.FullName
        $destination = Join-Path $codexRoot $relative
        if (Test-Path -LiteralPath $destination) {
            try {
                $lockTest = [System.IO.File]::Open($destination, 'Open', 'ReadWrite', 'None')
                $lockTest.Dispose()
            }
            catch {
                throw "A destination database is in use. Close Codex completely before restoring: $relative"
            }
        }
    }

    Get-ChildItem -Force -LiteralPath $payloadRoot | Where-Object { $_.Name -ne 'snapshot-files.json' } | ForEach-Object {
        $destination = Join-Path $codexRoot $_.Name
        if ($_.PSIsContainer) {
            New-Item -ItemType Directory -Path $destination -Force | Out-Null
            Get-ChildItem -Force -LiteralPath $_.FullName | Copy-Item -Destination $destination -Recurse -Force
        }
        else {
            Copy-Item -LiteralPath $_.FullName -Destination $destination -Force
        }
    }

    Write-Output "Encrypted Codex private snapshot restored into $codexRoot."
}
finally {
    Remove-ValidatedTempTree -TempRoot $tempRoot -TempBase $tempBase
}
