"""Extension execution reconciles inventory without repeated planning probes."""

from etchlib.config import load_repository
from etchlib.execution.runner import apply_repository
from tests.vscode_fixtures import VSCodeFixture


class VSCodeEfficiencyTests(VSCodeFixture):
    def test_unrelated_execution_keeps_extension_intent(self) -> None:
        self.module(
            actions=[
                {"create": ["first"]},
                {"create": ["second"]},
                {
                    "vscode": {
                        "command": str(self.code),
                        "extensions": ["publisher.tool"],
                    }
                },
            ]
        )
        report = apply_repository(load_repository(self.root), self.registry)
        self.assertTrue(report.succeeded, report.error)
        self.assertEqual(sum(c[0] == "--list-extensions" for c in self.calls()), 3)
        self.assertIn("publisher.tool", self.current()["extensions"])

    def test_inventory_is_scoped_to_profile_and_snapshot(self) -> None:
        from etchlib.planning.build import plan_repository

        self.state(extensions=["publisher.tool"])
        for name, profile in (("a", "one"), ("b", "one"), ("c", "two")):
            self.module(
                name,
                actions=[
                    {
                        "vscode": {
                            "command": str(self.code),
                            "profile": profile,
                            "extensions": ["publisher.tool"],
                        }
                    }
                ],
            )
        repository = load_repository(self.root)
        plan_repository(repository, self.registry)
        self.assertEqual(sum(c[0] == "--list-extensions" for c in self.calls()), 2)
        self.state(extensions=[])
        report = apply_repository(repository, self.registry)
        self.assertTrue(report.succeeded, report.error)
        self.assertTrue(any(c[0] == "--install-extension" for c in self.calls()))
