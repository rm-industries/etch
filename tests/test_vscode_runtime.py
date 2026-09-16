import ast
import subprocess
import sys

from etchlib.providers.errors import ProviderError
from tests.vscode_fixtures import ROOT, VSCodeFixture


class VSCodeRuntimeTests(VSCodeFixture):
    def test_vendored_plugin_apply_without_site_packages(self) -> None:
        self.module(
            actions=[
                {
                    "vscode": {
                        "command": str(self.code),
                        "extensions": ["ms-python.python"],
                    }
                }
            ]
        )
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                "-c",
                "import runpy, sys; sys.path.insert(0, sys.argv.pop(1)); sys.argv = sys.argv[1:]; runpy.run_path(sys.argv[0], run_name='__main__')",
                str(ROOT),
                str(ROOT / "etch"),
                "apply",
                "--repo",
                str(self.root),
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("CHANGED", result.stdout)
        self.assertEqual(self.current()["extensions"], ["ms-python.python"])

    def test_plugin_uses_python39_grammar_and_stdlib_or_core_imports(self) -> None:
        # The isolated integration test proves resolution; this catches dormant imports.
        allowed = {
            "dataclasses",
            "math",
            "os",
            "pathlib",
            "re",
            "shutil",
            "subprocess",
            "tempfile",
            "typing",
            "etchlib",
        }
        for file in (ROOT / "plugins/vscode").glob("*.py"):
            tree = ast.parse(
                file.read_text(), filename=str(file), feature_version=(3, 9)
            )
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertIn(alias.name.split(".")[0], allowed)
                elif (
                    isinstance(node, ast.ImportFrom) and not node.level and node.module
                ):
                    self.assertIn(node.module.split(".")[0], allowed)

    def test_invalid_targets_and_bounded_output(self) -> None:
        for timeout in (False, 0, -1, float("inf"), float("nan")):
            with self.subTest(timeout=timeout), self.assertRaises(ProviderError):
                self.vscode_plan([], timeout=timeout)
        self.state(output="x" * (1024 * 1024 + 1))
        with self.assertRaisesRegex(ProviderError, "exceeds 1 MiB"):
            self.vscode_plan([])

    def test_executable_disappearing_after_inspection_fails(self) -> None:
        from etchlib.providers.lifecycle import apply_action

        plan = self.vscode_plan(["ms-python.python"])
        self.code.unlink()
        with self.assertRaisesRegex(ProviderError, "executable changed"):
            apply_action(self.entry, plan, self.context)
