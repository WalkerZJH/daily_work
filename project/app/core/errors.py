from __future__ import annotations


class TerminalGuardError(Exception):
    pass


class DatasetLoadError(TerminalGuardError):
    pass


class UnitNotFoundError(TerminalGuardError):
    pass
