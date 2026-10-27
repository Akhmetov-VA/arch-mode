"""Each test builds a small project on disk and runs archcheck on it the way a user does."""
import json
import subprocess
import textwrap
from pathlib import Path

import pytest

from archcheck.cli import main


class Project:
    def __init__(self, root: Path, capsys):
        self.root = root
        self._capsys = capsys

    def write(self, files: dict[str, str]) -> "Project":
        for rel, text in files.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(textwrap.dedent(text).lstrip("\n"))
        return self

    def layers(self, toml: str) -> "Project":
        return self.write({"pyproject.toml": toml})

    def run(self, *args: str) -> tuple[int, str]:
        self._capsys.readouterr()
        code = main(["--root", str(self.root), *args])
        return code, self._capsys.readouterr().out

    def report(self, *args: str) -> dict:
        code, out = self.run("--json", *args)
        data = json.loads(out)
        data["exit"] = code
        return data

    def findings(self, *args: str, rule: str | None = None) -> list[dict]:
        found = self.report(*args)["findings"]
        return [f for f in found if rule is None or f["rule"] == rule]

    def git(self, *args: str) -> None:
        subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)

    def commit_all(self) -> None:
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init")


@pytest.fixture
def project(tmp_path, capsys) -> Project:
    return Project(tmp_path, capsys)


LAYERED = """
[[tool.archcheck.layers]]
name = "domain"
modules = ["shop.domain"]
pure = true

[[tool.archcheck.layers]]
name = "app"
modules = ["shop.app"]

[[tool.archcheck.layers]]
name = "adapters"
modules = ["shop.adapters"]
"""
