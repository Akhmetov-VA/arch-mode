"""Design heuristics (Design Patterns): type switches, deep inheritance, hidden global state."""


SHAPES = "class Circle: ...\nclass Square: ...\nclass Triangle: ...\n"


def test_type_switch_on_project_classes_is_a_warning(project):
    project.write({"kinds.py": SHAPES, "shapes.py": """
        def area(s):
            if isinstance(s, Circle):
                return 3.14 * s.r ** 2
            elif isinstance(s, Square):
                return s.a ** 2
            elif isinstance(s, Triangle):
                return s.b * s.h / 2
    """})
    [f] = project.findings(rule="type-switch")
    assert f["severity"] == "warning" and f["line"] == 1 and "area" in f["message"]


def test_type_switch_on_library_types_is_fine(project):
    project.write({"conv.py": """
        import ast
        def lit(v):
            if isinstance(v, bool):
                return "b"
            if isinstance(v, (int, float)):
                return "n"
            if isinstance(v, str):
                return "s"
        def visit(node):
            if isinstance(node, ast.Name):
                return 1
            elif isinstance(node, ast.Call):
                return 2
            elif isinstance(node, ast.Attribute):
                return 3
    """})
    assert project.findings(rule="type-switch") == []


def test_two_type_checks_are_fine(project):
    project.write({"kinds.py": SHAPES, "shapes.py": """
        def area(s):
            if isinstance(s, Circle):
                return 1
            if isinstance(s, Square):
                return 2
    """})
    assert project.findings(rule="type-switch") == []


def test_type_checks_on_different_values_are_fine(project):
    project.write({"shapes.py": """
        def f(a, b, c):
            if isinstance(a, int) and isinstance(b, int) and isinstance(c, int):
                return a + b + c
    """})
    assert project.findings(rule="type-switch") == []


def test_three_levels_of_project_inheritance_is_a_warning(project):
    project.write({"base.py": "class A: ...\n", "kids.py": """
        from base import A
        class B(A): ...
        class C(B): ...
        class D(C): ...
    """})
    [f] = project.findings(rule="deep-inheritance")
    assert f["path"] == "kids.py" and f["line"] == 4
    assert "class D inherits through 3 project classes (D -> C -> B -> A)" in f["message"]


def test_inheriting_from_library_classes_does_not_count(project):
    project.write({"m.py": "class A(Exception): ...\nclass B(A): ...\nclass C(B): ...\n"})
    assert project.findings(rule="deep-inheritance") == []


def test_global_statement_is_a_warning(project):
    project.write({"cache.py": "_cache = {}\ndef reset():\n    global _cache\n    _cache = {}\n"})
    [f] = project.findings(rule="global-state")
    assert f["line"] == 3 and "_cache" in f["message"]


def test_type_checks_in_nested_function_belong_to_it(project):
    project.write({"kinds.py": "class A: ...\nclass B: ...\nclass C: ...\n", "m.py": """
        def outer(s):
            if isinstance(s, A):
                return 1
            def inner(t):
                if isinstance(s, B) or isinstance(s, C):
                    return 2
            return inner
    """})
    assert project.findings(rule="type-switch") == []
