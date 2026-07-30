"""The player-risk decision must be reconstructable from persisted evidence."""
from conftest import REPO_ROOT, load_handler

M1 = REPO_ROOT / "module1-anomaly-detection"
handler = load_handler(
    "m1_arbitrage_explainability_handler",
    M1 / "arbitrage_detection" / "lambda" / "detector",
    extra_paths=[M1 / "arbitrage_detection" / "lambda" / "common" / "python"],
    env={
        "LAKE_BUCKET_NAME": "test-lake",
        "ALERTS_TOPIC_ARN": "arn:aws:sns:ap-northeast-1:123:test",
        "GLUE_DATABASE_NAME": "test",
        "ATHENA_WORKGROUP_NAME": "test",
        "AWS_DEFAULT_REGION": "ap-northeast-1",
    },
)


def device_evidence():
    return [{
        "device_id": "device_shared",
        "linked_player_count": 6,
        "linked_player_ids": [f"p_ring_{i:02d}" for i in range(6)],
    }]


def feature_row(**overrides):
    row = {
        "withdrawal_to_deposit_ratio_7d": "1.31",
        "bonus_claims_30d": "8",
        "wd_ratio_median": "0.24",
        "wd_ratio_p99": "0.77",
        "bonus_claims_median": "1",
        "bonus_claims_p99": "4",
    }
    row.update(overrides)
    return row


def test_finding_contains_structured_reconstructable_evidence():
    finding = handler._build_explainable_finding(
        "site_a", "2026-06-05", "p_ring_00", device_evidence(), feature_row(),
    )

    assert finding["status"] == "REVIEW_REQUIRED"
    assert finding["detector_id"] == "multi_account_arbitrage_review"
    assert finding["detector_version"] == "rules-v2-explainable"
    assert finding["evidence_window"] == {
        "start": "2026-05-07",
        "end": "2026-06-05",
    }
    assert finding["decision_note"].startswith("This is a review-priority signal")

    reasons = {reason["code"]: reason for reason in finding["reason_codes"]}
    assert set(reasons) == {
        "SHARED_DEVICE_FANOUT",
        "CASHOUT_RATIO_HIGH",
        "BONUS_CLAIM_BURST",
    }
    assert reasons["SHARED_DEVICE_FANOUT"]["actual"] == 6
    assert reasons["SHARED_DEVICE_FANOUT"]["threshold"] == 3
    assert reasons["CASHOUT_RATIO_HIGH"]["actual"] == 1.31
    assert reasons["CASHOUT_RATIO_HIGH"]["threshold"] == 0.8
    assert reasons["CASHOUT_RATIO_HIGH"]["peer_p99"] == 0.77
    assert reasons["BONUS_CLAIM_BURST"]["peer_median"] == 1.0

    assert finding["linked_player_ids"] == [
        "p_ring_01", "p_ring_02", "p_ring_03", "p_ring_04", "p_ring_05",
    ]
    assert finding["shared_device_ids"] == ["device_shared"]
    assert finding["review_score"] == round(
        sum(reason["contribution"] for reason in finding["reason_codes"]), 4,
    )
    assert "not a probability" in finding["score_interpretation"]


def test_device_fanout_alone_does_not_accuse_a_player():
    finding = handler._build_explainable_finding(
        "site_a",
        "2026-06-05",
        "ordinary_household_player",
        device_evidence(),
        feature_row(
            withdrawal_to_deposit_ratio_7d="0.20",
            bonus_claims_30d="2",
        ),
    )
    assert finding is None


def test_abnormal_behaviour_without_entity_linkage_does_not_flag():
    finding = handler._build_explainable_finding(
        "site_a", "2026-06-05", "lucky_winner", [], feature_row(),
    )
    assert finding is None


def test_each_human_explanation_is_code_rendered_from_structured_values():
    finding = handler._build_explainable_finding(
        "site_a", "2026-06-05", "p_ring_00", device_evidence(), feature_row(),
    )
    explanations = "\n".join(finding["reasons"])
    assert "6 accounts" in explanations
    assert "1.31" in explanations
    assert "8 bonuses" in explanations
    assert len(finding["reasons"]) == len(finding["reason_codes"])
