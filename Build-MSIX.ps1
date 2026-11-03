[CmdletBinding()]
param([string]$IdentityFile, [switch]$TestIdentity, [string]$Python = 'python')
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if ([bool]$IdentityFile -eq [bool]$TestIdentity) { throw 'Specify either -IdentityFile with Partner Center values, or -TestIdentity for a development package.' }
function Find-SdkTool([string]$Name) {
    $root = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits/10/bin'
    $tool = Get-ChildItem "$root/*/x64/$Name" | Sort-Object { [version]$_.Directory.Parent.Name } -Descending | Select-Object -First 1
    if (-not $tool) { throw "Install the Windows 10/11 SDK: missing $Name" }
    return $tool.FullName
}
$makeappx = Find-SdkTool 'makeappx.exe'
$makepri = Find-SdkTool 'makepri.exe'
$purpose = if ($TestIdentity) { 'development' } else { 'submission' }
$stage = Join-Path $PSScriptRoot "build/msix/$purpose"
if (Test-Path $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
$arguments = @('scripts/prepare_msix.py','--payload','dist/EasyAstroStudio','--output',$stage)
if ($TestIdentity) { $arguments += '--test-identity' } else { $arguments += @('--identity',(Resolve-Path $IdentityFile).Path) }
& $Python @arguments
if ($LASTEXITCODE -ne 0) { throw 'MSIX staging failed' }
$configuration = Join-Path $PSScriptRoot 'build/msix/priconfig.xml'
& $makepri createconfig /cf $configuration /dq en-US /o
if ($LASTEXITCODE -ne 0) { throw 'MakePRI configuration failed' }
& $makepri new /pr $stage /cf $configuration /of (Join-Path $stage 'resources.pri') /o
if ($LASTEXITCODE -ne 0) { throw 'MakePRI indexing failed' }
$version = (& $Python -c 'from app_version import VERSION; print(VERSION)').Trim()
$output = Join-Path $PSScriptRoot "msix-artifacts/$purpose"
New-Item -ItemType Directory -Force $output | Out-Null
$label = if ($TestIdentity) { 'Development-UNSIGNED' } else { 'Store-UNSIGNED' }
$package = Join-Path $output "EasyAstroStudio-$version-x64-$label.msix"
& $makeappx pack /d $stage /p $package /h SHA256 /o
if ($LASTEXITCODE -ne 0) { throw 'MakeAppx validation/packaging failed' }
Copy-Item (Join-Path $stage 'BuildInfo.json') $output -Force
Write-Output "Unsigned MSIX created: $package"
Write-Output 'Microsoft signs an accepted Store submission. This unsigned file is not a normal public installer.'
