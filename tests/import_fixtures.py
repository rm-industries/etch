"""Real local Git object stores behind a test-only transport substitution."""

import os
import subprocess
from dataclasses import replace
from typing import Any, Optional
from unittest.mock import patch

from etchlib.importing.copy import import_module
from etchlib.importing.git import Git
from etchlib.importing.source import Source
from tests.planning_fixtures import PlanningFixture


class ImportFixture(PlanningFixture):
    def setUp(self) -> None:
        super().setUp()
        self.upstream = self.root / "upstream"
        self.upstream.mkdir()
        (self.root / "disabled-hooks").mkdir()
        self.consumer = self.root / "consumer"
        self.consumer.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "core.autocrlf", "false")
        self.git("config", "core.filemode", "false")
        self.git("config", "core.symlinks", "true")
        self.git("config", "user.name", "Import Test")
        self.git("config", "user.email", "import@example.invalid")
        self.git("config", "uploadpack.allowFilter", "true")
        self.git("config", "uploadpack.allowAnySHA1InWant", "true")
        self.module_path = self.upstream / "modules/demo"
        self.module_path.mkdir(parents=True)
        self.config(actions=[{"link": {"target": "files/asset"}}])
        (self.module_path / "files").mkdir()
        (self.module_path / "files/asset").write_text("original\n")
        self.commit = self.save()
        upstream = self.upstream

        class LocalGit(Git):
            def fetch(self, source: Source) -> str:
                self.env["GIT_ALLOW_PROTOCOL"] = "file"
                return super().fetch(replace(source, url=upstream.as_uri()))

        transport = patch("etchlib.importing.copy.Git", LocalGit)
        transport.start()
        self.addCleanup(transport.stop)

    def git(self, *args: str, input_data: Optional[str] = None) -> str:
        result = subprocess.run(
            ["git", "-c", "core.hooksPath=" + str(self.root / "disabled-hooks"), *args],
            cwd=self.upstream,
            env=dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull),
            # Git plumbing requires literal LF bytes, including on Windows.
            input=input_data.encode("utf-8") if input_data is not None else None,
            capture_output=True,
            check=True,
        )
        return result.stdout.decode("utf-8").strip()

    def config(self, **values: Any) -> None:
        (self.module_path / "module.conf").write_text(
            repr(dict(schema_version=1, name="demo", **values))
        )

    def save(self) -> str:
        self.git("add", ".")
        self.git("commit", "-m", "Fixture")
        return self.git("rev-parse", "HEAD")

    def run_import(self, ref: str = "HEAD", provenance: bool = True) -> str:
        return import_module(
            self.consumer,
            "github:example/dotfiles",
            "modules/demo",
            ref,
            provenance=provenance,
        )
