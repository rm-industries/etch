#!/usr/bin/env bash
set -euo pipefail

engine_root=$(cd "$1" && pwd -P)
consumer_root=$(cd "$2" && pwd -P)
selection=$3

case "$selection" in
  profile) set -- --profile developer ;;
  git) set -- git ;;
  *) echo "Unknown selection: $selection" >&2; exit 2 ;;
esac

# The template pins a released engine. Substitute this checkout to verify the
# candidate engine against the real starter without changing its Git pin.
mkdir -p "$consumer_root/vendor/etch"
cp "$engine_root/etch" "$consumer_root/vendor/etch/etch"
cp -R "$engine_root/etchlib" "$consumer_root/vendor/etch/etchlib"

export HOME
HOME=$(mktemp -d)
trap 'rm -rf "$HOME"' EXIT
cd "$consumer_root"

./etch --version
./etch > /dev/null
test ! -e "$HOME/.gitconfig"
./etch plan "$@" > /dev/null
./etch doctor "$@" > /dev/null
./etch apply "$@" > /dev/null
test -L "$HOME/.gitconfig"
test "$(readlink "$HOME/.gitconfig")" = "$consumer_root/modules/git/files/gitconfig"
test "$(git config --file "$HOME/.gitconfig" --get init.defaultBranch)" = main

./etch apply "$@" > "$HOME/second-apply.log"
if grep -Eq '^(CHANGED|FAILED|BLOCKED) ' "$HOME/second-apply.log"; then
  cat "$HOME/second-apply.log" >&2
  echo 'Second apply changed the declarative starter state.' >&2
  exit 1
fi
