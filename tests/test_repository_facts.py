import shutil
import tempfile
import unittest
from pathlib import Path

from etchlib.config import load_repository
from etchlib.facts.core import core_registry
from etchlib.facts.repository import repository_facts
from etchlib.plugins.loader import load_plugins
from etchlib.providers.observations import FactRef
from tests.plugin_fixtures import write_plugin


class RepositoryFactTests(unittest.TestCase):
    def test_scoped_declarations_use_core_and_plugin_providers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(
                Path(__file__).resolve().parents[1] / "examples/minimal",
                root,
                dirs_exist_ok=True,
            )
            write_plugin(root / "vendor/example")
            (root / "modules/git/module.conf").write_text(
                repr(
                    {
                        "schema_version": 1,
                        "name": "git",
                        "facts": {
                            "plugin_value": {"example_fact": {}},
                            "config_present": {"file_exists": "files/gitconfig"},
                        },
                    }
                )
            )
            registry = load_plugins(root, ["vendor/example"], core_registry()).registry
            store = repository_facts(load_repository(root), registry)
            self.assertEqual(
                store.references()[:3],
                tuple(FactRef(None, n) for n in ("os", "distro", "arch")),
            )
            self.assertTrue(store.get(FactRef("git", "config_present")).value)
            self.assertEqual(
                store.get(FactRef("git", "plugin_value")).value, "from plugin"
            )
