$ErrorActionPreference = 'Stop'

# Follow the user-local launcher link back to its checkout, including relative targets.
$launcher = Get-Item -LiteralPath $PSCommandPath -Force
$linkCount = 0
while ($launcher.LinkType -eq 'SymbolicLink') {
    $linkCount++
    if ($linkCount -gt 40) {
        throw 'Etch launcher: symlink cycle or chain exceeds 40 links.'
    }
    $target = @($launcher.Target)[0]
    if (![IO.Path]::IsPathRooted($target)) {
        $target = Join-Path $launcher.DirectoryName $target
    }
    $launcher = Get-Item -LiteralPath $target -Force
}

$root = $launcher.DirectoryName
$engine = Join-Path $root 'vendor\etch\etch'
if (!(Test-Path -LiteralPath $engine -PathType Leaf)) {
    throw 'Initialize Etch first: git submodule update --init vendor/etch'
}
if (!(Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'Etch requires Python 3.9 or newer on PATH.'
}
$etchArguments = $args
if ($etchArguments.Count -eq 0) {
    $etchArguments = @('plan', '--profile', 'developer')
}


# Probe with Python, matching the provider's unprivileged Windows symlink API.
$symlinkProbe = @'
import os
import sys
import tempfile
from pathlib import Path

try:
    with tempfile.TemporaryDirectory(prefix='etch-symlink-check-') as temporary:
        root = Path(temporary)
        (root / 'file').touch()
        (root / 'directory').mkdir()
        for name, directory in (('file', False), ('directory', True)):
            os.symlink(str(root / name), str(root / (name + '-link')),
                       target_is_directory=directory)
except OSError as exc:
    print('Etch launcher: this session cannot create symbolic links: {}. '
          'Enable Windows Developer Mode for non-admin use, then retry from '
          'your normal terminal. Etch will not elevate or change system settings.'
          .format(exc), file=sys.stderr)
    raise SystemExit(1)
'@
if ($etchArguments[0] -eq 'apply' -and $etchArguments -notcontains '--help' -and $etchArguments -notcontains '-h') {
    & python -S -c $symlinkProbe
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

Push-Location -LiteralPath $root
try {
    & python -S $engine @etchArguments
    $exitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $exitCode
