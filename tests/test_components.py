"""Component principles: ADP (no cycles), SDP (depend toward stability), metrics I, A, D."""


def metrics(project):
    return {m["package"]: m for m in project.report()["packages"]}


def test_cycle_between_packages_is_an_error(project):
    project.write({"a/__init__.py": "", "a/x.py": "from b.y import f\n",
                   "b/__init__.py": "", "b/y.py": "import a.x\n"})
    [f] = project.findings(rule="component-cycle")
    assert f["severity"] == "error"
    assert "a" in f["message"] and "b" in f["message"]
    assert sorted([f["path"], *f["related"]]) == ["a/x.py", "b/y.py"]


def test_one_way_dependency_is_not_a_cycle(project):
    project.write({"a/x.py": "from b.y import f\n", "b/y.py": "def f(): ...\n"})
    assert project.findings(rule="component-cycle") == []


def test_imports_inside_one_package_are_not_a_cycle(project):
    project.write({"a/x.py": "from a import y\n", "a/y.py": "from a import x\n"})
    assert project.findings(rule="component-cycle") == []


def test_instability_counts_package_edges(project):
    project.write({"a/x.py": "import b.y\nimport c.z\n", "b/y.py": "import c.z\n", "c/z.py": ""})
    m = metrics(project)
    assert (m["a"]["ca"], m["a"]["ce"], m["a"]["instability"]) == (0, 2, 1.0)
    assert (m["b"]["ca"], m["b"]["ce"], m["b"]["instability"]) == (1, 1, 0.5)
    assert (m["c"]["ca"], m["c"]["ce"], m["c"]["instability"]) == (2, 0, 0.0)


def test_abstractness_counts_abstract_classes_and_protocols(project):
    project.write({"p/ports.py": """
        from abc import ABC, abstractmethod
        from typing import Protocol
        class Repo(ABC): ...
        class Clock(Protocol):
            def now(self): ...
        class Mailer:
            @abstractmethod
            def send(self): ...
        class Plain: ...
    """})
    assert metrics(project)["p"]["abstractness"] == 0.75


def test_distance_from_main_sequence(project):
    project.write({"a/x.py": "import b.y\n", "b/y.py": "class Concrete: ...\n"})
    assert metrics(project)["b"]["distance"] == 1.0   # stable and concrete: zone of pain


def test_stable_package_depending_on_unstable_one_is_a_warning(project):
    project.write({
        "a/m.py": "import core.m\n", "b/m.py": "import core.m\n",
        "core/m.py": "import plugins.m\n",
        "plugins/m.py": "import p1.m\nimport p2.m\n", "p1/m.py": "", "p2/m.py": "",
    })
    [f] = project.findings(rule="unstable-dependency")
    assert f["severity"] == "warning" and f["path"] == "core/m.py"
    assert "plugins" in f["message"]


def test_files_at_the_root_form_one_package(project):
    project.write({"main.py": "import lib.x\n", "lib/x.py": ""})
    assert "." in metrics(project)
