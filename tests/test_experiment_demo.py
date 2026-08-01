"""Offline checks for the deterministic Module 2 recording scenario."""

import importlib.util
import sys
from pathlib import Path


DEMO_DIR = (
    Path(__file__).resolve().parents[1]
    / "module2-experimentation-platform"
    / "demo"
)


def load_demo_module():
    sys.path.insert(0, str(DEMO_DIR))
    try:
        spec = importlib.util.spec_from_file_location(
            "module2_run_demo", DEMO_DIR / "run_demo.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(DEMO_DIR))


def test_broken_randomizer_is_repeatable_and_detectably_skewed():
    demo = load_demo_module()
    variants = [
        {"name": "control", "weight": 0.5},
        {"name": "treatment", "weight": 0.5},
    ]
    players = [f"player_{index:04d}" for index in range(300)]

    first = [
        demo.buggy_assign_variant("exp_a", 1, player, variants)
        for player in players
    ]
    second = [
        demo.buggy_assign_variant("exp_b", 999, player, variants)
        for player in players
    ]

    assert first == second
    control = first.count("control")
    treatment = first.count("treatment")
    chi2 = ((control - 150) ** 2 + (treatment - 150) ** 2) / 150
    assert demo.chi2_p_value_df1(chi2) < demo.SRM_P_VALUE_THRESHOLD
    assert demo.SRM_AS_OF_DATE == demo.AS_OF_DATE
