"""Scheduled detectors consume explicit transform publications exactly once."""
import io
import importlib.util
import json

import pytest

from conftest import REPO_ROOT, load_handler

M1 = REPO_ROOT / "module1-anomaly-detection"
COMMON_ENV = {
    "LAKE_BUCKET_NAME": "test-lake",
    "ALERTS_TOPIC_ARN": "arn:aws:sns:ap-northeast-1:123:test",
    "GLUE_DATABASE_NAME": "test",
    "ATHENA_WORKGROUP_NAME": "test",
    "AWS_DEFAULT_REGION": "ap-northeast-1",
}
anomaly = load_handler(
    "m1_anomaly_handler",
    M1 / "data_anomaly" / "lambda" / "detector",
    extra_paths=[M1 / "data_anomaly" / "lambda" / "common" / "python"],
    env=COMMON_ENV,
)
arbitrage = load_handler(
    "m1_arbitrage_handler",
    M1 / "arbitrage_detection" / "lambda" / "detector",
    extra_paths=[M1 / "arbitrage_detection" / "lambda" / "common" / "python"],
    env=COMMON_ENV,
)


class NoSuchKey(Exception):
    pass


class FakeS3:
    class exceptions:
        NoSuchKey = NoSuchKey

    def __init__(self, publication_key, table):
        self.objects = {
            publication_key: json.dumps({
                "table": table,
                "published_through": "2026-06-29",
                "published_at": "2026-07-29T00:00:00+00:00",
            }).encode(),
        }

    def get_object(self, Bucket, Key):
        try:
            body = self.objects[Key]
        except KeyError as error:
            raise NoSuchKey(Key) from error
        return {"Body": io.BytesIO(body)}

    def put_object(self, Bucket, Key, Body, **kwargs):
        self.objects[Key] = Body


@pytest.mark.parametrize("module,table", [
    (anomaly, "gold_daily_kpi"),
    (arbitrage, "gold_player_features"),
])
def test_unchanged_publication_is_not_requeried(monkeypatch, module, table):
    fake_s3 = FakeS3(module.PUBLICATION_MANIFEST_KEY, table)
    checks = []
    monkeypatch.setattr(module, "s3", fake_s3)
    monkeypatch.setattr(module, "_discover_sites", lambda: ["site_a", "site_b"])
    monkeypatch.setattr(
        module,
        "_check_site",
        lambda site, as_of_date: checks.append((site, as_of_date)) or {
            "client_site_id": site,
            "as_of_date": as_of_date,
        },
    )

    first = module.handler({"scheduled": True}, None)
    second = module.handler({"scheduled": True}, None)

    assert len(first["checked"]) == 2
    assert checks == [("site_a", "2026-06-29"), ("site_b", "2026-06-29")]
    assert second["checked"] == []
    assert second["skipped"] == "publication already processed"


def test_incomplete_publication_fails_closed(monkeypatch):
    fake_s3 = FakeS3(anomaly.PUBLICATION_MANIFEST_KEY, "gold_daily_kpi")
    fake_s3.objects[anomaly.PUBLICATION_MANIFEST_KEY] = json.dumps({
        "table": "gold_daily_kpi",
        "published_through": "2026-06-29",
    }).encode()
    monkeypatch.setattr(anomaly, "s3", fake_s3)

    with pytest.raises(ValueError, match="manifest is incomplete"):
        anomaly.handler({"scheduled": True}, None)


def test_lake_build_reapplies_governance_before_publication():
    source = (
        REPO_ROOT / "data-foundation" / "lake" / "build_lake.py"
    ).read_text(encoding="utf-8")
    main_source = source[source.index("def main():"):]

    assert (
        main_source.index("apply_client_isolation()")
        < main_source.index("publish_completion_manifest(")
    )


def test_hourly_gold_table_is_built_cleared_and_published():
    ddl = (
        REPO_ROOT
        / "data-foundation"
        / "lake"
        / "ddl"
        / "05_gold_hourly_kpi.sql"
    ).read_text(encoding="utf-8")
    builder = (
        REPO_ROOT / "data-foundation" / "lake" / "build_lake.py"
    ).read_text(encoding="utf-8")

    assert "CREATE TABLE gold_hourly_kpi" in ddl
    assert "date_trunc('hour', event_ts) AS event_hour" in ddl
    assert "partitioned_by = ARRAY['dt']" in ddl
    assert 'clear_prefix(bucket, "gold/hourly_kpi/")' in builder
    assert '"manifests/published/gold_hourly_kpi.json"' in builder


def test_hourly_monitoring_baseline_is_precomputed_and_published():
    ddl = (
        REPO_ROOT
        / "data-foundation"
        / "lake"
        / "ddl"
        / "06_gold_hourly_monitoring_features.sql"
    ).read_text(encoding="utf-8")
    hourly_ddl = (
        REPO_ROOT
        / "data-foundation"
        / "lake"
        / "ddl"
        / "05_gold_hourly_kpi.sql"
    ).read_text(encoding="utf-8")
    builder = (
        REPO_ROOT / "data-foundation" / "lake" / "build_lake.py"
    ).read_text(encoding="utf-8")

    assert "COUNT(*) AS processed_events" in hourly_ddl
    assert "CREATE TABLE gold_hourly_monitoring_features" in ddl
    assert "ROWS BETWEEN 30 PRECEDING AND 1 PRECEDING" in ddl
    assert "fact.event_hour <= cutoff.event_hour" in ddl
    assert "active_users_lower_bound" in ddl
    assert 'clear_prefix(bucket, "gold/hourly_monitoring_features/")' in builder
    assert '"manifests/published/gold_hourly_monitoring_features.json"' in builder


def test_lake_ddl_splitter_ignores_semicolons_in_comments_and_literals():
    script = REPO_ROOT / "data-foundation" / "lake" / "build_lake.py"
    spec = importlib.util.spec_from_file_location("lake_builder", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    statements = module.split_athena_statements(
        "-- prepared features; do not execute this comment\n"
        "DROP TABLE IF EXISTS sample;\n"
        "CREATE TABLE sample AS SELECT 'a;b' AS value;\n"
    )

    assert statements == [
        "DROP TABLE IF EXISTS sample",
        "CREATE TABLE sample AS SELECT 'a;b' AS value",
    ]
