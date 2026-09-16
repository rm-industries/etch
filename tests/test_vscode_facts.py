from etchlib.config import load_repository
from etchlib.execution.results import Status
from etchlib.execution.runner import apply_repository
from etchlib.facts.repository import repository_facts
from etchlib.providers.observations import FactRef, FactState
from tests.vscode_fixtures import VSCodeFixture


class VSCodeFactTests(VSCodeFixture):
    def declare(self) -> None:
        self.module(
            facts={
                kind: {"vscode." + kind: {"command": str(self.code)}}
                for kind in ("command", "version", "extensions")
            }
        )

    def test_command_version_and_normalized_extension_facts(self) -> None:
        self.state(extensions=["Zzz.Last", "aaa.first", "AAA.First"])
        self.declare()
        store = repository_facts(load_repository(self.root), self.registry)
        self.assertEqual(store.get(FactRef("demo", "command")).value, str(self.code))
        self.assertEqual(self.calls(), [])
        self.assertEqual(store.get(FactRef("demo", "version")).value, "1.105.0")
        self.assertEqual(
            store.get(FactRef("demo", "extensions")).value, ["aaa.first", "zzz.last"]
        )
        self.assertEqual(
            store.get(FactRef("demo", "extensions")).value, ["aaa.first", "zzz.last"]
        )
        self.assertEqual(len(self.calls()), 2)

    def test_missing_command_facts_are_unavailable(self) -> None:
        self.declare()
        self.code.unlink()
        store = repository_facts(load_repository(self.root), self.registry)
        for kind in ("command", "version", "extensions"):
            self.assertEqual(
                store.get(FactRef("demo", kind)).state, FactState.UNAVAILABLE
            )
        self.assertEqual(self.calls(), [])

    def test_cli_failure_is_an_error_fact(self) -> None:
        self.declare()
        self.state(fail="--list-extensions")
        store = repository_facts(load_repository(self.root), self.registry)
        result = store.get(FactRef("demo", "extensions"))
        self.assertEqual(result.state, FactState.ERROR)
        self.assertIn("status 7", result.reason or "")

    def test_successful_changes_refresh_facts_and_activate_configuration(self) -> None:
        self.module(
            facts={"extensions": {"vscode.extensions": {"command": str(self.code)}}},
            actions=[
                {
                    "vscode": {
                        "command": str(self.code),
                        "extensions": ["ms-python.python"],
                    },
                    "refresh": ["extensions"],
                },
                {
                    "create": ["configured"],
                    "when": {
                        "fact": {"name": "extensions", "equals": ["ms-python.python"]}
                    },
                },
            ],
        )
        repository = load_repository(self.root)
        first = apply_repository(repository, self.registry, jobs=2)
        self.assertTrue(first.succeeded, first.error)
        self.assertTrue((self.root / "configured").is_dir())
        fact = first.facts[FactRef("demo", "extensions")]
        assert fact is not None
        self.assertEqual(fact.value, ["ms-python.python"])
        second = apply_repository(repository, self.registry, jobs=2)
        self.assertTrue(second.succeeded, second.error)
        self.assertTrue(
            all(result.status is Status.SKIPPED for result in second.actions)
        )
        self.assertEqual(
            len([call for call in self.calls() if call[0] == "--install-extension"]), 1
        )

    def test_failed_install_does_not_refresh_or_configure(self) -> None:
        self.state(extensions=[], fail_extension="ms-python.python")
        self.module(
            facts={"extensions": {"vscode.extensions": {"command": str(self.code)}}},
            actions=[
                {
                    "vscode": {
                        "command": str(self.code),
                        "extensions": ["ms-python.python"],
                    },
                    "refresh": ["extensions"],
                },
                {
                    "create": ["configured"],
                    "when": {
                        "fact": {"name": "extensions", "equals": ["ms-python.python"]}
                    },
                },
            ],
        )
        report = apply_repository(load_repository(self.root), self.registry)
        self.assertFalse(report.succeeded)
        self.assertEqual(report.actions[1].status, Status.BLOCKED)
        self.assertFalse((self.root / "configured").exists())
        fact = report.facts[FactRef("demo", "extensions")]
        assert fact is not None
        self.assertEqual(fact.value, [])
