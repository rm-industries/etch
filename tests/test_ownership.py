import tempfile
import unittest
from pathlib import Path

from etchlib.ownership.claims import OwnershipError, validate_claims
from etchlib.providers.plans import ClaimKind, PathClaim, Plan, PlanStatus


class OwnershipTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def plan(
        self,
        path: Path,
        kind: ClaimKind = ClaimKind.EXCLUSIVE,
        status: PlanStatus = PlanStatus.CHANGE,
    ) -> Plan:
        return Plan(status, "claim", claims=(PathClaim(path, kind),))

    def test_same_destination_conflicts_even_for_skip(self) -> None:
        plans = {
            "one": self.plan(self.root / "file"),
            "two": self.plan(self.root / "file", status=PlanStatus.SKIP),
        }
        with self.assertRaisesRegex(OwnershipError, "destination conflict.*one.*two"):
            validate_claims(plans)

    def test_shared_directories_and_child_files_are_compatible(self) -> None:
        directory = self.root / "config"
        result = validate_claims(
            {
                "one": self.plan(directory, ClaimKind.SHARED_DIRECTORY),
                "two": self.plan(directory, ClaimKind.SHARED_DIRECTORY),
                "three": self.plan(directory / "app.conf"),
            }
        )
        self.assertEqual(len(result), 3)

    def test_exclusive_parent_conflicts_in_either_order(self) -> None:
        parent, child = (
            self.plan(self.root / "config"),
            self.plan(self.root / "config/file"),
        )
        for plans in [
            {"parent": parent, "child": child},
            {"child": child, "parent": parent},
        ]:
            with self.assertRaises(OwnershipError):
                validate_claims(plans)

    def test_siblings_do_not_conflict(self) -> None:
        validate_claims(
            {"one": self.plan(self.root / "one"), "two": self.plan(self.root / "two")}
        )

    def test_parent_symlink_aliases_conflict(self) -> None:
        real = self.root / "real"
        real.mkdir()
        alias = self.root / "alias"
        alias.symlink_to(real)
        with self.assertRaises(OwnershipError):
            validate_claims(
                {"one": self.plan(real / "file"), "two": self.plan(alias / "file")}
            )

    def test_exclusive_final_symlink_does_not_own_its_target(self) -> None:
        target = self.root / "target"
        target.write_text("hello")
        link = self.root / "link"
        link.symlink_to(target)
        validate_claims({"link": self.plan(link), "target": self.plan(target)})

    def test_replacing_symlink_parent_conflicts_with_child(self) -> None:
        real = self.root / "real"
        real.mkdir()
        alias = self.root / "alias"
        alias.symlink_to(real)
        with self.assertRaises(OwnershipError):
            validate_claims(
                {"link": self.plan(alias), "child": self.plan(alias / "file")}
            )

    def test_shared_directory_aliases_are_compatible(self) -> None:
        real = self.root / "real"
        real.mkdir()
        alias = self.root / "alias"
        alias.symlink_to(real)
        validate_claims(
            {
                "one": self.plan(alias, ClaimKind.SHARED_DIRECTORY),
                "two": self.plan(real, ClaimKind.SHARED_DIRECTORY),
            }
        )

    def test_regular_file_cannot_be_parent_or_shared_directory(self) -> None:
        path = self.root / "file"
        path.write_text("data")
        for plan in [
            self.plan(path, ClaimKind.SHARED_DIRECTORY),
            self.plan(path / "child"),
        ]:
            with self.assertRaises(OwnershipError):
                validate_claims({"one": plan})
