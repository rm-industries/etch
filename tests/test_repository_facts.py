import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from etchlib.config import load_repository
from etchlib.facts.core import core_registry
from etchlib.facts.probes import LocalProbe
from etchlib.facts.repository import repository_facts
from etchlib.plugins.loader import load_plugins
from etchlib.providers.contracts import Context
from etchlib.providers.errors import ProviderError
from etchlib.providers.observations import FactRef, FactResult
from tests.plugin_fixtures import write_plugin


class RepositoryFactTests(unittest.TestCase):
    def test_conditional_alternatives_are_lazy_and_share_refresh(self) -> None:
        calls: list[str] = []
        original = LocalProbe.gather

        def gather(probe: LocalProbe, config: str, context: Context) -> FactResult:
            calls.append(config)
            return original(probe, config, context)

        for system, selected in (("Linux", "linux"), ("Darwin", "macos")):
            with self.subTest(system=system), tempfile.TemporaryDirectory() as temp:
                calls.clear()
                root = Path(temp)
                shutil.copytree(
                    Path(__file__).resolve().parents[1] / "examples/minimal",
                    root,
                    dirs_exist_ok=True,
                )
                module = root / "modules/git"
                (module / "module.conf").write_text(
                    repr(
                        {
                            "schema_version": 1,
                            "name": "git",
                            "facts": {
                                "installed": [
                                    {
                                        "when": {"os": "linux"},
                                        "file_exists": "linux-tool",
                                    },
                                    {
                                        "when": {"os": "macos"},
                                        "file_exists": "macos-tool",
                                    },
                                ]
                            },
                        }
                    )
                )
                ref = FactRef("git", "installed")
                with (
                    patch(
                        "etchlib.facts.platform.platform.system", return_value=system
                    ),
                    patch.object(LocalProbe, "gather", gather),
                ):
                    store = repository_facts(load_repository(root), core_registry())
                    self.assertIsNone(store.peek(ref))
                    self.assertFalse(store.get(ref).value)
                    self.assertEqual(calls, [selected + "-tool"])
                    (module / (selected + "-tool")).touch()
                    store.invalidate(ref)
                    self.assertTrue(store.get(ref).value)
                    self.assertEqual(calls, [selected + "-tool"] * 2)

    def test_conditional_alternatives_reject_no_match_and_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(
                Path(__file__).resolve().parents[1] / "examples/minimal",
                root,
                dirs_exist_ok=True,
            )
            module = root / "modules/git/module.conf"
            for conditions, expected in (
                (["macos"], "found 0"),
                (["linux", "linux"], "found 2"),
            ):
                with self.subTest(conditions=conditions):
                    module.write_text(
                        repr(
                            {
                                "schema_version": 1,
                                "name": "git",
                                "facts": {
                                    "installed": [
                                        {"when": {"os": name}, "file_exists": "tool"}
                                        for name in conditions
                                    ]
                                },
                            }
                        )
                    )
                    with patch(
                        "etchlib.facts.platform.platform.system", return_value="Linux"
                    ):
                        with self.assertRaisesRegex(ProviderError, expected):
                            repository_facts(load_repository(root), core_registry())

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
