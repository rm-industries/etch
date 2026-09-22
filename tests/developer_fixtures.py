"""Run the checked-in developer example in a fresh, isolated consumer."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.installer_fixtures import InstallerFixture

ROOT = Path(__file__).resolve().parents[1]


class DeveloperFixture(InstallerFixture):
    def setUp(self) -> None:
        super().setUp()
        self.repo = self.root / "consumer"
        shutil.copytree(ROOT / "examples/developer", self.repo)
        engine = self.repo / ".vendor/etch"
        shutil.copytree(
            ROOT / "etchlib",
            engine / "etchlib",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        shutil.copy2(ROOT / "etch", engine / "etch")
        for plugin in ("homebrew", "vscode"):
            shutil.copytree(
                ROOT / "plugins" / plugin,
                self.repo / "vendor" / ("etch-" + plugin),
                ignore=shutil.ignore_patterns("__pycache__"),
            )
        self.home = self.root / "home"
        self.home.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        python = str(Path(getattr(sys, "_base_executable", sys.executable)).resolve())
        self.python = python
        self.tool("tmux", "print('tmux 3.4')\n")
        # Keep each fake CLI's state files separate while sharing PATH.
        tools: tuple[tuple[str, str, dict[str, Any]], ...] = (
            ("brew", "brew_cli.py", {"formula": [], "cask": []}),
            ("code", "vscode_cli.py", {"extensions": []}),
        )
        for name, fixture, state in tools:
            directory = self.root / name
            directory.mkdir()
            executable = directory / name
            executable.write_text(
                "#!" + python + "\n" + (ROOT / "tests/fixtures" / fixture).read_text()
            )
            executable.chmod(0o755)
            (directory / "state.json").write_text(json.dumps(state))
        self.env = dict(
            os.environ,
            HOME=str(self.home),
            PATH=os.pathsep.join(
                str(path) for path in (self.bin, self.root / "brew", self.root / "code")
            ),
            PYTHONNOUSERSITE="1",
        )
        self.env.pop("PYTHONPATH", None)
        environment = patch.dict(os.environ, self.env, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        starship = self.repo / "modules/starship"
        shutil.copy2(self.root / "ca.pem", starship / "ca.pem")
        config = self.module_config("starship")
        config["actions"][0]["installer"].update(
            url=self.url, shell=python, tls={"ca_file": "ca.pem"}
        )
        self.write_module("starship", config)
        program = "#!" + python + "\nprint('starship 1.20.0')\n"
        self.server.body = (
            "from pathlib import Path\np = Path({!r})\np.write_text({!r})\np.chmod(0o755)\n".format(
                str(self.bin / "starship"), program
            )
        ).encode()

    def tool(self, name: str, program: str) -> None:
        path = self.bin / name
        path.write_text("#!" + self.python + "\n" + program)
        path.chmod(0o755)

    def module_config(self, name: str) -> dict[str, Any]:
        from etchlib.config import read_config

        return read_config(self.repo / "modules" / name / "module.conf")

    def write_module(self, name: str, config: dict[str, Any]) -> None:
        (self.repo / "modules" / name / "module.conf").write_text(repr(config))

    def cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                self.python,
                "-S",
                str(self.repo / ".vendor/etch/etch"),
                *args,
                "--repo",
                str(self.repo),
                "--profile",
                "developer",
            ],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def calls(self, name: str) -> list[Any]:
        path = self.root / name / "calls.jsonl"
        return (
            [json.loads(line) for line in path.read_text().splitlines()]
            if path.exists()
            else []
        )
