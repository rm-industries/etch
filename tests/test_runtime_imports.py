"""Prove development environments cannot conceal forbidden core imports."""

import subprocess

from tests.bootstrap_fixtures import BootstrapFixture


class RuntimeImportTests(BootstrapFixture):
    def test_guard_rejects_available_nonstdlib_dependency(self) -> None:
        source = self.vendor()
        (source / "etch_test_dependency.py").write_text("VALUE = 1\n")
        # Available even without site packages: origin checking must still reject it.
        available = subprocess.run(
            [str(self.python), "-S", "-c", "import etch_test_dependency"],
            cwd=source,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(available.returncode, 0, available.stderr)
        (source / "etchlib/dependency_probe.py").write_text(
            "try:\n    import etch_test_dependency\nexcept ImportError:\n    pass\n"
        )
        result = self.run_probe()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "non-standard-library core import: etch_test_dependency", result.stderr
        )
        self.assertIn("etchlib/dependency_probe.py:2", result.stderr)

    def test_guard_rejects_dormant_missing_dependency(self) -> None:
        source = self.vendor()
        (source / "etchlib/dependency_probe.py").write_text(
            "if False:\n    from etch_missing_dependency import value\n"
        )
        result = self.run_probe()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "non-standard-library core import: etch_missing_dependency", result.stderr
        )

    def test_parent_pythonpath_cannot_supply_runtime_packages(self) -> None:
        self.vendor()
        packages = self.root / "developer packages"
        packages.mkdir()
        (packages / "sitecustomize.py").write_text(
            "raise RuntimeError('site leaked')\n"
        )
        (packages / "etchlib.py").write_text(
            "raise RuntimeError('global Etch leaked')\n"
        )
        # Keep hostile parent settings for this call: -I -S must independently isolate it.
        self.env.update(PYTHONPATH=str(packages), VIRTUAL_ENV=str(packages))
        result = self.run_probe()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Runtime compatibility OK", result.stdout)

    def test_import_sweep_checks_modules_outside_cli_startup(self) -> None:
        source = self.vendor()
        (source / "etchlib/api_probe.py").write_text(
            "from pathlib import etch_missing_stdlib_api\n"
        )
        result = self.run_probe()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("etch_missing_stdlib_api", result.stderr)
