"""Fake Homebrew, confined to adjacent temporary state, logs and test tools."""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any


def main() -> int:
    root = Path(__file__).parent
    state_path = root / "state.json"
    state: dict[str, Any] = json.loads(state_path.read_text())
    args = sys.argv[1:]
    with (root / "calls.jsonl").open("a") as stream:
        stream.write(
            json.dumps(
                {
                    "args": args,
                    "env": {
                        name: value
                        for name, value in os.environ.items()
                        if name.startswith("HOMEBREW_NO_")
                    },
                }
            )
            + "\n"
        )
    if state.get("sleep"):
        time.sleep(state["sleep"])
    if state.get("fail") == args[0]:
        print("controlled brew failure", file=sys.stderr)
        return 7
    if args[0] == "--version":
        print("Homebrew 5.0.0")
    elif args[0] == "list":
        kind = "formula" if "--formula" in args else "cask"
        print(state.get("output", "\n".join(state.get(kind, []))))
    elif args[0] == "install":
        lock = root / "install.lock"
        try:
            lock.touch(exist_ok=False)
        except FileExistsError:
            print("concurrent brew mutation", file=sys.stderr)
            return 9
        try:
            if state.get("gate"):
                (root / "started").touch()
                deadline = time.monotonic() + 5
                while not (root / "release").exists():
                    if time.monotonic() >= deadline:
                        raise ValueError("independent action did not progress")
                    time.sleep(0.005)
            kind = args[1][2:]
            if state.get("fail_kind") == kind:
                return 8
            if not state.get("pretend"):
                state.setdefault(kind, []).extend(args[2:])
                state[kind].extend(state.get("dependencies", []))
                state_path.write_text(json.dumps(state))
                if state.get("produce"):
                    tool = root / "installed-tool"
                    tool.write_text("#!" + sys.executable + "\nprint('2.0.0')\n")
                    tool.chmod(0o755)
        finally:
            lock.unlink()
    else:
        return 10
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
