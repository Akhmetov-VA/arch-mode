"""Selecting what to show (suppressions, scope, --changed), the text and JSON report, the snapshot."""
from __future__ import annotations

import json
import re
from pathlib import Path

from archcheck.model import ERROR, Config, Finding, Module

SUPPRESS = re.compile(r"#\s*archcheck:\s*ignore(?:\[([^\]]*)\])?")


def suppressed(f: Finding, lines: dict[str, list[str]]) -> bool:
    text = lines.get(f.path, [])
    match = SUPPRESS.search(text[f.line - 1]) if f.line <= len(text) else None
    if not match:
        return False
    return match.group(1) is None or f.rule in {r.strip() for r in match.group(1).split(",")}


def _under(path: str, scope: str) -> bool:
    return scope in ("", ".") or path == scope or path.startswith(scope.rstrip("/") + "/")


def select(findings: list[Finding], modules: list[Module], config: Config,
           scopes: list[str], changed: set[str] | None) -> list[Finding]:
    lines = {m.path: m.lines for m in modules}
    keep = [f for f in findings
            if f.rule not in config.disable and not suppressed(f, lines)
            and (not scopes or any(_under(p, s) for p in (f.path, *f.related) for s in scopes))
            and (changed is None or any(p in changed for p in (f.path, *f.related)))]
    return sorted(keep, key=lambda f: (f.severity != ERROR, f.path, f.line, f.rule))


def build(config: Config, modules: list[Module], findings: list[Finding], packages: dict) -> dict:
    errors = sum(f.severity == ERROR for f in findings)
    return {"layers": [layer.name for layer in config.layers], "modules": len(modules),
            "packages": [p.as_dict() for p in packages.values()], "findings": [f.as_dict() for f in findings],
            "summary": {"errors": errors, "warnings": len(findings) - errors}}


def render(report: dict) -> str:
    layers = " -> ".join(report["layers"]) + " (inner -> outer)" if report["layers"] else "not configured"
    out = [f"archcheck: {report['modules']} modules in {len(report['packages'])} packages; layers: {layers}"]
    out += [f"{f['severity'].upper():8} {f['rule']:20} {f['path']}:{f['line']}  {f['message']}" for f in report["findings"]]
    out += ["", f"{'Package':32} {'Ca':>4} {'Ce':>4} {'Instability':>12} {'Abstractness':>13} {'Distance':>9}"]
    out += [f"{p['package']:32} {p['ca']:>4} {p['ce']:>4} {p['instability']:>12.2f} {p['abstractness']:>13.2f} "
            f"{p['distance']:>9.2f}" for p in report["packages"]]
    summary = report["summary"]
    out += ["", f"{_count(summary['errors'], 'error')}, {_count(summary['warnings'], 'warning')}"]
    return "\n".join(out)


def _count(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def to_json(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False)


def write_snapshot(root: Path, report: dict) -> None:
    path = root / ".metrics" / "arch.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(to_json(report), encoding="utf-8")
