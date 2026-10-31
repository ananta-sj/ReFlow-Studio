param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$workspaceRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$profileRoot = Join-Path $workspaceRoot 'runtime_profiles'
$profileBoundary = $profileRoot.TrimEnd('\') + '\'
$entries = @(Get-ChildItem -LiteralPath $profileRoot -Recurse -Force)
foreach ($entry in @((Get-Item -LiteralPath $profileRoot)) + $entries) {
    if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "Profile trim refuses reparse points: $($entry.FullName)"
    }
}
$caches = @($entries | Where-Object { $_.PSIsContainer -and $_.Name -eq '__pycache__' })
$staticBuildLibrary = Join-Path $profileRoot 'musetalk\Lib\site-packages\torch\lib\dnnl.lib'
$targets = @($caches.FullName)
if (Test-Path -LiteralPath $staticBuildLibrary) { $targets += $staticBuildLibrary }
foreach ($target in $targets) {
    $resolved = [IO.Path]::GetFullPath($target)
    if (-not $resolved.StartsWith($profileBoundary, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Profile trim escapes the owned runtime tree: $resolved"
    }
}
$files = @($entries | Where-Object {
    if ($_.PSIsContainer) { return $false }
    if ($_.FullName -eq $staticBuildLibrary) { return $true }
    return $_.FullName -match '\\__pycache__\\'
})
$receipt = [ordered]@{
    applied = [bool]$Apply
    reason = 'Owned optional-profile bytecode caches and the unused native-extension static build library; inference DLLs are retained.'
    bytes = ($files | Measure-Object -Property Length -Sum).Sum
    files = @($files | ForEach-Object { [ordered]@{ path=$_.FullName; bytes=$_.Length } })
    targets = $targets
}
$receiptPath = Join-Path $workspaceRoot 'docs\validation\2026-10-03-optional-runtime-trim.json'
$receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $receiptPath -Encoding utf8
if ($Apply) {
    foreach ($target in ($targets | Sort-Object { $_.Length } -Descending)) {
        if (-not (Test-Path -LiteralPath $target)) { continue }
        Remove-Item -LiteralPath $target -Recurse -Force
    }
}
Write-Output "Optional runtime trim: $($files.Count) files, $($receipt.bytes) bytes; applied=$([bool]$Apply)"
