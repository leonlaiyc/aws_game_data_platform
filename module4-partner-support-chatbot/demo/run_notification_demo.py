"""Publish one maintenance notice and verify account-local SNS delivery."""
import json
import sys
import time
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "demo_lib"))
from signed_request import assume, signed_post  # noqa: E402

STACK_NAME = "AuroraGamesSupportChatbotStack"


def main() -> int:
    cfn = boto3.client("cloudformation")
    outputs = {
        output["OutputKey"]: output["OutputValue"]
        for output in cfn.describe_stacks(StackName=STACK_NAME)["Stacks"][0][
            "Outputs"
        ]
    }
    api_url = outputs["ChatApiUrl"]
    queue_url = outputs["PartnerNotificationAuditQueueUrl"]
    operator = assume("aurora-games-operator", "m4-notification-demo")
    sqs = boto3.client("sqs")

    print("PRECHECK: PASS — stack outputs and operator role resolved")
    payload = {
        "notification_type": "MAINTENANCE",
        "title": "Demo: settlement API maintenance",
        "message": (
            "Settlement callbacks may be delayed during the maintenance "
            "window. Existing game sessions are unaffected."
        ),
        "effective_at": "2026-08-01T02:00:00+08:00",
        "client_site_ids": ["site_a", "site_c"],
        "affected_games": [],
    }
    status, result = signed_post(
        operator, f"{api_url}notifications", payload
    )
    if status != 202 or result.get("status") != "PUBLISHED":
        print(f"RESULT: FAIL — publisher returned {status}: {result}")
        return 1

    notification_id = result["notification_id"]
    print(f"PUBLISHED: {notification_id}")
    print(f"SNS message: {result['sns_message_id']}")
    print("Waiting for the account-local audit subscriber...")
    deadline = time.time() + 30
    delivered = None
    receipt_handle = None
    while time.time() < deadline and not delivered:
        response = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=5,
            VisibilityTimeout=5,
        )
        for message in response.get("Messages", []):
            try:
                candidate = json.loads(message["Body"])
            except json.JSONDecodeError:
                continue
            if candidate.get("notification_id") == notification_id:
                delivered = candidate
                receipt_handle = message["ReceiptHandle"]
                break

    expected = {
        "notification_type": "MAINTENANCE",
        "client_site_ids": ["site_a", "site_c"],
        "title": payload["title"],
    }
    if not delivered or any(
        delivered.get(key) != value for key, value in expected.items()
    ):
        print(f"RESULT: FAIL — matching delivery not found: {delivered}")
        return 1

    sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)
    print("DELIVERED: PASS")
    print(
        f"  type={delivered['notification_type']} "
        f"sites={delivered['client_site_ids']} "
        f"effective_at={delivered['effective_at']}"
    )
    print("CLEANUP: PASS — matching audit message deleted")
    print("GROSS COST: below $0.01 for this SNS/SQS/API/Lambda demo")
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
