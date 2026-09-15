import sys
import tempfile
import unittest
from pathlib import Path

from etchlib.plugins.loader import load_plugins
from etchlib.providers.contracts import Context
from etchlib.providers.lifecycle import gather_fact
from etchlib.providers.registry import Registry
from tests.plugin_fixtures import ENTRY, write_plugin


class PluginLoadingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        before = set(sys.modules)
        self.addCleanup(
            lambda: [
                sys.modules.pop(name, None)
                for name in tuple(sys.modules)
                if name.startswith("_etch_plugin_") and name not in before
            ]
        )

    def test_local_and_vendored_source(self):
        for location in ["local/example", "vendor/example"]:
            with self.subTest(location=location):
                write_plugin(self.root / location)
                core = Registry()
                loaded = load_plugins(self.root, [location], core)
                self.assertEqual(core.entries(), ())
                self.assertEqual(loaded.plugins[0].version, "1.2.3")
                entry = loaded.registry.fact("example_fact")
                context = Context(self.root, self.root, "module", {})
                self.assertEqual(gather_fact(entry, {}, context).value, "from plugin")
                self.assertEqual(entry.origin.name, "example")

    def test_only_declared_entrypoint_executes(self):
        write_plugin(self.root / "declared")
        write_plugin(self.root / "undeclared", "raise RuntimeError('must not run')")
        (self.root / "declared" / "unrelated.py").write_text(
            "raise RuntimeError('must not run')"
        )
        self.assertEqual(
            len(load_plugins(self.root, ["declared"], Registry()).plugins), 1
        )

    def test_relative_imports_do_not_collide(self):
        write_plugin(self.root / "one")
        write_plugin(self.root / "two", ENTRY.replace('"example"', '"second"'))
        helper = self.root / "two" / "implementation.py"
        helper.write_text(helper.read_text().replace('"example_fact"', '"second_fact"'))
        original_path = list(sys.path)
        loaded = load_plugins(self.root, ["two", "one"], Registry())
        self.assertEqual([p.name for p in loaded.plugins], ["second", "example"])
        self.assertEqual(
            [e.name for e in loaded.registry.entries()], ["second_fact", "example_fact"]
        )
        self.assertEqual(sys.path, original_path)

    def test_empty_bundle_and_no_declarations(self):
        write_plugin(
            self.root / "empty", ENTRY.replace("return [ExampleFact()]", "return []")
        )
        self.assertEqual(
            load_plugins(self.root, ["empty"], Registry()).registry.entries(), ()
        )
        self.assertEqual(load_plugins(self.root, [], Registry()).plugins, ())

    def test_action_factory_registers_without_running_provider(self):
        entry = (
            ENTRY
            + """
class ExampleAction:
    name = "example_action"
    def validate(self, *args):
        raise AssertionError("loading must not validate actions")
    inspect = validate
    plan = validate
    apply = validate
def actions():
    return [ExampleAction()]
"""
        )
        write_plugin(self.root / "plugin", entry)
        loaded = load_plugins(self.root, ["plugin"], Registry())
        self.assertEqual(
            loaded.registry.action("example_action").origin.name, "example"
        )
