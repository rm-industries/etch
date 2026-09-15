"""Fresh consumer sources and a base-interpreter-only runtime environment."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]


class BootstrapFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="etch bootstrap ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.consumer = self.root / "consumer repo"
        shutil.copytree(ROOT / "examples" / "minimal", self.consumer)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.python = self.bin / "python3"
        self.python.symlink_to(
            Path(getattr(sys, "_base_executable", sys.executable)).resolve()
        )
        self.env = dict(os.environ, PATH=str(self.bin), PYTHONNOUSERSITE="1")
        self.env.pop("PYTHONPATH", None)
        self.env.pop("PYTHONHOME", None)
        self.env.pop("VIRTUAL_ENV", None)

    def vendor(self, destination: Optional[Path] = None) -> Path:
        destination = destination or self.consumer / "vendor" / "etch"
        destination.mkdir(parents=True)
        shutil.copy2(ROOT / "etch", destination / "etch")
        shutil.copytree(
            ROOT / "etchlib",
            destination / "etchlib",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        return destination

    def run_install(
        self, *args: str, consumer: Optional[Path] = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str((consumer or self.consumer) / "install"), *args],
            cwd=self.root,
            env=self.env,
            text=True,
            capture_output=True,
            timeout=30,
        )

    def run_probe(
        self, consumer: Optional[Path] = None
    ) -> subprocess.CompletedProcess[str]:
        consumer = consumer or self.consumer
        return subprocess.run(
            [
                str(self.python),
                "-I",
                "-S",
                str(ROOT / "tests/runtime_probe.py"),
                str(consumer),
            ],
            cwd=self.root,
            env=self.env,
            text=True,
            capture_output=True,
            timeout=30,
        )
