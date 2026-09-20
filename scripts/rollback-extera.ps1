param(
    [Parameter(Mandatory = $true)][string]$Manifest,
    [string]$Root = (Split-Path $PSScriptRoot -Parent),
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'
$rootPath = [IO.Path]::GetFullPath($Root).TrimEnd([IO.Path]::DirectorySeparatorChar)
$prefix = $rootPath + [IO.Path]::DirectorySeparatorChar
$manifestPath = (Resolve-Path -LiteralPath $Manifest).Path
$backupRoot = Join-Path (Split-Path $manifestPath -Parent) 'baseline'
$data = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($data.schema -ne 1) { throw 'Unsupported rollback manifest.' }
$entries = @()
foreach ($file in $data.files) {
    if ([IO.Path]::IsPathRooted($file.path)) { throw 'Manifest paths must be relative.' }
    $target = [IO.Path]::GetFullPath((Join-Path $rootPath $file.path))
    if (-not $target.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Path escapes the selected project: $target"
    }
    $ancestor = $target
    while ($ancestor -and $ancestor.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        if ((Test-Path -LiteralPath $ancestor) -and
            ((Get-Item -LiteralPath $ancestor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "Reparse points are not supported: $ancestor"
        }
        $ancestor = Split-Path $ancestor -Parent
    }
    if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
        throw "Expected modified file is missing: $target"
    }
    if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.modified_sha256) {
        throw "File has newer edits; rollback stopped: $target"
    }
    $source = $null
    if ($file.baseline_sha256) {
        $source = [IO.Path]::GetFullPath((Join-Path $backupRoot $file.path))
        $backupPrefix = [IO.Path]::GetFullPath($backupRoot) + [IO.Path]::DirectorySeparatorChar
        if (-not $source.StartsWith($backupPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Invalid backup path.'
        }
        if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.baseline_sha256) {
            throw "Baseline hash mismatch: $source"
        }
    }
    $entries += [PSCustomObject]@{ Target = $target; Source = $source; Hash = $file.baseline_sha256 }
}
if (-not $Apply) {
    Write-Output "CHECK OK: $($entries.Count) feature files match the manifest; no files changed."
    exit 0
}
foreach ($entry in $entries) {
    if ($entry.Source) {
        [IO.File]::WriteAllBytes($entry.Target, [IO.File]::ReadAllBytes($entry.Source))
        if ((Get-FileHash -LiteralPath $entry.Target -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Hash) {
            throw "Restored file verification failed: $($entry.Target)"
        }
    } else {
        Remove-Item -LiteralPath $entry.Target
        if (Test-Path -LiteralPath $entry.Target) { throw "File still exists: $($entry.Target)" }
    }
}
Write-Output "ROLLBACK OK: $($entries.Count) feature files restored to the captured upstream state."
