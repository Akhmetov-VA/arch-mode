"""What the user sees: exit codes, text report, suppressions, --changed, excludes, the snapshot file."""
import json

NO_TIMEOUT = "import requests\nrequests.get(url)\n"
GLOBAL = "x = 0\ndef f():\n    global x\n"


def test_errors_fail_the_run(project):
    project.write({"app.py": NO_TIMEOUT})
    code, out = project.run()
    assert code == 1
    assert "ERROR" in out and "network-timeout" in out and "app.py:2" in out
    assert "1 error, 0 warnings" in out


def test_warnings_alone_pass_unless_strict(project):
    project.write({"app.py": GLOBAL})
    assert project.run()[0] == 0
    assert project.run("--strict")[0] == 1


def test_clean_project_passes(project):
    project.write({"app.py": "def f():\n    return 1\n"})
    code, out = project.run()
    assert code == 0 and "0 errors, 0 warnings" in out


def test_text_report_shows_package_metrics(project):
    project.write({"a/x.py": "import b.y\n", "b/y.py": ""})
    out = project.run()[1]
    assert "Package" in out and "Instability" in out


def test_inline_ignore_suppresses_named_rule(project):
    project.write({"app.py": "import requests\nrequests.get(url)  # archcheck: ignore[network-timeout] stream\n"})
    assert project.findings() == []


def test_inline_ignore_for_other_rule_does_not_suppress(project):
    project.write({"app.py": "import requests\nrequests.get(url)  # archcheck: ignore[global-state]\n"})
    assert len(project.findings(rule="network-timeout")) == 1


def test_inline_ignore_works_on_the_first_line(project):
    project.write({"app.py": "import requests; requests.get(url)  # archcheck: ignore[network-timeout]\n"})
    assert project.findings() == []


def test_bare_inline_ignore_suppresses_everything_on_the_line(project):
    project.write({"app.py": "import requests\nrequests.get(url)  # archcheck: ignore\n"})
    assert project.findings() == []


def test_disable_in_config_turns_a_rule_off(project):
    project.write({"pyproject.toml": "[tool.archcheck]\ndisable = ['global-state']\n", "app.py": GLOBAL})
    assert project.findings() == []


def test_tests_and_virtualenvs_are_not_checked(project):
    project.write({"tests/test_app.py": NO_TIMEOUT, "test_x.py": NO_TIMEOUT, "conftest.py": NO_TIMEOUT,
                   ".venv/lib/x.py": NO_TIMEOUT, "app.py": ""})
    assert project.findings() == []


def test_exclude_globs_from_config(project):
    project.write({"pyproject.toml": "[tool.archcheck]\nexclude = ['legacy/*']\n", "legacy/old.py": NO_TIMEOUT})
    assert project.findings() == []


def test_src_layout_is_detected(project):
    project.layers("""
        [[tool.archcheck.layers]]
        name = "domain"
        modules = ["pkg.domain"]
        [[tool.archcheck.layers]]
        name = "web"
        modules = ["pkg.web"]
    """).write({"src/pkg/domain/m.py": "from pkg.web import app\n", "src/pkg/web/app.py": ""})
    [f] = project.findings(rule="dependency-rule")
    assert f["path"] == "src/pkg/domain/m.py"


def test_changed_reports_only_files_changed_in_git(project):
    project.write({"old.py": NO_TIMEOUT, "new.py": ""})
    project.commit_all()
    project.write({"new.py": NO_TIMEOUT, "added.py": NO_TIMEOUT})
    paths = sorted(f["path"] for f in project.findings("--changed"))
    assert paths == ["added.py", "new.py"]


def test_paths_limit_the_report(project):
    project.write({"a/x.py": NO_TIMEOUT, "a/z.py": NO_TIMEOUT, "b/y.py": NO_TIMEOUT})
    assert [f["path"] for f in project.findings("a")] == ["a/x.py", "a/z.py"]
    assert [f["path"] for f in project.findings("a/z.py")] == ["a/z.py"]


def test_errors_are_listed_before_warnings(project):
    project.write({"a.py": GLOBAL, "b.py": NO_TIMEOUT})
    out = project.run()[1]
    assert out.index("ERROR") < out.index("WARNING")


def test_header_names_layers_inner_to_outer(project):
    project.write({"pyproject.toml": "[[tool.archcheck.layers]]\nname = 'домен'\nmodules = ['d']\n"
                                     "[[tool.archcheck.layers]]\nname = 'web'\nmodules = ['w']\n", "d.py": ""})
    assert "layers: домен -> web (inner -> outer)" in project.run()[1]
    assert '"домен"' in project.run("--json")[1]


def test_snapshot_is_written_to_metrics(project):
    project.write({"app.py": NO_TIMEOUT})
    project.run()
    snap = json.loads((project.root / ".metrics" / "arch.json").read_text())
    assert snap["findings"][0]["rule"] == "network-timeout"


def test_no_write_skips_the_snapshot(project):
    project.write({"app.py": ""})
    project.run("--no-write")
    assert not (project.root / ".metrics").exists()


def test_syntax_error_is_reported_not_fatal(project):
    project.write({"bad.py": "def (:\n", "app.py": NO_TIMEOUT})
    found = project.findings()
    assert {f["rule"] for f in found} == {"parse-error", "network-timeout"}
    assert [f["line"] for f in found if f["rule"] == "parse-error"] == [1]


def test_broken_toml_is_a_config_error(project):
    project.write({"pyproject.toml": "[tool.archcheck\nlayers = 1\n", "app.py": ""})
    code, out = project.run()
    assert code == 2 and "pyproject.toml" in out


def test_unknown_config_key_is_a_config_error(project):
    project.write({"pyproject.toml": "[tool.archcheck]\nlayer = []\n", "app.py": ""})
    code, out = project.run()
    assert code == 2 and "layer" in out


def test_config_needs_python_311_to_be_read(project, monkeypatch):
    from archcheck import config
    monkeypatch.setattr(config, "tomllib", None)
    project.write({"pyproject.toml": "[tool.archcheck]\n", "app.py": ""})
    code, out = project.run()
    assert code == 2 and "3.11" in out


def test_changed_outside_git_is_an_error(project):
    project.write({"app.py": ""})
    code, out = project.run("--changed")
    assert code == 2 and "git" in out
