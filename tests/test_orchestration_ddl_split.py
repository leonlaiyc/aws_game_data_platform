import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "module2-experimentation-platform"
    / "orchestration"
    / "build_orchestration_tables.py"
)


def _load_builder():
    spec = importlib.util.spec_from_file_location("orchestration_table_builder", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_split_sql_ignores_semicolon_in_comment_and_string():
    builder = _load_builder()
    sql = """-- first statement; this semicolon is commentary
DROP TABLE IF EXISTS sample;
CREATE TABLE sample (value string)
LOCATION 's3://bucket/path;still-in-string/';
"""

    statements = builder.split_sql_statements(sql)

    assert len(statements) == 2
    assert statements[0] == "DROP TABLE IF EXISTS sample"
    assert "path;still-in-string" in statements[1]


def test_exposure_ddl_splits_into_drop_and_create_only():
    builder = _load_builder()
    ddl = (
        SCRIPT.parent / "ddl" / "gold_experiment_exposures.sql"
    ).read_text(encoding="utf-8")

    statements = builder.split_sql_statements(ddl)

    assert len(statements) == 2
    assert statements[0].startswith("DROP TABLE")
    assert statements[1].startswith("CREATE EXTERNAL TABLE")
