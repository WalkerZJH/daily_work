"""Guarded cleanup for alive prediction temporary cache files."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


PROTECTED_DATA_PARTS = {"03_cleaned", "04_facts", "05_features", "06_train_sets"}


@dataclass(frozen=True)
class CleanupCandidate:
    path: Path
    artifact_name: str
    created_at: str
    size: int
    reason_for_cleanup: str


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def assert_cleanup_allowed(path: str | Path, cache_root: str | Path) -> None:
    target = Path(path).resolve()
    root = Path(cache_root).resolve()
    if any(part in PROTECTED_DATA_PARTS for part in target.parts):
        raise PermissionError(f"Refusing to delete protected data-layer artifact: {target}")
    if not _is_under(target, root):
        raise PermissionError(f"Refusing to delete outside cleanup root {root}: {target}")


def plan_cache_cleanup(
    cache_root: str | Path,
    *,
    older_than_days: int | None = None,
    keep_latest: bool = False,
) -> list[CleanupCandidate]:
    root = Path(cache_root)
    if not root.exists():
        return []
    cutoff = None
    if older_than_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    files = sorted([path for path in root.rglob("*") if path.is_file()], key=lambda path: path.stat().st_mtime, reverse=True)
    if keep_latest and files:
        files = files[1:]
    candidates: list[CleanupCandidate] = []
    for path in files:
        stat = path.stat()
        created = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
        if cutoff is not None and created >= cutoff:
            continue
        reason = "older_than_days" if older_than_days is not None else "manual_dry_run"
        if keep_latest:
            reason = f"{reason};keep_latest"
        candidates.append(
            CleanupCandidate(
                path=path,
                artifact_name=path.stem,
                created_at=created.isoformat(),
                size=int(stat.st_size),
                reason_for_cleanup=reason,
            )
        )
    return candidates


def clean_cache(
    cache_root: str | Path,
    *,
    older_than_days: int | None = None,
    keep_latest: bool = False,
    dry_run: bool = True,
    confirm: bool = False,
) -> list[CleanupCandidate]:
    candidates = plan_cache_cleanup(cache_root, older_than_days=older_than_days, keep_latest=keep_latest)
    if dry_run or not confirm:
        return candidates
    for candidate in candidates:
        assert_cleanup_allowed(candidate.path, cache_root)
        candidate.path.unlink()
    return candidates
