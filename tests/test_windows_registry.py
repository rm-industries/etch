"""Registry reconciliation proof with fake access and a disposable Windows key."""

import platform
import tempfile
import unittest
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from etchlib.core import core_registry
from etchlib.plugins.loader import load_plugins
from etchlib.providers.contracts import Context
from etchlib.providers.plans import PlanStatus
from etchlib.scheduling.resources import requirements
from plugins.windows_registry.access import read, write
from plugins.windows_registry.action import WindowsRegistryAction
from plugins.windows_registry.schema import preferences


class WindowsRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = Context(Path.cwd(), Path.cwd(), "test", {})
        self.provider = WindowsRegistryAction()
        self.config: dict[str, Any] = {
            "hive": "HKEY_CURRENT_USER",
            "key": r"Software\EtchTests",
            "values": {
                "flag": {"type": "REG_DWORD", "data": 1},
                "text": {"type": "REG_SZ", "data": "hello"},
                "wide": {"type": "REG_QWORD", "data": 2**40},
                "paths": {"type": "REG_MULTI_SZ", "data": ["a", "b"]},
                "home": {"type": "REG_EXPAND_SZ", "data": "%USERPROFILE%"},
            },
        }

    def test_native_access_reconciles_types_and_preserves_other_values(self) -> None:
        api = MagicMock()
        for index, name in enumerate(
            ("REG_SZ", "REG_EXPAND_SZ", "REG_DWORD", "REG_QWORD", "REG_MULTI_SZ")
        ):
            setattr(api, name, index)
        current: dict[str, tuple[Any, int]] = {
            "flag": (1, api.REG_SZ),
            "untouched": ("keep", api.REG_SZ),
        }

        def query(handle: Any, name: str) -> tuple[Any, int]:
            if name not in current:
                raise FileNotFoundError(name)
            return current[name]

        def put(handle: Any, name: str, reserved: int, kind: int, data: Any) -> None:
            current[name] = (data, kind)

        api.QueryValueEx.side_effect = query
        api.SetValueEx.side_effect = put
        with (
            patch("platform.system", return_value="Windows"),
            patch(
                "plugins.windows_registry.access.importlib.import_module",
                return_value=api,
            ),
        ):
            observation = self.provider.inspect(self.config, self.context)
            plan = self.provider.plan(self.config, observation, self.context)
            self.assertEqual(plan.status, PlanStatus.CHANGE)
            self.assertEqual(requirements(plan), frozenset({"registry:hkcu"}))
            self.assertIn("flag: REG_SZ 1 -> REG_DWORD 1", plan.description)
            self.assertIn("text: missing key/value", plan.description)
            api.CreateKeyEx.assert_not_called()
            api.SetValueEx.assert_not_called()
            self.assertTrue(self.provider.apply(plan, self.context).changed)
            self.assertEqual(current["untouched"], ("keep", api.REG_SZ))
            self.assertEqual(api.SetValueEx.call_count, 5)
            self.assertFalse(self.provider.apply(plan, self.context).changed)
            second = self.provider.plan(
                self.config,
                self.provider.inspect(self.config, self.context),
                self.context,
            )
            self.assertEqual(second.status, PlanStatus.SKIP)
            current["flag"] = (0, api.REG_DWORD)
            self.assertTrue(self.provider.apply(plan, self.context).changed)
            self.assertEqual(api.SetValueEx.call_count, 6)

    def test_missing_key_and_permission_failures(self) -> None:
        desired = preferences(self.config)
        api = MagicMock()
        with patch("plugins.windows_registry.access.registry", return_value=api):
            api.OpenKey.side_effect = FileNotFoundError()
            self.assertEqual(read(desired), {})
            api.OpenKey.side_effect = PermissionError()
            with self.assertRaisesRegex(ValueError, "read denied.*permissions"):
                read(desired)
            api.CreateKeyEx.side_effect = PermissionError()
            with self.assertRaisesRegex(ValueError, "write denied.*does not elevate"):
                write(desired, ("flag",))

    def test_schema_rejects_unsafe_or_ambiguous_configuration(self) -> None:
        invalid = (
            dict(self.config, hive="HKEY_LOCAL_MACHINE"),
            dict(self.config, key=""),
            dict(self.config, key=r"\Software"),
            dict(self.config, key="Software/Etch"),
            dict(self.config, values={}),
            dict(self.config, values={"": {"type": "REG_SZ", "data": "x"}}),
            dict(self.config, values={"a": {"type": "REG_DWORD", "data": True}}),
            dict(self.config, values={"a": {"type": "REG_DWORD", "data": 2**32}}),
            dict(self.config, values={"a": {"type": "REG_QWORD", "data": -1}}),
            dict(self.config, values={"a": {"type": "REG_SZ", "data": "x\x00y"}}),
            dict(self.config, values={"a": {"type": "REG_MULTI_SZ", "data": [""]}}),
            dict(self.config, values={"a": None}),
            dict(self.config, values={"a": {"type": "REG_BINARY", "data": "x"}}),
            dict(
                self.config,
                values={
                    "a": {"type": "REG_SZ", "data": "x"},
                    "A": {"type": "REG_SZ", "data": "y"},
                },
            ),
        )
        for config in invalid:
            with self.subTest(config=config), self.assertRaises(ValueError):
                preferences(config)

    def test_plugin_loads_without_winreg_and_reports_platform_guard(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            registry = load_plugins(
                Path(temp), [str(root / "plugins/windows_registry")], core_registry()
            ).registry
            self.assertEqual(
                registry.action("windows_registry").provider.name, "windows_registry"
            )
        with patch("platform.system", return_value="Linux"):
            with self.assertRaisesRegex(ValueError, "Windows-only.*guard"):
                self.provider.inspect(self.config, self.context)


@unittest.skipUnless(platform.system() == "Windows", "native Windows Registry")
class WindowsRegistryIntegrationTests(unittest.TestCase):
    def test_disposable_key_reconciles_without_touching_other_values(self) -> None:
        import importlib

        winreg = importlib.import_module("winreg")

        key = r"Software\EtchTests-" + uuid.uuid4().hex
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            key,
            0,
            winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY,
        ) as handle:
            winreg.SetValueEx(handle, "untouched", 0, winreg.REG_SZ, "keep")
        self.addCleanup(
            winreg.DeleteKeyEx, winreg.HKEY_CURRENT_USER, key, winreg.KEY_WOW64_64KEY
        )
        config: dict[str, Any] = {
            "hive": "HKEY_CURRENT_USER",
            "key": key,
            "values": {
                "flag": {"type": "REG_DWORD", "data": 1},
                "text": {"type": "REG_SZ", "data": "hello"},
                "wide": {"type": "REG_QWORD", "data": 2**40},
                "paths": {"type": "REG_MULTI_SZ", "data": ["a", "b"]},
                "home": {"type": "REG_EXPAND_SZ", "data": "%USERPROFILE%"},
            },
        }
        context = Context(Path.cwd(), Path.cwd(), "test", {})
        provider = WindowsRegistryAction()
        plan = provider.plan(config, provider.inspect(config, context), context)
        self.assertTrue(provider.apply(plan, context).changed)
        self.assertFalse(provider.apply(plan, context).changed)
        second = provider.plan(config, provider.inspect(config, context), context)
        self.assertEqual(second.status, PlanStatus.SKIP)
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            key,
            0,
            winreg.KEY_QUERY_VALUE | winreg.KEY_WOW64_64KEY,
        ) as handle:
            self.assertEqual(
                winreg.QueryValueEx(handle, "untouched"), ("keep", winreg.REG_SZ)
            )
            for name, value in config["values"].items():
                self.assertEqual(
                    winreg.QueryValueEx(handle, name),
                    (value["data"], getattr(winreg, value["type"])),
                )
