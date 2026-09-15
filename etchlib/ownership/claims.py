"""Compare path claims without changing the filesystem."""

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, TypeVar

from etchlib.providers.plans import ClaimKind, PathClaim, Plan

Owner = TypeVar("Owner")


class OwnershipError(ValueError):
    """Invalid path or conflicting active owners."""


@dataclass(frozen=True)
class OwnedClaim:
    owner: object
    claim: PathClaim
    paths: tuple[Path, ...]


def normalize(owner: object, claim: PathClaim) -> OwnedClaim:
    try:
        lexical = Path(os.path.normpath(str(claim.path)))
        resolved = claim.path.parent.resolve() / claim.path.name
        if claim.path.name == "..":
            resolved = claim.path.resolve()
        parent = resolved.parent
        while True:
            try:
                mode = parent.stat().st_mode
                break
            except FileNotFoundError:
                if parent == parent.parent:
                    raise
                parent = parent.parent
        if not stat.S_ISDIR(mode):
            raise OwnershipError(
                "{}: parent is not a directory: {}".format(owner, parent)
            )
        if claim.kind is ClaimKind.SHARED_DIRECTORY:
            try:
                mode = resolved.stat().st_mode
            except FileNotFoundError as exc:
                if resolved.is_symlink():
                    raise OwnershipError(
                        "{}: broken directory symlink: {}".format(owner, resolved)
                    ) from exc
                mode = stat.S_IFDIR
            if not stat.S_ISDIR(mode):
                raise OwnershipError(
                    "{}: shared directory is not a directory: {}".format(
                        owner, resolved
                    )
                )
            resolved = resolved.resolve()
        return OwnedClaim(owner, claim, tuple(dict.fromkeys((lexical, resolved))))
    except (OSError, RuntimeError, ValueError) as exc:
        raise OwnershipError(
            "{}: invalid claim {}: {}".format(owner, claim.path, exc)
        ) from exc


def validate_claims(plans: Mapping[Owner, Plan]) -> tuple[OwnedClaim, ...]:
    """Include every active plan, even SKIP: satisfied state still has an owner."""
    claims: list[OwnedClaim] = []
    for owner, plan in plans.items():
        for claim in plan.claims:
            current = normalize(owner, claim)
            for previous in claims:
                if previous.owner == owner:
                    continue
                for left in previous.paths:
                    for right in current.paths:
                        conflict = left == right and (
                            previous.claim.kind is ClaimKind.EXCLUSIVE
                            or claim.kind is ClaimKind.EXCLUSIVE
                        )
                        conflict |= (
                            left in right.parents
                            and previous.claim.kind is ClaimKind.EXCLUSIVE
                        )
                        conflict |= (
                            right in left.parents and claim.kind is ClaimKind.EXCLUSIVE
                        )
                        if conflict:
                            raise OwnershipError(
                                "destination conflict: {} ({}) and {} ({})".format(
                                    previous.owner, left, owner, right
                                )
                            )
            claims.append(current)
    return tuple(claims)
