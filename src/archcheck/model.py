"""Data shapes shared by every check."""
from __future__ import annotations

import ast
from dataclasses import dataclass, field

ERROR = "error"
WARNING = "warning"


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str
    path: str
    line: int
    message: str
    related: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {"rule": self.rule, "severity": self.severity, "path": self.path, "line": self.line,
                "message": self.message, "related": list(self.related)}


@dataclass(frozen=True)
class Layer:
    """A ring of the architecture. Layers are listed from the innermost to the outermost."""
    name: str
    modules: tuple[str, ...]
    pure: bool = False
    forbid: tuple[str, ...] = ()

    def claim(self, module: str) -> int:
        """Length of this layer's longest module prefix that contains module; 0 when it does not."""
        return max((len(p) for p in self.modules if module == p or module.startswith(p + ".")), default=0)


@dataclass(frozen=True)
class Config:
    layers: tuple[Layer, ...] = ()
    roots: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    disable: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Import:
    name: str        # absolute dotted name; relative imports are already resolved against the package
    line: int
    relative: bool


@dataclass
class Module:
    name: str        # dotted module name
    path: str        # posix path relative to the project root
    package: str     # dotted package; "." for files that sit directly in a source root
    tree: ast.Module | None
    lines: list[str]
    imports: list[Import] = field(default_factory=list)


@dataclass(frozen=True)
class Edge:
    """source imports the project module target at line."""
    source: Module
    target: str
    line: int
