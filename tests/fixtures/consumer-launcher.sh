#!/bin/sh
# Run the pinned engine from this consumer repository.
set -e

if ! command -v python3 >/dev/null 2>&1; then
    echo "Etch requires Python 3.9 or newer." >&2
    exit 1
fi

# Follow launcher links without GNU-only readlink -f or changing arguments.
launcher=$0
case "$launcher" in
    */*) ;;
    *) launcher=$(command -v "$launcher") ;;
esac
case "$launcher" in
    /*) ;;
    *) launcher="$(pwd -P)/$launcher" ;;
esac
link_count=0
while [ -L "$launcher" ]; do
    link_count=$((link_count + 1))
    if [ "$link_count" -gt 40 ]; then
        echo "Etch launcher: symlink cycle or chain exceeds 40 links." >&2
        exit 1
    fi
    link_dir=$(CDPATH= cd -- "${launcher%/*}" && pwd -P)
    target=$(readlink "$launcher")
    case "$target" in
        /*) launcher=$target ;;
        *) launcher="$link_dir/$target" ;;
    esac
done
if [ ! -f "$launcher" ]; then
    echo "Etch launcher: missing or dangling launcher: $launcher" >&2
    exit 1
fi
CDPATH= cd -- "${launcher%/*}"

# This path matches the engine submodule declared in .gitmodules. Normally leave
# it unchanged. If you move the submodule, update both this check and the exec
# path at the end of this file to match its new location.
if [ ! -f vendor/etch/etch ]; then
    echo "Etch source is missing from vendor/etch." >&2
    echo "Run: git submodule update --init --recursive" >&2
    exit 1
fi

# Choose what a bare ./etch does. "$#" counts the supplied arguments; when
# there are none, "set --" supplies the default arguments for the exec below.
# The current default previews the developer profile without applying changes.
#
# Consumer changes (replace the set -- line below with ONE of these):
#   set -- plan --profile workstation   # Use profiles/workstation.conf.
#   set -- apply --profile developer    # Make bare ./etch apply changes.
#   set -- plan git vim                 # Select modules/git and modules/vim.
# Create the referenced profile/modules first. These defaults apply only when
# no arguments are given: ./etch doctor --profile developer still runs doctor.
if [ "$#" -eq 0 ]; then
    set -- plan --profile developer
fi

# Forward the selected arguments unchanged ("$@" preserves argument boundaries)
# and return Etch's exit status. -S keeps startup independent of site packages;
# no pip install or virtual environment is needed for the pinned engine.
exec python3 -S vendor/etch/etch "$@"
