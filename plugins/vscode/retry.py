"""Bounded recovery for recognized Marketplace service failures."""

import sys
from time import sleep

from etchlib.providers.contracts import Context

from .cli import InstallError, installed, run
from .schema import Target


def install(
    executable: str, target: Target, extension: str, retries: int, context: Context
) -> set[str]:
    for attempt in range(retries + 1):
        try:
            run(executable, target, ("--install-extension", extension), context)
        except InstallError as exc:
            if not retries or not exc.transient:
                raise
            # A failed invocation can still have installed the requested extension.
            current = set(installed(executable, target, context))
            if extension in current:
                return current
            if attempt == retries:
                raise
            delay = 2**attempt
            print(
                "VS Code {}: transient service failure; retry {}/{} in {}s".format(
                    extension, attempt + 1, retries, delay
                ),
                file=sys.stderr,
            )
            sleep(delay)
            continue
        current = set(installed(executable, target, context))
        if extension not in current:
            raise ValueError(
                "VS Code reported success but extension remains missing: " + extension
            )
        return current
    raise AssertionError("retry loop did not return or raise")
