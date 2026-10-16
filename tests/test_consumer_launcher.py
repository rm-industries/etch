"""Consumer launcher regressions belong to core, not consumer setup CI."""

import os
import platform
import shutil
import subprocess
from unittest import skipUnless

from tests.bootstrap_fixtures import ROOT, BootstrapFixture


@skipUnless(platform.system() in ("Linux", "Darwin"), "POSIX consumer launcher")
class ConsumerLauncherTests(BootstrapFixture):
    def test_direct_path_and_symlink_invocation_preserve_consumer_and_arguments(
        self,
    ) -> None:
        self.vendor()
        launcher = self.consumer / "etch"
        shutil.copy2(ROOT / "examples/minimal/etch", launcher)
        env = dict(self.env, PATH=str(self.bin) + os.pathsep + os.defpath)
        absolute = self.bin / "etch"
        absolute.symlink_to(launcher)
        relative = self.bin / "relative"
        relative.symlink_to(os.path.relpath(launcher, self.bin))
        chain = self.bin / "chain"
        chain.symlink_to("relative")
        for executable in (
            str(launcher),
            str(absolute),
            str(relative),
            str(chain),
            "etch",
        ):
            for args in ((), ("validate",), ("plan", "--profile", "developer")):
                with self.subTest(executable=executable, args=args):
                    result = subprocess.run(
                        [executable, *args],
                        cwd=self.root,
                        env=env,
                        text=True,
                        capture_output=True,
                        timeout=15,
                    )
                    self.assertEqual(
                        result.returncode, 0, result.stdout + result.stderr
                    )
                    if not args or args[0] == "plan":
                        self.assertIn(str(self.consumer.resolve()), result.stdout)
            result = subprocess.run(
                [executable, "plan", "--profile", "does not exist"],
                cwd=self.root,
                env=env,
                text=True,
                capture_output=True,
                timeout=15,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("does not exist", result.stderr)
        self.assertFalse((self.root / "home/.gitconfig").exists())
        for name, target in (
            ("dangling", "missing"),
            ("cycle-a", "cycle-b"),
            ("cycle-b", "cycle-a"),
        ):
            (self.bin / name).symlink_to(target)
        for name in ("dangling", "cycle-a"):
            result = subprocess.run(
                ["/bin/sh", str(self.bin / name)],
                cwd=self.root,
                env=env,
                text=True,
                capture_output=True,
                timeout=5,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(result.stderr)
