[CmdletBinding()]
param(
    [string]$CodexHome,
    [string]$RecipientFile,
    [ValidateRange(5, 90)]
    [int]$PartSizeMiB = 45
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($CodexHome)) {
    $CodexHome = Split-Path -Parent $PSScriptRoot
}
if ([string]::IsNullOrWhiteSpace($RecipientFile)) {
    $RecipientFile = Join-Path $PSScriptRoot 'recipient.txt'
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
        $leaf -notmatch '^codex-private-export-[0-9a-f-]{36}$') {
        throw "Refusing to remove unvalidated temporary path: $resolvedRoot"
    }

    Remove-Item -LiteralPath $resolvedRoot -Recurse -Force
}

$codexRoot = [System.IO.Path]::GetFullPath($CodexHome)
if (-not (Test-Path -LiteralPath (Join-Path $codexRoot '.git'))) {
    throw "CodexHome is not the expected Git repository: $codexRoot"
}

$age = Resolve-RequiredTool -Name 'age'
$python = Resolve-RequiredTool -Name 'python'
$tar = Resolve-RequiredTool -Name 'tar'

if (-not (Test-Path -LiteralPath $RecipientFile -PathType Leaf)) {
    throw "Recipient file not found: $RecipientFile"
}
$recipient = (Get-Content -Raw -LiteralPath $RecipientFile).Trim()
if ($recipient -notmatch '^age1[0-9a-z]+$') {
    throw 'The recipient file does not contain a valid age recipient.'
}

$tempBase = [System.IO.Path]::GetTempPath()
$tempRoot = Join-Path $tempBase ("codex-private-export-{0}" -f [System.Guid]::NewGuid())
$payloadRoot = Join-Path $tempRoot 'payload'
$archivePath = Join-Path $tempRoot 'codex-private.tar.gz'
$encryptedPath = Join-Path $tempRoot 'codex-private.tar.gz.age'
$partsRoot = Join-Path $tempRoot 'parts'
$outputRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)

New-Item -ItemType Directory -Path $payloadRoot -Force | Out-Null
New-Item -ItemType Directory -Path $partsRoot -Force | Out-Null

try {
    $relativeItems = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($relative in @(
        'auth.json',
        'secrets',
        '.sandbox-secrets',
        'tokens',
        'credentials',
        'sessions',
        'archived_sessions',
        'attachments',
        'session_index.jsonl',
        'transcription-history.jsonl',
        'external_agent_session_imports.json'
    )) {
        [void]$relativeItems.Add($relative)
    }

    Get-ChildItem -Force -LiteralPath $codexRoot -ErrorAction Stop |
        Where-Object { $_.Name -match '(?i)(token|credential)' } |
        ForEach-Object { [void]$relativeItems.Add($_.Name) }

    foreach ($relative in $relativeItems) {
        $source = Join-Path $codexRoot $relative
        if (-not (Test-Path -LiteralPath $source)) {
            continue
        }

        $destination = Join-Path $payloadRoot $relative
        $destinationParent = Split-Path -Parent $destination
        New-Item -ItemType Directory -Path $destinationParent -Force | Out-Null
        Copy-Item -LiteralPath $source -Destination $destination -Recurse -Force
    }

    $databaseFiles = @(
        Get-ChildItem -Force -LiteralPath $codexRoot -File -Filter '*.sqlite' -ErrorAction SilentlyContinue
    )
    $sqliteDirectory = Join-Path $codexRoot 'sqlite'
    if (Test-Path -LiteralPath $sqliteDirectory) {
        $databaseFiles += @(
            Get-ChildItem -Force -LiteralPath $sqliteDirectory -File -Filter '*.sqlite' -Recurse -ErrorAction SilentlyContinue
        )
    }

    $backupCode = @'
import sqlite3
import sys

source_path, destination_path = sys.argv[1], sys.argv[2]
source = sqlite3.connect('file:' + source_path.replace('\\', '/') + '?mode=ro', uri=True)
destination = sqlite3.connect(destination_path)
try:
    source.backup(destination)
finally:
    destination.close()
    source.close()
'@

    foreach ($database in $databaseFiles) {
        $relative = Get-RelativePathCompat -BasePath $codexRoot -ChildPath $database.FullName
        $destination = Join-Path $payloadRoot $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
        & $python -c $backupCode $database.FullName $destination
        if ($LASTEXITCODE -ne 0) {
            throw "SQLite backup failed for $relative"
        }
    }

    $payloadFiles = @(
        Get-ChildItem -Force -LiteralPath $payloadRoot -File -Recurse | ForEach-Object {
            [ordered]@{
                path = Get-RelativePathCompat -BasePath $payloadRoot -ChildPath $_.FullName
                size = $_.Length
                sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()
            }
        }
    )
    $privateManifest = [ordered]@{
        format = 1
        created_utc = [System.DateTime]::UtcNow.ToString('o')
        file_count = $payloadFiles.Count
        files = $payloadFiles
    }
    $privateManifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $payloadRoot 'snapshot-files.json') -Encoding UTF8

    & $tar -czf $archivePath -C $payloadRoot '.'
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $archivePath)) {
        throw 'Failed to create the compressed snapshot archive.'
    }

    & $age -r $recipient -o $encryptedPath $archivePath
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $encryptedPath)) {
        throw 'Failed to encrypt the snapshot archive.'
    }

    $partSize = [int64]$PartSizeMiB * 1MB
    $buffer = New-Object byte[] (4MB)
    $inputStream = [System.IO.File]::OpenRead($encryptedPath)
    $partRecords = @()
    try {
        $partNumber = 1
        while ($inputStream.Position -lt $inputStream.Length) {
            $partName = 'codex-private.tar.gz.age.part{0:D3}' -f $partNumber
            $partPath = Join-Path $partsRoot $partName
            $outputStream = [System.IO.File]::Create($partPath)
            try {
                $remaining = $partSize
                while ($remaining -gt 0 -and $inputStream.Position -lt $inputStream.Length) {
                    $requested = [int][System.Math]::Min($buffer.Length, $remaining)
                    $read = $inputStream.Read($buffer, 0, $requested)
                    if ($read -le 0) { break }
                    $outputStream.Write($buffer, 0, $read)
                    $remaining -= $read
                }
            }
            finally {
                $outputStream.Dispose()
            }

            $partInfo = Get-Item -LiteralPath $partPath
            $partRecords += [ordered]@{
                name = $partName
                size = $partInfo.Length
                sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $partPath).Hash.ToLowerInvariant()
            }
            $partNumber++
        }
    }
    finally {
        $inputStream.Dispose()
    }

    $publicManifest = [ordered]@{
        format = 1
        created_utc = [System.DateTime]::UtcNow.ToString('o')
        encryption = 'age-x25519'
        compression = 'tar-gzip'
        recipient = $recipient
        parts = $partRecords
        restore_requires_codex_closed = $true
    }
    $publicManifestPath = Join-Path $partsRoot 'snapshot-manifest.json'
    $publicManifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $publicManifestPath -Encoding UTF8

    $oldParts = @(
        Get-ChildItem -Force -LiteralPath $outputRoot -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^codex-private\.tar\.gz\.age\.part[0-9]{3,}$' }
    )
    foreach ($oldPart in $oldParts) {
        Remove-Item -LiteralPath $oldPart.FullName -Force
    }
    $oldManifest = Join-Path $outputRoot 'snapshot-manifest.json'
    if (Test-Path -LiteralPath $oldManifest) {
        Remove-Item -LiteralPath $oldManifest -Force
    }

    Get-ChildItem -LiteralPath $partsRoot -File | Copy-Item -Destination $outputRoot -Force

    Write-Output ("Created {0} encrypted snapshot part(s) in {1}." -f $partRecords.Count, $outputRoot)
    Write-Output 'The plaintext staging directory has been removed. Review and commit only the encrypted parts, manifest, and scripts.'
}
finally {
    Remove-ValidatedTempTree -TempRoot $tempRoot -TempBase $tempBase
}
