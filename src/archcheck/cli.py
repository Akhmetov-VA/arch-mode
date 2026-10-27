"""archcheck [paths...] [--changed] [--strict] [--json] [--no-write] [--root DIR]

Exit code: 0 clean, 1 errors (or warnings with --strict), 2 configuration or git problem.
"""
from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

from archcheck import checks, components, layers, report
from archcheck.config import ConfigError, load
from archcheck.source import load_modules


class GitError(Exception):
    pass


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="archcheck", description="Architecture gate for arch-mode.")
    p.add_argument("paths", nargs="*", help="report only findings under these paths (relative to --root)")
    p.add_argument("--root", default=".", help="project root (default: current directory)")
    p.add_argument("--changed", action="store_true", help="report only files changed or added in git")
    p.add_argument("--strict", action="store_true", help="warnings fail the run too")
    p.add_argument("--json", action="store_true", help="print the report as JSON")
    p.add_argument("--no-write", action="store_true", help="do not write .metrics/arch.json")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = Path(args.root).resolve()
    try:
        config = load(root)
        changed = changed_files(root) if args.changed else None
    except (ConfigError, GitError) as exc:
        print(f"archcheck: {exc}")
        return 2
    modules, problems = load_modules(root, config)
    edges = components.project_edges(modules)
    graph = components.package_graph(modules, edges)
    packages = components.metrics(modules, graph)
    found = (problems + layers.dependency_rule(config.layers, edges) + layers.pure_layer(config.layers, modules)
             + components.cycles(graph) + components.unstable_dependencies(graph, packages)
             + checks.deep_inheritance(modules) + [f for m in modules for f in checks.module_checks(m)])
    findings = report.select(found, modules, config, [_scope(root, p) for p in args.paths], changed)
    result = report.build(config, modules, findings, packages)
    if not args.no_write:
        report.write_snapshot(root, result)
    print(report.to_json(result) if args.json else report.render(result))
    failed = result["summary"]["errors"] or (args.strict and result["summary"]["warnings"])
    return 1 if failed else 0


def _scope(root: Path, path: str) -> str:
    absolute = Path(path) if Path(path).is_absolute() else root / path
    return Path(os.path.relpath(absolute, root)).as_posix()


def _git(root: Path, *args: str) -> str | None:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else None


def changed_files(root: Path) -> set[str]:
    untracked = _git(root, "ls-files", "--others", "--exclude-standard")
    if untracked is None:
        raise GitError("--changed needs a git repository")
    diff = _git(root, "diff", "--name-only", "--relative", "HEAD") or ""
    return {line for line in (diff + untracked).splitlines() if line}
