"""File-backed Claude CLI double; no user configuration or remote plugins."""

import json
import sys
import time
from pathlib import Path

root = Path(__file__).parent
state_path = root / "state.json"
state = json.loads(state_path.read_text())
args = sys.argv[1:]
if sys.stdin.read():
    raise SystemExit("stdin must be closed")
with (root / "calls.jsonl").open("a") as stream:
    stream.write(json.dumps(args) + "\n")
if state.get("sleep"):
    time.sleep(state["sleep"])
if state.get("fail") == args:
    print("controlled Claude failure", file=sys.stderr)
    raise SystemExit(7)
if args == ["--version"]:
    print("2.1.312 (Claude Code)")
elif args == ["plugin", "marketplace", "list", "--json"]:
    print(state.get("marketplace_output", json.dumps(state.get("marketplaces", []))))
elif args == ["plugin", "list", "--json"]:
    print(state.get("plugin_output", json.dumps(state.get("installed", []))))
elif args[:3] == ["plugin", "marketplace", "add"] and args[-2:] == ["--scope", "user"]:
    source = args[3]
    if any(
        item.get("url", item.get("path")) == source
        for item in state.get("marketplaces", [])
    ):
        raise SystemExit("marketplace already present")
    name = state.get("source_names", {}).get(source, "catalog")
    if any(item["name"] == name for item in state.get("marketplaces", [])):
        raise SystemExit("marketplace name already registered with a different source")
    if not state.get("pretend_market"):
        local = source.startswith("/")
        state.setdefault("marketplaces", []).append(
            {
                "name": name,
                "source": "directory" if local else "git",
                "path" if local else "url": source,
                "installLocation": str(root / "marketplaces" / name),
            }
        )
    state.setdefault("installed", []).extend(state.get("installed_by_marketplace", []))
    print("Successfully added marketplace: " + name)
elif args[:2] == ["plugin", "install"] and args[-2:] == ["--scope", "user"]:
    lock = root / "install.lock"
    try:
        lock.touch(exist_ok=False)
    except FileExistsError:
        raise SystemExit("concurrent Claude mutation") from None
    try:
        if state.get("gate"):
            (root / "started").touch()
            deadline = time.monotonic() + 5
            while not (root / "release").exists():
                if time.monotonic() > deadline:
                    raise RuntimeError("unrelated action did not progress")
                time.sleep(0.005)
        plugin = args[2]
        if plugin.split("@")[1] not in {
            row["name"] for row in state.get("marketplaces", [])
        }:
            raise SystemExit("unknown marketplace")
        if not state.get("pretend"):
            state.setdefault("installed", []).append(
                {
                    "id": plugin,
                    "version": "1.0.0",
                    "scope": "user",
                    "enabled": True,
                    "installPath": str(root / "cache" / plugin),
                    "installedAt": "2026-10-27T00:00:00.000Z",
                    "lastUpdated": "2026-10-27T00:00:00.000Z",
                }
            )
        print("Successfully installed plugin: " + plugin)
    finally:
        lock.unlink()
else:
    raise SystemExit("unexpected arguments: " + repr(args))
state_path.write_text(json.dumps(state))
