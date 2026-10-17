#!/bin/sh
# Fresh-machine bootstrap; existing checkouts are deliberately never updated.
set -u

# Owners: set your generated repository URL, destination, and optional module here.
repository=''
destination=${DOTFILES_DIR:-"$HOME/.dotfiles"}
module=''
no_module=false

die() {
    printf 'Etch consumer installer: %s\n' "$2" >&2
    exit "$1"
}

repository_identity() {
    value=${1%/}
    case "$value" in
        git@github.com:*) value="https://github.com/${value#git@github.com:}" ;;
    esac
    printf '%s' "${value%.git}"
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --repo)
            [ "$#" -ge 2 ] || die 2 '--repo requires a repository URL.'
            repository=$2
            case "$repository" in ''|-*) die 2 '--repo requires a repository URL.' ;; esac
            shift 2
            ;;
        --module)
            [ "$#" -ge 2 ] || die 2 '--module requires a name.'
            module=$2
            case "$module" in ''|-*|*[!a-zA-Z0-9_-]*) die 2 'Invalid module name.' ;; esac
            shift 2
            ;;
        --no-module) no_module=true; shift ;;
        --help|-h)
            printf '%s\n' 'Usage: install.sh [--repo URL] [--module NAME] [--no-module]' \
                'Set your generated repository URL in this script or pass --repo URL.' \
                'Clone to DOTFILES_DIR (default: ~/.dotfiles); no module runs by default.' \
                '--no-module always takes precedence. Existing checkouts are untouched.'
            exit 0
            ;;
        *) die 2 "Unknown argument: $1" ;;
    esac
done
case "$repository" in ''|-*) die 2 'Set the generated repository URL or use --repo URL.' ;; esac
[ "$no_module" = false ] || module=
case "$module" in -*|*[!a-zA-Z0-9_-]*) die 2 'Invalid default module name.' ;; esac
command -v git >/dev/null 2>&1 || die 127 'Git is required; install it and retry.'

if [ -e "$destination" ] || [ -L "$destination" ]; then
    if [ -d "$destination" ] && [ -e "$destination/.git" ]; then
        origin=$(git -C "$destination" remote get-url origin 2>/dev/null) || origin=
        if [ -n "$origin" ] && [ "$(repository_identity "$origin")" = "$(repository_identity "$repository")" ]; then
            git -C "$destination" rev-parse --is-inside-work-tree >/dev/null 2>&1 ||
                die 1 "Invalid checkout at $destination; it was not changed."
            printf 'Checkout already exists at %s; nothing changed.\n' "$destination"
            exit 0
        fi
    fi
    die 1 "Destination is occupied by an unrelated file or directory: $destination"
fi

if [ -n "$module" ]; then
    command -v python3 >/dev/null 2>&1 || die 127 'Python 3.9+ is required to run Etch; install it or use --no-module.'
    python3 -S -c 'import sys; sys.exit(sys.version_info < (3, 9))' ||
        die "$?" 'Python 3.9+ is required to run Etch.'
fi

GIT_TERMINAL_PROMPT=0 git clone -- "$repository" "$destination" ||
    die "$?" "Clone failed. Any partial destination was retained at $destination; inspect it before retrying."
GIT_TERMINAL_PROMPT=0 git -C "$destination" submodule update --init --recursive ||
    die "$?" "Submodule initialization failed at $destination. Repair it manually; reruns do not update existing checkouts."

if [ -n "$module" ]; then
    python3 -S "$destination/vendor/etch/etch" apply "$module" --repo "$destination" ||
        die "$?" "Etch module $module failed. Checkout retained at $destination; rerun Etch directly after resolving the error."
fi
printf 'Checkout installed at %s.\n' "$destination"
