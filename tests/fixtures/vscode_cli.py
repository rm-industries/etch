"""A local fake CLI; only files beside this copied script can be changed."""

import json
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
        stream.write(json.dumps(args) + "\n")
    if state.get("sleep"):
        time.sleep(state["sleep"])
    if state.get("fail") == args[0]:
        print("controlled CLI failure", file=sys.stderr)
        return 7
    if args[0] == "--version":
        print(state.get("version", "1.105.0\nfake-commit\nx64"))
    elif args[0] == "--list-extensions":
        print(state.get("output", "\n".join(state.get("extensions", []))))
    elif args[0] == "--install-extension":
        extension = args[1]
        if state.get("fail_extension") == extension:
            print("controlled extension failure", file=sys.stderr)
            return 8
        if not state.get("pretend"):
            state.setdefault("extensions", []).append(extension)
            state["extensions"].extend(state.get("bundled", {}).get(extension, []))
            state_path.write_text(json.dumps(state))
    else:
        print("unexpected arguments", file=sys.stderr)
        return 9
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
