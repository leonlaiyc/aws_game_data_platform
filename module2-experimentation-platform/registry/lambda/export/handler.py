"""Keeps an Athena-queryable snapshot of every experiment in S3, driven by
DynamoDB Streams. One JSON file per experiment_id, overwritten on every
change - this is a "current state" export for dashboarding, not an event
log. DynamoDB Streams retains change records only temporarily, so durable
history requires a separate append-only S3 archive.
"""
import json
import os
from decimal import Decimal

import boto3
from boto3.dynamodb.types import TypeDeserializer

s3 = boto3.client("s3")
deserializer = TypeDeserializer()
BUCKET = os.environ["LAKE_BUCKET_NAME"]
EXPORT_PREFIX = "gold/experiments_export/"


def _json_default(obj):
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def handler(event, context):
    for record in event["Records"]:
        keys = record["dynamodb"]["Keys"]
        experiment_id = keys["experiment_id"]["S"]
        key = f"{EXPORT_PREFIX}{experiment_id}.json"

        if record["eventName"] == "REMOVE":
            s3.delete_object(Bucket=BUCKET, Key=key)
            continue

        new_image = record["dynamodb"].get("NewImage")
        if not new_image:
            continue
        item = {k: deserializer.deserialize(v) for k, v in new_image.items()}
        s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=json.dumps(item, default=_json_default).encode("utf-8"),
            ContentType="application/json",
        )
