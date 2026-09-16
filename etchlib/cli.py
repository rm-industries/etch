"""Command-line entrypoint; no optional dependencies or startup network calls."""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from etchlib import __version__
from etchlib.config import load_repository
from etchlib.core import core_registry
from etchlib.execution.render import render_apply
from etchlib.execution.runner import apply_repository
from etchlib.planning.build import plan_repository
from etchlib.planning.render import render_plan
from etchlib.plugins.loader import load_plugins
from etchlib.providers.errors import ProviderError


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="etch", description="Make your environment yours."
    )
    parser.add_argument("--version", action="version", version="Etch " + __version__)
    commands = parser.add_subparsers(dest="command")
    doctor = commands.add_parser(
        "doctor", help="check repository configuration structure"
    )
    plan = commands.add_parser(
        "plan", help="inspect and explain changes without applying them"
    )
    plan.add_argument(
        "--verbose", "-v", action="store_true", help="show provider origins"
    )
    apply = commands.add_parser("apply", help="apply a validated staged action graph")
    apply.add_argument(
        "--allow-sudo",
        action="store_true",
        help="authorize declared elevation requests",
    )
    for command in (doctor, plan, apply):
        command.add_argument(
            "modules", nargs="*", help="module names (default: all discovered modules)"
        )
        command.add_argument("--profile", help="select an ordered profile")
        command.add_argument(
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
        if args.command == "apply":
            applied = apply_repository(
                repository, loaded.registry, allow_sudo=args.allow_sudo
            )
            print(render_apply(applied))
            return 0 if applied.succeeded else 1
        if args.command == "plan":
            report = plan_repository(repository, loaded.registry)
            print(render_plan(repository, report, loaded.plugins, args.verbose))
            return 0
    except (ValueError, ProviderError, OSError) as exc:
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
