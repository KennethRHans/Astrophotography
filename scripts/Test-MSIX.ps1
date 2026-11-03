# CI-only test: the certificate and package registration are removed afterwards.
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$package = Get-ChildItem 'msix-artifacts/development/*.msix' | Select-Object -First 1
if (-not $package) { throw 'Build the development MSIX first' }
$info = Get-Content 'msix-artifacts/development/BuildInfo.json' -Raw | ConvertFrom-Json
$tool = Get-ChildItem "${env:ProgramFiles(x86)}/Windows Kits/10/bin/*/x64/signtool.exe" | Sort-Object { [version]$_.Directory.Parent.Name } -Descending | Select-Object -First 1
if (-not $tool) { throw 'Windows SDK SignTool missing' }
$local = Join-Path (Get-Location) 'build/msix-local-test'
New-Item -ItemType Directory -Force $local | Out-Null
$signed = Join-Path $local 'Development-LocalTest.msix'
Copy-Item $package.FullName $signed -Force
$certificate = $null
$registered = $null
try {
    $certificate = New-SelfSignedCertificate -Type Custom -Subject $info.identity.publisher -KeyUsage DigitalSignature -CertStoreLocation 'Cert:/CurrentUser/My' -KeyAlgorithm RSA -KeyLength 2048 -HashAlgorithm SHA256 -NotAfter (Get-Date).AddDays(2) -TextExtension @('2.5.29.37={text}1.3.6.1.5.5.7.3.3')
    $public = Join-Path $local 'ci-public.cer'
    Export-Certificate -Cert $certificate -FilePath $public | Out-Null
    Import-Certificate -FilePath $public -CertStoreLocation 'Cert:/LocalMachine/TrustedPeople' | Out-Null
    & $tool.FullName sign /fd SHA256 /s My /sha1 $certificate.Thumbprint $signed
    if ($LASTEXITCODE -ne 0) { throw 'CI test signing failed' }
    & $tool.FullName verify /pa $signed
    if ($LASTEXITCODE -ne 0) { throw 'CI test signature verification failed' }
    Add-AppxPackage -Path $signed -ForceApplicationShutdown
    $registered = Get-AppxPackage -Name $info.identity.name
    if (-not $registered) { throw 'MSIX installation did not register the package' }
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
[ComImport, Guid("2e941141-7f97-4756-ba1d-9decde894a3d"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IAppActivationManager {
 [PreserveSig] int ActivateApplication([MarshalAs(UnmanagedType.LPWStr)] string id, [MarshalAs(UnmanagedType.LPWStr)] string arguments, uint options, out uint pid);
 [PreserveSig] int ActivateForFile(IntPtr id, IntPtr array, IntPtr verb, out uint pid);
 [PreserveSig] int ActivateForProtocol(IntPtr id, IntPtr array, out uint pid);
}
public static class StoreTestLauncher {
 public static uint Launch(string id, string arguments) {
  object instance = Activator.CreateInstance(Type.GetTypeFromCLSID(new Guid("45BA127D-10A8-46EA-8AB7-56EA9078943C")));
  var manager = (IAppActivationManager)instance;
  uint pid;
  int result = manager.ActivateApplication(id, arguments, 0, out pid);
  Marshal.ThrowExceptionForHR(result);
  Marshal.ReleaseComObject(instance);
  return pid;
 }
}
'@
    foreach ($pass in 1,2) {
        $resultPath = Join-Path $local "activation-$pass.json"
        $theme = if ($pass -eq 1) { '--smoke-write-theme Light' } else { '--smoke-expect-theme Light' }
        $arguments = "--smoke-test --require-package-identity $theme --smoke-result `"$resultPath`""
        $processId = [StoreTestLauncher]::Launch(($registered.PackageFamilyName + '!App'), $arguments)
        $deadline = (Get-Date).AddSeconds(120)
        while (-not (Test-Path $resultPath) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 250 }
        if (-not (Test-Path $resultPath)) {
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
            throw 'MSIX activation test did not produce a success result'
        }
        $result = Get-Content $resultPath -Raw | ConvertFrom-Json
        if (-not $result.ok -or -not $result.package_identity) { throw 'MSIX package identity or processing check failed' }
        $running = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($running -and -not $running.WaitForExit(30000)) { $running.Kill(); throw 'MSIX test app did not exit' }
    }
    @{ status='passed'; installation=$true; package_identity=$true; processing_project_export=$true; settings_persisted=$true; gpu_hardware_tested=$false } | ConvertTo-Json | Set-Content 'msix-artifacts/development/RuntimeValidation.json'
} finally {
    if ($registered) { Remove-AppxPackage -Package $registered.PackageFullName -ErrorAction Continue }
    if ($certificate) {
        Remove-Item ("Cert:/LocalMachine/TrustedPeople/" + $certificate.Thumbprint) -ErrorAction SilentlyContinue
        Remove-Item ("Cert:/CurrentUser/My/" + $certificate.Thumbprint) -ErrorAction SilentlyContinue
    }
    Remove-Item $local -Recurse -Force -ErrorAction SilentlyContinue
}
