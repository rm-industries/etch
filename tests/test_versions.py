import unittest

from etchlib.versions.constraints import matches
from etchlib.versions.parser import Version, extract_version, parse_version


class VersionTests(unittest.TestCase):
    def test_required_tool_formats(self) -> None:
        for output, expected in [
            ("2.9a", "2.9a"),
            ("3.5a", "3.5a"),
            ("v22.4.1", "22.4.1"),
            ("Python 3.12.2", "3.12.2"),
            ("git version 2.47.0", "2.47.0"),
            ("OpenSSH_9.8p1, OpenSSL 3.0.0", "9.8p1"),
            ("tmux 3.5a", "3.5a"),
        ]:
            with self.subTest(output=output):
                self.assertEqual(extract_version(output), expected)

    def test_normalization_and_patch_order(self) -> None:
        self.assertEqual(parse_version("v02.01.0"), parse_version("2.1"))
        self.assertEqual(Version((2, 1, 0)), parse_version("2.1"))
        self.assertEqual(hash(parse_version("2.1.0")), hash(parse_version("2.1")))
        for left, right in [
            ("2.9", "2.10"),
            ("3.5", "3.5a"),
            ("3.5a", "3.5b"),
            ("9.8p2", "9.8p10"),
            ("9.8p10", "9.9"),
            ("2.1", "2.1.1"),
        ]:
            with self.subTest(left=left, right=right):
                self.assertLess(parse_version(left), parse_version(right))

    def test_all_comparisons_and_conjunctions(self) -> None:
        for expression, expected in [
            ("==2.1", True),
            ("!=2.1", False),
            ("<2.1", False),
            ("<=2.1", True),
            (">2.1", False),
            (">=2.1", True),
            (">=2.1,<4", True),
            (">=3,<4", False),
            (" >= 2.1 , < 4 ", True),
        ]:
            with self.subTest(expression=expression):
                self.assertIs(matches("2.1.0", expression), expected)

    def test_tmux_boundary_selects_one_branch(self) -> None:
        for version, legacy in [
            ("2.0", True),
            ("2.1", False),
            ("2.9a", False),
            ("3.5a", False),
        ]:
            self.assertIs(matches(version, "<2.1"), legacy)
            self.assertIs(matches(version, ">=2.1"), not legacy)

    def test_rejects_unsupported_constraints_even_after_false_term(self) -> None:
        for expression in [
            "",
            "2.1",
            "^1.2",
            "~1.4",
            "==1.x",
            ">=2,",
            ">99,invalid",
            "==1.2.3-rc1",
            "==1.2+build",
        ]:
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                matches("2.1", expression)

    def test_bad_versions_are_not_truncated(self) -> None:
        for output in [
            "tool 1.2.3-rc1",
            "tool 1.2beta1",
            "tool 1.2+build",
            "tool 1.2..3",
            "no version",
            "warning\ntool 2.1",
        ]:
            with self.subTest(output=output), self.assertRaises(ValueError):
                extract_version(output)

    def test_only_first_nonempty_line_and_first_version_token(self) -> None:
        self.assertEqual(
            extract_version("\n\nTool v1.2 (library 3.4)\nother 5.6"), "1.2"
        )
