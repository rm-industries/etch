"""Exercise both bootstraps with real local Git repositories and a tiny Etch fixture."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1] / "examples/minimal"
REAL_GIT = shutil.which("git") or ""
WINDOWS = os.name == "nt"
HOSTS = (
    [shutil.which("pwsh.exe"), shutil.which("powershell.exe")]
    if WINDOWS
    else ["/bin/sh"]
)
HOSTS = [h for h in HOSTS if h]


@unittest.skipUnless(REAL_GIT, "Git is required for installer fixtures")
class InstallerTests(unittest.TestCase):
    host: str
    fixture: tempfile.TemporaryDirectory[str]
    base: Path
    env: dict[str, str]
    engine: Path
    source: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = tempfile.TemporaryDirectory(prefix="dotfiles installer fixtures ")
        cls.base = Path(cls.fixture.name)
        cls.env = dict(
            os.environ,
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_ALLOW_PROTOCOL="file",
            GIT_AUTHOR_NAME="Installer Test",
            GIT_AUTHOR_EMAIL="test@example.invalid",
            GIT_COMMITTER_NAME="Installer Test",
            GIT_COMMITTER_EMAIL="test@example.invalid",
            GIT_TERMINAL_PROMPT="0",
        )
        cls.engine = cls.base / "engine"
        cls.source = cls.base / "source"
        for path in [cls.engine, cls.source]:
            path.mkdir()
            cls.git("init", str(path))
        (cls.engine / "etch").write_text(
            "import json,os,sys\nfrom pathlib import Path\n"
            'Path(os.environ["MODULE_LOG"]).write_text(json.dumps(sys.argv[1:]))\n'
            'sys.exit(int(os.environ.get("MODULE_EXIT", "0")))\n'
        )
        support = cls.base / "nested support"
        support.mkdir()
        cls.git("init", str(support))
        (support / "pinned").write_text("nested fixture\n")
        cls.git("-C", str(support), "add", ".")
        cls.git("-C", str(support), "commit", "-m", "Nested fixture")
        cls.git(
            "-C", str(cls.engine), "submodule", "add", str(support), "runtime/support"
        )
        cls.git("-C", str(cls.engine), "add", ".")
        cls.git("-C", str(cls.engine), "commit", "-m", "Fixture engine")
        cls.git(
            "-C", str(cls.source), "submodule", "add", str(cls.engine), "vendor/etch"
        )
        (cls.source / "README").write_text("Fixture checkout\n")
        cls.git("-C", str(cls.source), "add", ".")
        cls.git("-C", str(cls.source), "commit", "-m", "Fixture dotfiles")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.fixture.cleanup()

    @classmethod
    def git(cls, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [REAL_GIT, *args],
            env=cls.env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="dotfiles bootstrap test ")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.destination = self.base / "checkout with spaces"
        self.installer_root = self.base / "installer scripts"
        self.installer_root.mkdir()
        for name in ("install.sh", "install.ps1"):
            shutil.copy2(ROOT / name, self.installer_root / name)
        self.log = self.base / "git.jsonl"
        self.module_log = self.base / "module.json"
        helper = self.bin / "git_helper.py"
        helper.write_text("""import json,os,subprocess,sys
from pathlib import Path
args=sys.argv[1:]
with open(os.environ['GIT_LOG'],'a') as log: log.write(json.dumps(args)+'\\n')
if args[0]=='clone' and os.environ.get('CLONE_EXIT'):
 if os.environ.get('PARTIAL_CLONE'):
  Path(args[-1]).mkdir(); (Path(args[-1])/'partial').write_text('retained')
 sys.exit(int(os.environ['CLONE_EXIT']))
if 'submodule' in args and 'update' in args and os.environ.get('SUBMODULE_EXIT'): sys.exit(int(os.environ['SUBMODULE_EXIT']))
clone=args[0]=='clone'
if clone:
 if args[-2] != os.environ['EXPECTED_REPOSITORY']: sys.exit(99)
 args[-2]=os.environ['FIXTURE_SOURCE']
result=subprocess.run([os.environ['REAL_GIT'],*args])
if clone and result.returncode==0:
 result=subprocess.run([os.environ['REAL_GIT'],'-C',args[-1],'remote','set-url','origin',os.environ['EXPECTED_REPOSITORY']])
sys.exit(result.returncode)
""")
        if WINDOWS:
            (self.bin / "git.cmd").write_text(
                f'@"{sys.executable}" "{helper}" %*\n@exit /b %errorlevel%\n'
            )
        else:
            wrapper = self.bin / "git"
            wrapper.write_text(
                f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(helper))} "$@"\n'
            )
            wrapper.chmod(0o755)
        self.env = dict(
            self.__class__.env,
            PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
            DOTFILES_DIR=str(self.destination),
            REAL_GIT=REAL_GIT,
            FIXTURE_SOURCE=str(self.source),
            EXPECTED_REPOSITORY="https://github.com/generated-owner/generated-dotfiles.git",
            GIT_LOG=str(self.log),
            MODULE_LOG=str(self.module_log),
        )

    def run_installer(
        self,
        *args: str,
        env: Optional[dict[str, str]] = None,
        expected: int = 0,
        repository: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        host = self.host
        if WINDOWS:
            harness = self.base / "invoke.ps1"
            installer = str(self.installer_root / "install.ps1").replace("'", "''")
            harness.write_text(
                "$PSNativeCommandUseErrorActionPreference = $true\n"
                + f"& '{installer}' @args\nexit $LASTEXITCODE\n"
            )
            command = [
                host,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(harness),
            ]
        else:
            command = [host, str(self.installer_root / "install.sh")]
        selected = (
            ["--repo", (env or self.env)["EXPECTED_REPOSITORY"]] if repository else []
        )
        result = subprocess.run(
            [*command, *selected, *args],
            env=env or self.env,
            cwd=self.base,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def calls(self) -> list[list[str]]:
        return (
            [json.loads(line) for line in self.log.read_text().splitlines()]
            if self.log.exists()
            else []
        )

    def test_default_is_clone_only_and_initializes_submodules(self) -> None:
        self.run_installer()
        self.assertTrue((self.destination / "vendor/etch/etch").is_file())
        self.assertFalse(self.module_log.exists())
        self.assertEqual(
            (self.destination / "vendor/etch/runtime/support/pinned").read_text(),
            "nested fixture\n",
        )
        self.assertEqual(
            self.calls()[0],
            ["clone", "--", self.env["EXPECTED_REPOSITORY"], str(self.destination)],
        )

    def test_repository_url_is_required_without_owner_customization(self) -> None:
        result = self.run_installer(repository=False, expected=2)
        self.assertIn("repository", result.stderr.lower())
        self.assertFalse(self.calls())
        self.assertFalse(self.destination.exists())

    def configure_owner(self, *, repository: str = "", module: str = "") -> None:
        shell = self.installer_root / "install.sh"
        shell.write_text(
            shell.read_text()
            .replace("repository=''", "repository='" + repository + "'", 1)
            .replace("module=''", "module='" + module + "'", 1)
        )
        powershell = self.installer_root / "install.ps1"
        powershell.write_text(
            powershell.read_text()
            .replace("$repository = ''", "$repository = '" + repository + "'", 1)
            .replace("$module = ''", "$module = '" + module + "'", 1)
        )

    def test_owner_configured_repository_and_default_module(self) -> None:
        self.configure_owner(repository=self.env["EXPECTED_REPOSITORY"], module="etch")
        self.run_installer(repository=False)
        self.assertEqual(
            json.loads(self.module_log.read_text()),
            ["apply", "etch", "--repo", str(self.destination)],
        )

    def test_explicit_repository_overrides_owner_default(self) -> None:
        self.configure_owner(repository="https://github.com/another-owner/old-repo.git")
        env = dict(
            self.env,
            EXPECTED_REPOSITORY="https://github.com/new-owner/new-generated-repo.git",
        )
        self.run_installer(env=env)
        self.assertEqual(self.calls()[0][-2], env["EXPECTED_REPOSITORY"])

    def test_no_module_overrides_owner_default(self) -> None:
        self.configure_owner(module="etch")
        self.run_installer("--no-module")
        self.assertFalse(self.module_log.exists())

    def test_existing_ssh_origin_is_the_same_repository(self) -> None:
        self.run_installer()
        self.git(
            "-C",
            str(self.destination),
            "remote",
            "set-url",
            "origin",
            "git@github.com:generated-owner/generated-dotfiles.git",
        )
        self.log.unlink()
        self.run_installer("--module", "git")
        self.assertFalse(
            any(
                "clone" in call or "submodule" in call or "pull" in call
                for call in self.calls()
            )
        )
        self.assertFalse(self.module_log.exists())

    def test_override(self) -> None:
        self.configure_owner(module="etch")
        self.run_installer("--module", "git")
        self.assertEqual(json.loads(self.module_log.read_text())[1], "git")

    def test_clone_only_precedence(self) -> None:
        for args in [
            ("--no-module", "--module", "git"),
            ("--module", "git", "--no-module"),
        ]:
            self.env["DOTFILES_DIR"] = str(self.destination) + str(len(self.calls()))
            self.run_installer(*args)
            self.assertFalse(self.module_log.exists())

    def test_existing_checkout_is_strict_noop(self) -> None:
        self.run_installer("--no-module")
        (self.destination / "README").write_text("User changes\n")
        self.log.unlink()
        unavailable = self.bin / ("python.cmd" if WINDOWS else "python3")
        unavailable.write_text("@exit /b 127\n" if WINDOWS else "#!/bin/sh\nexit 127\n")
        unavailable.chmod(0o755)
        self.run_installer("--module", "git")
        self.assertEqual((self.destination / "README").read_text(), "User changes\n")
        self.assertFalse(self.module_log.exists())
        self.assertTrue(
            all(
                "clone" not in c and "submodule" not in c and "pull" not in c
                for c in self.calls()
            )
        )

    def test_unrelated_occupied_directory(self) -> None:
        self.destination.mkdir()
        sentinel = self.destination / "user-data"
        sentinel.write_text("Keep me")
        self.run_installer(expected=1)
        self.assertEqual(sentinel.read_text(), "Keep me")
        self.assertFalse(self.calls())

    def test_dangling_destination_is_not_replaced(self) -> None:
        missing = self.base / "missing target"
        self.destination.symlink_to(missing, target_is_directory=True)
        original_target = os.readlink(self.destination)
        self.run_installer(expected=1)
        self.assertTrue(self.destination.is_symlink())
        self.assertEqual(os.readlink(self.destination), original_target)
        self.assertFalse(self.calls())

    def test_unrelated_repository(self) -> None:
        self.destination.mkdir()
        self.git("init", str(self.destination))
        self.git(
            "-C",
            str(self.destination),
            "remote",
            "add",
            "origin",
            "https://example.invalid/other.git",
        )
        self.run_installer(expected=1)
        self.assertFalse(any(c[0] == "clone" for c in self.calls()))

    def test_invalid_arguments(self) -> None:
        for args in [
            ("--unknown",),
            ("--module",),
            ("--module", ""),
            ("--module", "--help"),
            ("--repo",),
            ("--repo", ""),
            ("--repo", "--help"),
        ]:
            self.run_installer(*args, expected=2)
        self.assertFalse(self.destination.exists())
        self.assertFalse(self.calls())

    def test_help(self) -> None:
        self.run_installer("--help", repository=False)
        self.assertFalse(self.calls())

    def test_missing_git(self) -> None:
        empty = self.base / "empty"
        empty.mkdir()
        env = dict(self.env, PATH=str(empty))
        result = self.run_installer(env=env, expected=127)
        self.assertIn("Git is required", result.stderr)

    def test_python_unavailable_and_clone_only(self) -> None:
        name = "python.cmd" if WINDOWS else "python3"
        unavailable = self.bin / name
        unavailable.write_text("@exit /b 127\n" if WINDOWS else "#!/bin/sh\nexit 127\n")
        unavailable.chmod(0o755)
        self.run_installer("--module", "etch", expected=127)
        self.assertFalse(self.destination.exists())
        self.run_installer()
        self.assertTrue((self.destination / "vendor/etch/etch").exists())
        self.assertFalse(self.module_log.exists())

    def test_repository_without_origin(self) -> None:
        self.destination.mkdir()
        self.git("init", str(self.destination))
        self.run_installer(expected=1)

    def test_clone_failure(self) -> None:
        self.run_installer(env=dict(self.env, CLONE_EXIT="41"), expected=41)
        self.assertFalse(self.destination.exists())

    def test_partial_clone_is_retained_and_rerun_does_not_repair(self) -> None:
        self.run_installer(
            env=dict(self.env, CLONE_EXIT="41", PARTIAL_CLONE="1"), expected=41
        )
        self.assertEqual((self.destination / "partial").read_text(), "retained")
        self.log.unlink()
        self.run_installer(expected=1)
        self.assertEqual((self.destination / "partial").read_text(), "retained")
        self.assertFalse(self.calls())

    def test_invalid_owner_module_is_rejected_before_cloning(self) -> None:
        self.configure_owner(module="bad/name")
        self.run_installer(expected=2)
        self.assertFalse(self.calls())
        self.assertFalse(self.destination.exists())

    def test_submodule_failure(self) -> None:
        self.run_installer(env=dict(self.env, SUBMODULE_EXIT="43"), expected=43)
        self.assertTrue(self.destination.exists())
        self.assertFalse(self.module_log.exists())

    def test_module_failure(self) -> None:
        self.run_installer(
            "--module", "etch", env=dict(self.env, MODULE_EXIT="47"), expected=47
        )
        self.assertTrue(self.destination.exists())


# Run the same behavioral contract under sh or both Windows PowerShell hosts.
for index, host in enumerate(HOSTS):
    globals()[f"InstallerHost{index}Tests"] = type(
        f"InstallerHost{index}Tests", (InstallerTests,), {"host": host}
    )
del InstallerTests

if __name__ == "__main__":
    unittest.main()
