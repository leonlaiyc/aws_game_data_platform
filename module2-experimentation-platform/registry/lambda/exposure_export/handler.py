"""Export immutable product exposure events to the lake for Athena joins.

DynamoDB remains the low-latency/idempotent write path. The stream export is
the analytical copy used by SRM, guardrail and final-effect queries. Files are
append-only and batched per Lambda invocation; this is intentionally simple at
side-project scale. At higher volume, Firehose buffering/compaction replaces
this small-file path.
"""
import json
import os
import uuid
from decimal import Decimal

import boto3
from boto3.dynamodb.types import TypeDeserializer

s3 = boto3.client("s3")
deserializer = TypeDeserializer()
BUCKET = os.environ["LAKE_BUCKET_NAME"]
EXPORT_PREFIX = "gold/experiment_exposures/"


def _json_default(obj):
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def handler(event, context):
    rows = []
    failed_item_ids = []
    for record in event.get("Records", []):
        try:
            new_image = record.get("dynamodb", {}).get("NewImage")
            if record.get("eventName") != "INSERT" or not new_image:
                continue
            rows.append({
                key: deserializer.deserialize(value)
                for key, value in new_image.items()
            })
        except Exception:
            failed_item_ids.append({"itemIdentifier": record["eventID"]})

    if rows:
        date_value = str(rows[0]["exposed_at"])[:10]
        request_id = getattr(context, "aws_request_id", None) or uuid.uuid4().hex
        key = f"{EXPORT_PREFIX}dt={date_value}/{request_id}.jsonl"
        body = "\n".join(
            json.dumps(row, default=_json_default, separators=(",", ":"))
            for row in rows
        )
        try:
            s3.put_object(
                Bucket=BUCKET,
                Key=key,
                Body=body.encode("utf-8"),
                ContentType="application/x-ndjson",
            )
        except Exception:
            return {
                "batchItemFailures": [
                    {"itemIdentifier": record["eventID"]}
                    for record in event.get("Records", [])
                    if record.get("eventName") == "INSERT"
                ]
            }

    return {"batchItemFailures": failed_item_ids}
