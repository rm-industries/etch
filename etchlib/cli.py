"""Command-line entrypoint; no optional dependencies or startup network calls."""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from etchlib import __version__
from etchlib.config import ConfigError, load_repository
from etchlib.core import core_registry
from etchlib.plugins.loader import load_plugins
from etchlib.plugins.metadata import PluginError


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="etch", description="Make your environment yours."
    )
    parser.add_argument("--version", action="version", version="Etch " + __version__)
    commands = parser.add_subparsers(dest="command")
    doctor = commands.add_parser(
        "doctor", help="check repository configuration structure"
    )
    doctor.add_argument(
        "modules", nargs="*", help="module names (default: all discovered modules)"
    )
    doctor.add_argument("--profile", help="select an ordered profile")
    doctor.add_argument(
        "--repo",
        type=Path,
        default=Path.cwd(),
        help="consumer repository root (default: current directory)",
    )
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        repository = load_repository(args.repo, args.profile, args.modules)
        loaded = load_plugins(
            repository.root, repository.defaults.get("plugins", []), core_registry()
        )
    except (ConfigError, PluginError) as exc:
        print("Etch: {}".format(exc), file=sys.stderr)
        return 1
    print("Configuration structure OK: {}".format(repository.root))
    for module in repository.modules:
        print("  {}".format(module.name))
    for plugin in loaded.plugins:
        print(
            "Plugin {} {} (API {}): {}".format(
                plugin.name, plugin.version, plugin.api, plugin.root
            )
        )
    print(
        "Provider schemas, dependencies, facts and destination conflicts are not checked yet."
    )
    return 0
