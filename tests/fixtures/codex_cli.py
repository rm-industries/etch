"""File-backed native plugin CLI double; no real Codex installation is modified."""

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
    print("controlled CLI failure", file=sys.stderr)
    raise SystemExit(7)
if args == ["--version"]:
    print("codex-cli 0.154.0")
elif args == ["plugin", "marketplace", "list", "--json"]:
    print(
        state.get(
            "marketplace_output",
            json.dumps({"marketplaces": state.get("marketplaces", [])}),
        )
    )
elif args == ["plugin", "list", "--json"]:
    print(
        state.get(
            "plugin_output",
            json.dumps(
                {
                    "installed": state.get("installed", []),
                    "available": state.get("available", []),
                }
            ),
        )
    )
elif args[:3] == ["plugin", "marketplace", "add"] and args[-1] == "--json":
    source = args[3]
    name = state.get("source_names", {}).get(source, "catalog")
    if any(item["name"] == name for item in state.get("marketplaces", [])):
        print("marketplace already added from a different source", file=sys.stderr)
        raise SystemExit(7)
    state.setdefault("marketplaces", []).append(
        {"name": name, "marketplaceSource": {"sourceType": "git", "source": source}}
    )
    print(json.dumps({"marketplaceName": name, "alreadyAdded": False}))
elif args[:2] == ["plugin", "add"] and args[-1] == "--json":
    selector = args[2]
    if not state.get("pretend"):
        name, market = selector.split("@")
        if market not in {item["name"] for item in state.get("marketplaces", [])}:
            print("unknown marketplace", file=sys.stderr)
            raise SystemExit(8)
        state.setdefault("installed", []).append(
            {
                "pluginId": selector,
                "name": name,
                "marketplaceName": market,
                "installed": True,
                "enabled": True,
                "version": "1.0.0",
            }
        )
    print(json.dumps({"pluginId": selector}))
else:
    print("unexpected args", file=sys.stderr)
    raise SystemExit(9)
state_path.write_text(json.dumps(state))
