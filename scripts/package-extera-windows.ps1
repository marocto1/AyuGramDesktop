$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $repo
$destination = Join-Path $repo 'dist/ExteraGramDesktop'
New-Item -ItemType Directory -Force $destination | Out-Null
Copy-Item -LiteralPath out/Debug/AyuGram.exe -Destination $destination
foreach ($folder in @('extera_runtime', 'plugin_examples')) {
    Copy-Item -LiteralPath "out/Debug/$folder" -Destination $destination -Recurse -Force
}
$runtime = Join-Path $destination 'python'
New-Item -ItemType Directory -Force $runtime | Out-Null
$archive = Join-Path $repo 'dist/python-3.13.12-embed-amd64.zip'
Invoke-WebRequest 'https://www.python.org/ftp/python/3.13.12/python-3.13.12-embed-amd64.zip' -OutFile $archive
$expected = '76f238f606250c87c6beac75dccd35ee99070a13490555936abb6cb64ecce3d0'
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {
    throw 'Python archive SHA-256 mismatch.'
}
Expand-Archive -LiteralPath $archive -DestinationPath $runtime -Force
Add-Content -LiteralPath (Join-Path $runtime 'python313._pth') -Value '../extera_runtime' -Encoding ascii
Copy-Item -LiteralPath LICENSE,LEGAL -Destination $destination
Copy-Item -LiteralPath docs/extera-plugins.md -Destination (Join-Path $destination 'PLUGINS.md')
Copy-Item -LiteralPath build-logs/api-mode.txt -Destination $destination
$smokeRoot = Join-Path $repo 'dist/runtime-smoke-state'
$request = '{"op":"list","id":1}' + "`n" + '{"op":"shutdown","id":2}'
$responses = $request | & (Join-Path $runtime 'python.exe') -u -B (Join-Path $destination 'extera_runtime/host.py') --root $smokeRoot
if ($LASTEXITCODE -ne 0) { throw 'Bundled Python smoke test failed.' }
$parsed = @($responses | ForEach-Object { $_ | ConvertFrom-Json })
if ($parsed.Count -ne 2 -or @($parsed | Where-Object { -not $_.ok }).Count) {
    throw 'Bundled Python protocol smoke test failed.'
}
Get-ChildItem -LiteralPath $destination -File -Recurse | ForEach-Object {
    $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    "$hash  $([IO.Path]::GetRelativePath($destination, $_.FullName))"
} | Set-Content -LiteralPath (Join-Path $destination 'SHA256SUMS.txt') -Encoding utf8
Write-Output "Verified portable package: $destination"
