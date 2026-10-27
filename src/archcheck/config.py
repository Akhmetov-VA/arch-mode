"""Reads [tool.archcheck] from pyproject.toml, or the top level of .archcheck.toml."""
from __future__ import annotations

from pathlib import Path

from archcheck.model import Config, Layer

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    tomllib = None

TOP_KEYS = {"layers", "roots", "exclude", "disable"}
LAYER_KEYS = {"name", "modules", "pure", "forbid"}


class ConfigError(Exception):
    pass


def load(root: Path) -> Config:
    return parse(_table(root))


def _read(path: Path) -> dict:
    if tomllib is None:
        raise ConfigError(f"{path.name}: reading TOML needs Python 3.11 or newer")
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path.name}: {exc}") from None


def _table(root: Path) -> dict:
    pyproject = root / "pyproject.toml"
    if pyproject.is_file() and "archcheck" in pyproject.read_text(encoding="utf-8"):
        table = _read(pyproject).get("tool", {}).get("archcheck")
        if table is not None:
            return table
    own = root / ".archcheck.toml"
    return _read(own) if own.is_file() else {}


def parse(table: dict) -> Config:
    _no_unknown(table, TOP_KEYS, "[tool.archcheck]")
    layers = tuple(_layer(n, raw) for n, raw in enumerate(table.get("layers", []), 1))
    return Config(layers=layers, roots=tuple(table.get("roots", ())), exclude=tuple(table.get("exclude", ())),
                  disable=frozenset(table.get("disable", ())))


def _layer(number: int, raw: dict) -> Layer:
    name = raw.get("name", f"layer {number}")
    _no_unknown(raw, LAYER_KEYS, f"layer '{name}'")
    if not raw.get("modules"):
        raise ConfigError(f"layer '{name}' lists no modules")
    return Layer(name, tuple(raw["modules"]), bool(raw.get("pure", False)), tuple(raw.get("forbid", ())))


def _no_unknown(table: dict, known: set[str], where: str) -> None:
    unknown = sorted(set(table) - known)
    if unknown:
        raise ConfigError(f"{where}: unknown keys {', '.join(unknown)}")
