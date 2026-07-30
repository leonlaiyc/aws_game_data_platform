from pathlib import Path

from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
    CfnOutput,
    aws_dynamodb as dynamodb,
    aws_kinesis as kinesis,
    aws_lambda as _lambda,
    aws_lambda_event_sources as lambda_event_sources,
    aws_sns as sns,
)
from constructs import Construct

REPO_ROOT = Path(__file__).resolve().parents[2]
LAMBDA_DIR = REPO_ROOT / "module1-anomaly-detection" / "streaming" / "lambda"

RTP_ALERT_THRESHOLD = 0.95       # normal simulated RTP is ~50-70%; this signals a payout/exploit issue
VOLUME_ALERT_THRESHOLD = 200     # bet events in a 1-minute processing-time window


class StreamingStack(Stack):
    """Short-lived, cost-controlled real-time path, separate from every
    always-on stack in this project: Kinesis (1 provisioned shard) ->
    Lambda -> a DynamoDB-backed tumbling window -> SNS, demonstrating
    real-time RTP/volume threshold alerting alongside AnomalyStack's
    steady-state batch detection.

    Kinesis Data Streams has no "pay only when used" mode - verified
    pricing (2026-07-28): Provisioned bills $0.015/shard-hour continuously
    regardless of traffic; On-Demand Standard bills a separate fixed
    $0.040/stream-hour PLUS per-GB data-in, actually pricier at idle. No
    free tier at all. That's why this is its own stack: deploy it,
    run the demo, then `cdk destroy AuroraGamesStreamingStack` - see
    module1-anomaly-detection/streaming/README.md.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.stream = kinesis.Stream(
            self,
            "RealtimeEvents",
            stream_name="aurora-games-realtime-events",
            shard_count=1,
            stream_mode=kinesis.StreamMode.PROVISIONED,
            retention_period=Duration.hours(24),  # minimum retention
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.window_table = dynamodb.Table(
            self,
            "StreamingWindows",
            table_name="aurora-games-streaming-windows",
            partition_key=dynamodb.Attribute(name="window_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            time_to_live_attribute="expires_at",  # old windows self-clean, no manual sweep needed
        )

        self.alerts_topic = sns.Topic(self, "AlertsTopic", topic_name="aurora-games-streaming-alerts")

        self.aggregator_fn = _lambda.Function(
            self,
            "RealtimeAggregator",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=_lambda.Code.from_asset(str(LAMBDA_DIR / "aggregator")),
            environment={
                "WINDOW_TABLE_NAME": self.window_table.table_name,
                "ALERTS_TOPIC_ARN": self.alerts_topic.topic_arn,
                "RTP_ALERT_THRESHOLD": str(RTP_ALERT_THRESHOLD),
                "VOLUME_ALERT_THRESHOLD": str(VOLUME_ALERT_THRESHOLD),
            },
            timeout=Duration.seconds(30),
        )
        self.window_table.grant_read_write_data(self.aggregator_fn)
        self.alerts_topic.grant_publish(self.aggregator_fn)
        self.aggregator_fn.add_event_source(
            lambda_event_sources.KinesisEventSource(
                self.stream,
                starting_position=_lambda.StartingPosition.LATEST,
                batch_size=100,
                max_batching_window=Duration.seconds(5),
                retry_attempts=1,
            )
        )

        CfnOutput(self, "StreamName", value=self.stream.stream_name)
        CfnOutput(self, "AlertsTopicArn", value=self.alerts_topic.topic_arn)
