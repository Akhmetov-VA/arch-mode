"""Dependency Rule and pure layers (Clean Architecture)."""
from conftest import LAYERED


def shop(project, domain="", app="", adapters=""):
    return project.layers(LAYERED).write({
        "shop/__init__.py": "",
        "shop/domain/__init__.py": "",
        "shop/domain/order.py": domain or "class Order: ...\n",
        "shop/app/__init__.py": "",
        "shop/app/place.py": app or "from shop.domain.order import Order\n",
        "shop/adapters/__init__.py": "",
        "shop/adapters/db.py": adapters or "from shop.app.place import *\n",
    })


def test_inner_layer_importing_outer_layer_is_an_error(project):
    shop(project, domain="from shop.adapters.db import save\n")
    [f] = project.findings(rule="dependency-rule")
    assert f["severity"] == "error"
    assert f["path"] == "shop/domain/order.py" and f["line"] == 1
    assert "domain" in f["message"] and "adapters" in f["message"]


def test_outer_layers_may_import_inner_layers(project):
    shop(project)
    assert project.findings(rule="dependency-rule") == []


def test_relative_import_is_resolved(project):
    shop(project, app="from ..adapters import db\n")
    [f] = project.findings(rule="dependency-rule")
    assert f["path"] == "shop/app/place.py"


def test_plain_import_of_outer_module_is_an_error(project):
    shop(project, domain="import shop.app.place\n")
    assert len(project.findings(rule="dependency-rule")) == 1


def test_script_style_sibling_import_is_resolved(project):
    project.layers("""
        [[tool.archcheck.layers]]
        name = "domain"
        modules = ["bot.devices"]
        [[tool.archcheck.layers]]
        name = "telegram"
        modules = ["bot.vpnbot"]
    """).write({"bot/devices.py": "import vpnbot\n", "bot/vpnbot.py": "import devices as D\n"})
    [f] = project.findings(rule="dependency-rule")
    assert f["path"] == "bot/devices.py"


def test_pure_layer_cannot_import_io_or_frameworks(project):
    shop(project, domain="import requests\nfrom os import path\nimport json\n")
    found = project.findings(rule="pure-layer")
    assert [f["line"] for f in found] == [1, 2]
    assert all(f["severity"] == "error" for f in found)


def test_pure_layer_cannot_open_files(project):
    shop(project, domain="def load(p):\n    return open(p).read()\n")
    [f] = project.findings(rule="pure-layer")
    assert f["line"] == 2


def test_layer_that_is_not_pure_may_do_io(project):
    shop(project, adapters="import sqlite3\nopen('x')\n")
    assert project.findings(rule="pure-layer") == []


def test_layer_forbid_list_adds_names(project):
    shop(project, app="import numpy as np\n")
    project.layers(LAYERED.replace('modules = ["shop.app"]', 'modules = ["shop.app"]\nforbid = ["numpy"]'))
    [f] = project.findings(rule="pure-layer")
    assert f["path"] == "shop/app/place.py" and "numpy" in f["message"]


def test_without_layers_there_is_no_dependency_rule(project):
    project.write({"a/x.py": "import b.y\n", "b/y.py": ""})
    report = project.report()
    assert report["layers"] == []
    assert [f for f in report["findings"] if f["rule"] == "dependency-rule"] == []


def test_archcheck_toml_is_read_when_there_is_no_pyproject_section(project):
    project.write({".archcheck.toml": LAYERED.replace("tool.archcheck.", "")})
    shop(project, domain="from shop.adapters.db import save\n")
    (project.root / "pyproject.toml").write_text("[project]\nname='x'\n")
    assert len(project.findings(rule="dependency-rule")) == 1


def test_layer_without_modules_is_a_config_error(project):
    project.layers('[[tool.archcheck.layers]]\nname = "domain"\n').write({"a.py": ""})
    code, out = project.run()
    assert code == 2 and "domain" in out
