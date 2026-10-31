[CmdletBinding()]
param([switch]$Apply, [switch]$RemoveReplaceableModels,
      [string]$ReportDirectory = 'docs/cleanup/2026-10-03')
$ErrorActionPreference = 'Stop'
$taskRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')).TrimEnd('\')
$taskPrefix = $taskRoot + '\'
function Assert-WorkspacePath([string]$Path) {
    $resolved = [IO.Path]::GetFullPath($Path)
    if (-not $resolved.StartsWith($taskPrefix, [StringComparison]::OrdinalIgnoreCase)) { throw "Outside workspace: $resolved" }
    $relative = $resolved.Substring($taskPrefix.Length)
    if ($relative -match '(^|\\)\.git(\\|$)') { throw "Git history is protected: $resolved" }
    $cursor = $resolved
    while ($cursor.Length -gt $taskRoot.Length) {
        if (Test-Path -LiteralPath $cursor) {
            if ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Link/reparse point is protected: $cursor" }
        }
        $cursor = Split-Path -Parent $cursor
    }
    return $resolved
}
$taskReport = Assert-WorkspacePath (Join-Path $taskRoot $ReportDirectory)
New-Item -ItemType Directory -Path $taskReport -Force | Out-Null
$taskTargets = [Collections.Generic.List[object]]::new()
function Add-Target([string]$Relative, [string]$Reason) {
    $absolute = Assert-WorkspacePath (Join-Path $taskRoot $Relative)
    if (Test-Path -LiteralPath $absolute) {
        $item = Get-Item -LiteralPath $absolute -Force
        $files = if ($item.PSIsContainer) { @(Get-ChildItem -LiteralPath $absolute -File -Recurse -Force) } else { @($item) }
        if ($item.PSIsContainer) { if (Get-ChildItem -LiteralPath $absolute -Directory -Recurse -Force | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint } | Select-Object -First 1) { throw "Target contains a reparse point: $absolute" } }
        $bytes = ($files | Measure-Object Length -Sum).Sum
        $taskTargets.Add([pscustomobject]@{ Path=$Relative; Bytes=[long]$bytes; Files=$files.Count; Reason=$Reason; Absolute=$absolute })
    }
}
Add-Target 'installer/ReflowStudio-1.0.0-Setup.exe' 'Obsolete generated native installer; rebuild with legacy packaging tools if required.'
Add-Target 'frontend/node_modules' 'Frontend development dependencies; npm ci restores them. Built UI retained.'
Add-Target 'build/windows-portable/Lib/site-packages/torch/lib/dnnl.lib' 'Static oneDNN compilation archive; runtime DLLs retained. Reinstall identical torch wheel before compiling extensions.'
# Import/static link archives are compiler inputs; inference loads retained DLLs.
$taskTorchLib = Join-Path $taskRoot 'build/windows-portable/Lib/site-packages/torch/lib'
if (Test-Path -LiteralPath $taskTorchLib) {
    foreach ($taskArchive in Get-ChildItem -LiteralPath $taskTorchLib -File -Filter '*.lib') {
        if ($taskArchive.Name -ne 'dnnl.lib') {
            Add-Target $taskArchive.FullName.Substring($taskPrefix.Length) 'Portable Torch compiler/link archive; runtime DLLs and development environment retained. Reinstall the matching Torch wheel before compiling extensions.'
        }
    }
}
Add-Target '.venv/Lib/site-packages/~umpy' 'Abandoned pip uninstall/upgrade directory; active numpy retained.'
Add-Target '.venv/Lib/site-packages/~umpy.libs' 'Abandoned pip uninstall/upgrade DLL directory; active numpy.libs retained.'
Add-Target 'core/Wav2Lip/temp_input.wav' 'Generated copy of input audio used by the Wav2Lip subprocess.'
Add-Target 'core/Wav2Lip/temp_input.mp4' 'Generated copy of input video used by the Wav2Lip subprocess.'
Add-Target 'core/Wav2Lip/temp_output.mp4' 'Generated intermediate Wav2Lip output; final user outputs retained.'
Add-Target 'temp' 'Disposable processing temporary directory.'
Add-Target 'core/Wav2Lip/temp' 'Disposable Wav2Lip processing temporary directory.'
Add-Target 'core/MuseTalk/temp' 'Disposable MuseTalk processing temporary directory.'
if ($RemoveReplaceableModels) {
    Add-Target 'build/windows-portable/Lib/site-packages/rvc_python/base_model/hubert_base.pt' 'Replaceable RVC HuBERT checkpoint; restored by RVC feature on first use.'
    Add-Target 'build/windows-portable/Lib/site-packages/rvc_python/base_model/rmvpe.pt' 'Replaceable RVC pitch checkpoint; restored by RVC feature on first use.'
    Add-Target 'build/windows-portable/Lib/site-packages/rvc_python/base_model/rmvpe.onnx' 'Replaceable RVC ONNX pitch checkpoint; restored by RVC feature on first use.'
    Add-Target 'models/_downloads' 'Interrupted Marketplace downloads and HF partial blobs; source URLs retained in registry/audit.'
    Add-Target 'models/translation' 'Replaceable M2M100 HF cache; existing translator restores on next use.'
    Add-Target 'models/xtts/default/model.pth' 'Replaceable XTTS checkpoint; restored on first TTS use.'
    Add-Target 'models/xtts/default/speakers_xtts.pth' 'Replaceable XTTS speaker embeddings; restored on first TTS use.'
    Add-Target 'core/MuseTalk/models' 'Replaceable MuseTalk v1/v1.5 and auxiliary weights; on-demand recovery fetches only v1.5.'
    Add-Target 'core/Wav2Lip/checkpoints/Wav2Lip_GAN.pth' 'Replaceable Wav2Lip GAN checkpoint; restored on first lip-sync use.'
    Add-Target 'gfpgan/weights/GFPGANv1.4.pth' 'Replaceable GFPGAN restoration checkpoint.'
    Add-Target 'gfpgan/weights/parsing_parsenet.pth' 'Replaceable face parsing checkpoint.'
    Add-Target 'gfpgan/weights/detection_Resnet50_Final.pth' 'Replaceable face detection checkpoint.'
    # Remove the root HuBERT only when an identical copy is retained in RVC.
    $hubert = Join-Path $taskRoot 'models/rvc/hubert_base.pt'
    $bundled = Join-Path $taskRoot 'build/windows-portable/Lib/site-packages/rvc_python/base_model/hubert_base.pt'
    if ((Test-Path -LiteralPath $hubert) -and (Test-Path -LiteralPath $bundled)) {
        if ((Get-FileHash -LiteralPath $hubert).Hash -eq (Get-FileHash -LiteralPath $bundled).Hash) {
            Add-Target 'models/rvc/hubert_base.pt' 'SHA256-identical duplicate of retained RVC package checkpoint.'
        }
    }
}
# Enumerate without following directory links. Do not traverse Git, audit files,
# or folders already selected above; this prevents overlap/double-counting.
$stack = [Collections.Generic.Stack[string]]::new()
$stack.Push($taskRoot)
while ($stack.Count -gt 0) {
    $directory = $stack.Pop()
    foreach ($item in Get-ChildItem -LiteralPath $directory -Directory -Force) {
        if ($item.Name -eq '.git' -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { continue }
        if ($item.FullName -eq $taskReport -or $taskTargets.Absolute -contains $item.FullName) { continue }
        if ($item.Name -in @('__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache')) {
            Add-Target $item.FullName.Substring($taskPrefix.Length) 'Disposable interpreter/tool cache; source and package metadata retained.'
        } else { $stack.Push($item.FullName) }
    }
}
$taskTargets | Select-Object Path,Bytes,Files,Reason | Export-Csv -LiteralPath (Join-Path $taskReport 'cleanup-plan.csv') -NoTypeInformation -Encoding utf8
$total = ($taskTargets | Measure-Object Bytes -Sum).Sum
Write-Output "Planned targets: $($taskTargets.Count); bytes: $total; GiB: $([math]::Round($total/1GB,3)); apply: $Apply"
if (-not $Apply) { return }
$taskRemoved = [Collections.Generic.List[object]]::new()
foreach ($target in $taskTargets) {
    $absolute = Assert-WorkspacePath $target.Absolute
    Remove-Item -LiteralPath $absolute -Recurse -Force
    $taskRemoved.Add([pscustomobject]@{Path=$target.Path;Bytes=$target.Bytes;Files=$target.Files;Reason=$target.Reason})
    # Persist each completed operation so an interruption still leaves a ledger.
    $taskRemoved | Export-Csv -LiteralPath (Join-Path $taskReport 'removed-targets.csv') -NoTypeInformation -Encoding utf8
}
New-Item -ItemType Directory -Path (Join-Path $taskRoot 'temp') -Force | Out-Null
Write-Output "Removed $($taskRemoved.Count) targets. Samples, outputs, Git, Python runtime DLLs and the built UI were preserved."



