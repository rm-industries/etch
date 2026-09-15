import contextlib
import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from etchlib.cli import main
from etchlib.plugins.loader import load_plugins
from etchlib.plugins.metadata import PluginError
from etchlib.providers.registry import Origin, Registry
from tests.plugin_fixtures import ENTRY, write_plugin
from tests.provider_fixtures import MemoryFact


class PluginErrorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_bad_metadata_and_incompatible_api(self):
        for index, entry in enumerate(
            [
                ENTRY.replace('"api": 1', '"api": 2'),
                ENTRY.replace('"api": 1', '"api": True'),
                ENTRY.replace('"version": "1.2.3"', '"version": 3'),
                ENTRY.replace('"name": "example"', '"name": ""'),
                ENTRY.replace("PLUGIN =", "NOT_METADATA ="),
            ]
        ):
            location = str(index)
            write_plugin(self.root / location, entry)
            with self.subTest(index=index), self.assertRaises(PluginError):
                load_plugins(self.root, [location], Registry())

    def test_factory_not_called_for_incompatible_api(self):
        marker = self.root / "factory-called"
        entry = ENTRY.replace('"api": 1', '"api": 99').replace(
            "return []", "open({!r}, 'w').close(); return []".format(str(marker))
        )
        write_plugin(self.root / "bad", entry)
        with self.assertRaisesRegex(PluginError, "incompatible"):
            load_plugins(self.root, ["bad"], Registry())
        self.assertFalse(marker.exists())

    def test_factory_and_import_failures_are_contextual(self):
        entries = [
            "raise RuntimeError('import failed')",
            "raise SystemExit(2)",
            ENTRY.replace("return []", "return None"),
            ENTRY + "\nactions = None\n",
            ENTRY.replace("return []", "raise RuntimeError('factory failed')"),
        ]
        for index, entry in enumerate(entries):
            location = str(index)
            write_plugin(self.root / location, entry)
            with (
                self.subTest(index=index),
                self.assertRaisesRegex(PluginError, str(self.root / location)),
            ):
                load_plugins(self.root, [location], Registry())

    def test_missing_and_duplicate_paths(self):
        write_plugin(self.root / "plugin")
        for paths in [["missing"], ["plugin", "./plugin"], ["\x00"], [""], "plugin"]:
            with self.subTest(paths=paths), self.assertRaises(PluginError):
                load_plugins(self.root, paths, Registry())

    def test_duplicate_names_and_providers_leave_core_unchanged(self):
        write_plugin(self.root / "one")
        write_plugin(self.root / "two")
        core = Registry()
        core.register(Origin("Etch core", "0.1", True), facts=[MemoryFact()])
        before = set(sys.modules)
        with self.assertRaisesRegex(PluginError, "duplicate plugin name"):
            load_plugins(self.root, ["one", "two"], core)
        self.assertEqual([e.name for e in core.entries()], ["memory_value"])
        self.assertFalse(
            [n for n in set(sys.modules) - before if n.startswith("_etch_plugin_")]
        )
        entry = self.root / "two" / "etch_plugin.py"
        entry.write_text(ENTRY.replace('"example"', '"other"'))
        with self.assertRaisesRegex(PluginError, "conflicts"):
            load_plugins(self.root, ["one", "two"], core)
        self.assertEqual(len(core.entries()), 1)

    def test_core_provider_shadowing(self):
        write_plugin(self.root / "plugin")
        core_fact = MemoryFact()
        core_fact.name = "example_fact"
        core = Registry()
        core.register(Origin("Etch core", "0.1", True), facts=[core_fact])
        with self.assertRaisesRegex(PluginError, "Etch core"):
            load_plugins(self.root, ["plugin"], core)
        self.assertIs(core.fact("example_fact").provider, core_fact)

    def test_doctor_reports_plugin_failure_without_traceback(self):
        example = Path(__file__).resolve().parents[1] / "examples/minimal"
        shutil.copytree(example, self.root, dirs_exist_ok=True)
        (self.root / "defaults.conf").write_text(
            "{'schema_version': 1, 'plugins': ['missing']}"
        )
        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            status = main(["doctor", "--repo", str(self.root)])
        self.assertEqual(status, 1)
        self.assertIn("missing plugin entrypoint", error.getvalue())
        self.assertNotIn("Traceback", error.getvalue())
