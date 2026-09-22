def test_import_app() -> None:
    from washy_washy.main import app

    assert app is not None


def test_import_core_does_not_import_washy_washy() -> None:
    """core must remain independent of the washy_washy service package."""
    import ast
    from pathlib import Path

    core_src = Path(__file__).resolve().parents[1] / "src" / "core"
    for py_file in core_src.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module] if node.module else []
            else:
                continue
            for name in names:
                assert not (name or "").startswith("washy_washy"), (
                    f"{py_file} imports washy_washy, violating the core -> washy_washy "
                    "dependency direction"
                )
