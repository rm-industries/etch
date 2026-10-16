$ErrorActionPreference = 'Stop'

# Keep the user-local launcher directory discoverable without changing machine PATH.
$bin = Join-Path $env:USERPROFILE '.local\bin'
$stateDirectory = Join-Path $env:USERPROFILE '.local\state\etch'
$marker = Join-Path $stateDirectory 'windows-user-path'
$key = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey('Environment')
try {
    # Preserve unexpanded references (such as %USERPROFILE%) and the Registry type.
    $userPath = [string]$key.GetValue('Path', '', [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
    foreach ($entry in ($userPath -split ';')) {
        $expanded = [Environment]::ExpandEnvironmentVariables($entry.Trim().Trim('"'))
        if ($expanded.TrimEnd('\') -ieq $bin.TrimEnd('\')) {
            New-Item -ItemType Directory -Force $stateDirectory | Out-Null
            New-Item -ItemType File -Force $marker | Out-Null
            exit 0
        }
    }
    $kind = [Microsoft.Win32.RegistryValueKind]::ExpandString
    if ($key.GetValueNames() -contains 'Path') {
        $kind = $key.GetValueKind('Path')
        if ($kind -notin @([Microsoft.Win32.RegistryValueKind]::String, [Microsoft.Win32.RegistryValueKind]::ExpandString)) {
            throw 'User PATH must be a string; it was not changed.'
        }
    }
    $separator = if ($userPath -and !$userPath.EndsWith(';')) { ';' } else { '' }
    $key.SetValue('Path', "$userPath$separator$bin", $kind)
} finally {
    $key.Dispose()
}

# Notify desktop applications so newly opened terminals inherit the updated PATH.
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class EtchEnvironment {
    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern IntPtr SendMessageTimeout(IntPtr window, uint message,
        UIntPtr wParam, string lParam, uint flags, uint timeout, out UIntPtr result);
}
'@
$result = [UIntPtr]::Zero
[void][EtchEnvironment]::SendMessageTimeout([IntPtr]0xffff, 0x001a,
    [UIntPtr]::Zero, 'Environment', 0x0002, 1000, [ref]$result)
New-Item -ItemType Directory -Force $stateDirectory | Out-Null
New-Item -ItemType File -Force $marker | Out-Null
Write-Output 'Added ~/.local/bin to user PATH. Open a new terminal to use etch.'
