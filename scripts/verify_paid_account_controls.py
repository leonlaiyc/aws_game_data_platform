"""Read-only pre-deployment checks for this project's paid AWS account."""
import sys

import boto3
from botocore.exceptions import ClientError

BUDGET_NAME = "aurora-games-monthly"
OBSERVABILITY_STACK = "AuroraGamesObservabilityStack"
EXPECTED_NOTIFICATIONS = {("FORECASTED", 80.0), ("ACTUAL", 100.0)}


def main() -> int:
    failures = []
    account_id = boto3.client("sts").get_caller_identity()["Account"]
    budgets = boto3.client("budgets", region_name="us-east-1")

    budget = budgets.describe_budget(
        AccountId=account_id, BudgetName=BUDGET_NAME
    )["Budget"]
    limit = budget["BudgetLimit"]
    if float(limit["Amount"]) != 5.0 or limit["Unit"] != "USD":
        failures.append(f"budget limit is {limit}, expected USD 5")

    notifications = budgets.describe_notifications_for_budget(
        AccountId=account_id, BudgetName=BUDGET_NAME
    ).get("Notifications", [])
    configured = {
        (notification["NotificationType"], float(notification["Threshold"]))
        for notification in notifications
    }
    missing = EXPECTED_NOTIFICATIONS - configured
    if missing:
        failures.append(f"missing budget notifications: {sorted(missing)}")

    outputs = boto3.client("cloudformation").describe_stacks(
        StackName=OBSERVABILITY_STACK
    )["Stacks"][0]["Outputs"]
    topic_arn = next(
        output["OutputValue"]
        for output in outputs
        if output["OutputKey"] == "OpsAlertsTopicArn"
    )
    subscriptions = boto3.client("sns").list_subscriptions_by_topic(
        TopicArn=topic_arn
    ).get("Subscriptions", [])
    confirmed = [
        subscription
        for subscription in subscriptions
        if subscription.get("SubscriptionArn") != "PendingConfirmation"
    ]
    if not confirmed:
        failures.append(
            "USD 5 budget topic has no confirmed subscriber; alerts have no "
            "actionable destination"
        )

    streams = boto3.client("kinesis").list_streams().get("StreamNames", [])
    project_streams = [
        stream for stream in streams if stream.startswith("aurora-games")
    ]
    if project_streams:
        failures.append(
            f"ephemeral Kinesis stream still exists: {project_streams}"
        )

    print(
        f"Budget: {limit['Amount']} {limit['Unit']} | "
        f"notifications={sorted(configured)} | "
        f"confirmed_destinations={len(confirmed)}"
    )
    print(f"Project Kinesis streams: {project_streams or 'none'}")
    if failures:
        print("RESULT: BLOCKED")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ClientError as error:
        print(
            "RESULT: BLOCKED — AWS readiness check failed: "
            f"{error.response.get('Error', {}).get('Code', type(error).__name__)}"
        )
        raise SystemExit(1)
