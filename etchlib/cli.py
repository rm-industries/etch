"""Command-line entrypoint; no optional dependencies or startup network calls."""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from etchlib import __version__
from etchlib.config import load_repository
from etchlib.core import core_registry
from etchlib.diagnostics.doctor import diagnose
from etchlib.diagnostics.facts import gather, render_facts
from etchlib.diagnostics.render import render_doctor
from etchlib.execution.render import render_apply
from etchlib.execution.runner import apply_repository
from etchlib.facts.repository import repository_facts
from etchlib.importing.copy import import_module
from etchlib.planning.build import plan_repository
from etchlib.planning.render import render_plan
from etchlib.plugins.loader import load_plugins
from etchlib.providers.errors import ProviderError
from etchlib.providers.observations import FactState


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="etch", description="Make your environment yours."
    )
    parser.add_argument("--version", action="version", version="Etch " + __version__)
    commands = parser.add_subparsers(dest="command")
    doctor = commands.add_parser(
        "doctor", help="diagnose configuration, providers and current state"
    )
    plan = commands.add_parser(
        "plan", help="inspect and explain changes without applying them"
    )
    plan.add_argument(
        "--verbose", "-v", action="store_true", help="show provider origins"
    )
    apply = commands.add_parser("apply", help="apply a validated staged action graph")
    apply.add_argument(
        "--jobs", "-j", type=int, help="maximum concurrent actions (1–64)"
    )
    apply.add_argument(
        "--allow-sudo",
        action="store_true",
        help="authorize declared elevation requests",
    )
    facts = commands.add_parser(
        "facts", help="gather built-in and selected module facts"
    )
    for command in (doctor, plan, apply, facts):
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
    importer = commands.add_parser(
        "import", help="copy a public Git module without executing it"
    )
    importer.add_argument("source")
    importer.add_argument("--path", required=True, help="source module directory")
    importer.add_argument(
        "--ref", default="HEAD", help="HEAD, full branch/tag ref or full commit"
    )
    importer.add_argument("--repo", type=Path, default=Path.cwd())
    importer.add_argument("--no-provenance", action="store_true")
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        if args.command == "import":
            print(
                import_module(
                    args.repo,
                    args.source,
                    args.path,
                    args.ref,
                    provenance=not args.no_provenance,
                )
            )
            return 0
        repository = load_repository(args.repo, args.profile, args.modules)
        loaded = load_plugins(
            repository.root, repository.defaults.get("plugins", []), core_registry()
        )
        if args.command == "facts":
            observations = gather(repository_facts(repository, loaded.registry))
            print(render_facts(observations))
            return (
                1
                if any(fact.state is FactState.ERROR for fact in observations.values())
                else 0
            )
        if args.command == "doctor":
            diagnosis = diagnose(repository, loaded.registry)
            print(render_doctor(repository, loaded.registry, loaded.plugins, diagnosis))
            return 1 if diagnosis.errors else 0
        if args.command == "apply":
            applied = apply_repository(
                repository, loaded.registry, allow_sudo=args.allow_sudo, jobs=args.jobs
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
    return 0
