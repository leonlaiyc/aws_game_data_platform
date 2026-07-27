"""Shared DynamoDB helpers, packaged as a Lambda Layer alongside athena_utils.

DynamoDB's boto3 Table resource requires Decimal for numbers (rejects
native float/int-from-json-float), and Step Functions/JSON output rejects
Decimal in return - clean_decimals/to_decimal convert between the two
directions consistently across every Lambda in this module.
"""
import time
from decimal import Decimal


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def clean_decimals(obj):
    """DynamoDB item -> JSON-safe (for returning from a Lambda into Step Functions)."""
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    if isinstance(obj, list):
        return [clean_decimals(v) for v in obj]
    if isinstance(obj, dict):
        return {k: clean_decimals(v) for k, v in obj.items()}
    return obj


def to_decimal(obj):
    """JSON/float data -> DynamoDB-safe (for writing back with put_item/update_item)."""
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, list):
        return [to_decimal(v) for v in obj]
    if isinstance(obj, dict):
        return {k: to_decimal(v) for k, v in obj.items()}
    return obj
