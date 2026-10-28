"""File-backed npm double; no registry access or real global installs."""

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
    if sys.stdin.read():
        raise ValueError("stdin must be closed")
    with (root / "calls.jsonl").open("a") as stream:
        stream.write(json.dumps({"args": args, "cwd": os.getcwd()}) + "\n")
    if state.get("sleep"):
        time.sleep(state["sleep"])
    if args == ["--version"]:
        print("11.19.1")
        return 0
    if args[:2] == ["prefix", "--global"]:
        override = next(
            (arg.split("=", 1)[1] for arg in args if arg.startswith("--prefix=")), None
        )
        print(
            state.get(
                "prefix_output", override or state.get("prefix", str(root / "global"))
            )
        )
        return 0
    if args[:2] == ["ls", "--global"]:
        print(
            state.get(
                "output",
                json.dumps(
                    {
                        "name": "lib",
                        "dependencies": {
                            name: {"version": version, "overridden": False}
                            for name, version in state.get("packages", {}).items()
                        },
                    }
                ),
            )
        )
        return int(state.get("inventory_status", 0))
    if args[:2] != ["install", "--global"] or "--" not in args:
        print("unsupported invocation", file=sys.stderr)
        return 9
    lock = root / "install.lock"
    try:
        lock.touch(exist_ok=False)
    except FileExistsError:
        print("concurrent npm mutation", file=sys.stderr)
        return 9
    try:
        if state.get("gate"):
            (root / "started").touch()
            deadline = time.monotonic() + 5
            while not (root / "release").exists():
                if time.monotonic() > deadline:
                    raise ValueError("unrelated work did not progress")
                time.sleep(0.005)
        if not state.get("pretend"):
            specs = args[args.index("--") + 1 :]
            if not specs or any(not name.endswith("@*") for name in specs):
                raise ValueError("expected explicit registry package specs")
            names = [name[:-2] for name in specs]
            prefix = next(
                arg.split("=", 1)[1] for arg in args if arg.startswith("--prefix=")
            )
            (Path(prefix) / "lib").mkdir(parents=True, exist_ok=True)
            for name in names:
                state.setdefault("packages", {})[name] = "1.0.0"
                if state.get("partial_failure"):
                    state_path.write_text(json.dumps(state))
                    print("controlled partial failure", file=sys.stderr)
                    return 8
            for name in state.get("dependencies", []):
                state.setdefault("packages", {})[name] = "1.0.0"
            state_path.write_text(json.dumps(state))
            if state.get("produce"):
                tool = root / "installed-tool"
                tool.write_text("#!" + sys.executable + "\nprint('2.0.0')\n")
                tool.chmod(0o755)
    finally:
        lock.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
