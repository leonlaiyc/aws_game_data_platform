"""Step 2: automated Sample Ratio Mismatch check. Pure computation, no AWS
calls - a chi-square goodness-of-fit test between observed and expected
(by variant weight) assignment counts.

Only supports 2-variant experiments: for df=1, the chi-square distribution
is exactly the square of a standard normal, so its survival function (the
p-value) has a closed form via erfc - no incomplete gamma function needed.
A k-variant generalization would need the regularized incomplete gamma
function for the chi-square CDF instead.
"""
import math

# Stricter than the conventional 0.05: SRM checks run on every experiment,
# and a false-positive here kills a real experiment, so we want few of them.
SRM_P_VALUE_THRESHOLD = 0.01


def _chi2_p_value_df1(chi2: float) -> float:
    return math.erfc(math.sqrt(chi2 / 2))


def handler(event, context):
    variants = event["assignment"]["experiment"]["variants"]
    variant_counts = event["assignment"]["variant_counts"]
    total = event["assignment"]["total_assigned"]

    if len(variants) != 2:
        raise ValueError("SRM check currently only supports 2-variant experiments")
    if total == 0:
        return {"passed": False, "chi2": None, "p_value": None, "threshold": SRM_P_VALUE_THRESHOLD,
                "error": "no players were assigned - audience query returned zero eligible players"}

    chi2 = 0.0
    for v in variants:
        observed = variant_counts.get(v["name"], 0)
        expected = total * float(v["weight"])
        if expected > 0:
            chi2 += (observed - expected) ** 2 / expected

    p_value = _chi2_p_value_df1(chi2)
    passed = p_value >= SRM_P_VALUE_THRESHOLD

    return {
        "passed": passed,
        "chi2": round(chi2, 4),
        "p_value": round(p_value, 6),
        "threshold": SRM_P_VALUE_THRESHOLD,
    }
