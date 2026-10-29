"""File-backed uv tool CLI double; no package downloads or real user tools."""

import json
import os
import sys
import time
from pathlib import Path

root = Path(__file__).parent
state_path = root / "state.json"
state = json.loads(state_path.read_text())
if sys.stdin.read():
    raise SystemExit("stdin must be closed")
if sys.argv[1:4] != ["--color", "never", "--no-progress"]:
    raise SystemExit("expected deterministic output flags before command")
args = sys.argv[4:]
with (root / "calls.jsonl").open("a") as stream:
    stream.write(
        json.dumps(
            {
                "args": args,
                "tools": os.environ.get("UV_TOOL_DIR"),
                "bin": os.environ.get("UV_TOOL_BIN_DIR"),
            }
        )
        + "\n"
    )
if state.get("sleep"):
    time.sleep(state["sleep"])
tools_dir = state.get("tools_dir", os.environ.get("UV_TOOL_DIR", str(root / "tools")))
bin_dir = state.get(
    "bin_dir", os.environ.get("UV_TOOL_BIN_DIR", str(root / "executables"))
)
if args == ["--version"]:
    print("uv 0.12.17 (test)")
elif args == ["tool", "dir"]:
    print(state.get("dir_output", tools_dir))
elif args == ["tool", "dir", "--bin"]:
    print(state.get("bin_output", bin_dir))
elif args == ["tool", "list"]:
    if state.get("list_status"):
        print("controlled inventory failure", file=sys.stderr)
        raise SystemExit(state["list_status"])
    output = state.get("output")
    if output is None:
        output = "\n".join(
            name + " v" + version + "\n- " + name
            for name, version in sorted(state.get("tools", {}).items())
        )
    if output:
        print(output)
    warning = state.get("warning", "" if output else "No tools installed")
    if warning:
        print(warning, file=sys.stderr)
elif args[:4] == ["tool", "install", "--no-python-downloads", "--"] and len(args) == 5:
    spec = args[4]
    if not spec.endswith(">=0"):
        raise SystemExit("expected named registry requirement")
    name = spec[:-3]
    lock = root / "install.lock"
    try:
        lock.touch(exist_ok=False)
    except FileExistsError:
        raise SystemExit("concurrent uv mutation") from None
    try:
        if state.get("gate"):
            (root / "started").touch()
            deadline = time.monotonic() + 5
            while not (root / "release").exists():
                if time.monotonic() > deadline:
                    raise RuntimeError("unrelated action did not progress")
                time.sleep(0.005)
        if state.get("fail_tool") == name:
            print("controlled installation failure", file=sys.stderr)
            raise SystemExit(8)
        if not state.get("pretend"):
            state.setdefault("tools", {})[name] = "1.0.0"
            for other in state.get("appeared", []):
                state["tools"][other] = "1.0.0"
            state_path.write_text(json.dumps(state))
            if state.get("produce"):
                tool = Path(bin_dir) / "installed-tool"
                tool.parent.mkdir(parents=True, exist_ok=True)
                tool.write_text("#!" + sys.executable + "\nprint('2.0.0')\n")
                tool.chmod(0o755)
        print("Installed tool", file=sys.stderr)
    finally:
        lock.unlink()
else:
    raise SystemExit("unexpected arguments: " + repr(args))
