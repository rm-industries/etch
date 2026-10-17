# Fresh-machine bootstrap; existing checkouts are deliberately never updated.
$ErrorActionPreference = 'Stop'
# Handle native exit codes explicitly, including when the caller enables PS7 native errors.
$PSNativeCommandUseErrorActionPreference = $false
# Owners: set your generated repository URL, destination, and optional module here.
$repository = ''
$destination = if ($env:DOTFILES_DIR) { $env:DOTFILES_DIR } else { Join-Path $HOME '.dotfiles' }
$module = ''
$noModule = $false

function Fail([int]$code, [string]$message) {
    [Console]::Error.WriteLine("Etch consumer installer: $message")
    exit $code
}

function RepositoryIdentity([string]$url) {
    return ($url.TrimEnd('/') -creplace '^git@github\.com:', 'https://github.com/' -creplace '\.git$', '')
}

for ($i = 0; $i -lt $args.Count; $i++) {
    switch ($args[$i]) {
        '--repo' {
            $i++
            if ($i -ge $args.Count -or !$args[$i] -or $args[$i].StartsWith('-')) {
                Fail 2 '--repo requires a repository URL.'
            }
            $repository = $args[$i]
        }
        '--module' {
            $i++
            if ($i -ge $args.Count -or $args[$i] -notmatch '^[a-zA-Z0-9_][a-zA-Z0-9_-]*$') {
                Fail 2 '--module requires a valid name.'
            }
            $module = $args[$i]
        }
        '--no-module' { $noModule = $true }
        { $_ -in '--help', '-h' } {
            Write-Output 'Usage: install.ps1 [--repo URL] [--module NAME] [--no-module]'
            Write-Output 'Set your generated repository URL in this script or pass --repo URL.'
            Write-Output 'Clone to DOTFILES_DIR (default: ~/.dotfiles); no module runs by default.'
            Write-Output '--no-module always takes precedence. Existing checkouts are untouched.'
            exit 0
        }
        default { Fail 2 "Unknown argument: $($args[$i])" }
    }
}
if (!$repository -or $repository.StartsWith('-')) { Fail 2 'Set the generated repository URL or use --repo URL.' }
if ($noModule) { $module = '' }
if ($module -and $module -notmatch '^[a-zA-Z0-9_][a-zA-Z0-9_-]*$') { Fail 2 'Invalid default module name.' }
if (!(Get-Command git -ErrorAction SilentlyContinue)) { Fail 127 'Git is required; install it and retry.' }

if (Get-Item -LiteralPath $destination -Force -ErrorAction SilentlyContinue) {
    if (Test-Path -LiteralPath (Join-Path $destination '.git')) {
        $origin = & git -C $destination remote get-url origin 2>$null
        if ($LASTEXITCODE -eq 0 -and $origin -and (RepositoryIdentity $origin) -ceq (RepositoryIdentity $repository)) {
            & git -C $destination rev-parse --is-inside-work-tree 2>$null | Out-Null
            if ($LASTEXITCODE -ne 0) { Fail 1 "Invalid checkout at $destination; it was not changed." }
            Write-Output "Checkout already exists at $destination; nothing changed."
            exit 0
        }
    }
    Fail 1 "Destination is occupied by an unrelated file or directory: $destination"
}

if ($module) {
    if (!(Get-Command python -ErrorAction SilentlyContinue)) {
        Fail 127 'Python 3.9+ is required to run Etch; install it or use --no-module.'
    }
    & python -S -c 'import sys; sys.exit(sys.version_info < (3, 9))'
    if ($LASTEXITCODE -ne 0) { Fail $LASTEXITCODE 'Python 3.9+ is required to run Etch.' }
}

$gitPrompt = $env:GIT_TERMINAL_PROMPT
try {
    $env:GIT_TERMINAL_PROMPT = '0'
    & git clone -- $repository $destination
    if ($LASTEXITCODE -ne 0) {
        Fail $LASTEXITCODE "Clone failed. Any partial destination was retained at $destination; inspect it before retrying."
    }
    & git -C $destination submodule update --init --recursive
    if ($LASTEXITCODE -ne 0) {
        Fail $LASTEXITCODE "Submodule initialization failed at $destination. Repair it manually; reruns do not update existing checkouts."
    }
} finally {
    $env:GIT_TERMINAL_PROMPT = $gitPrompt
}
if ($module) {
    $engine = Join-Path $destination 'vendor/etch/etch'
    & python -S $engine apply $module --repo $destination
    if ($LASTEXITCODE -ne 0) {
        Fail $LASTEXITCODE "Etch module $module failed. Checkout retained at $destination; rerun Etch directly after resolving the error."
    }
}
Write-Output "Checkout installed at $destination."
exit 0
