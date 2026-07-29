"""Operational alarms.

Kept in one stack rather than scattered across the stacks that own the
resources, because the question an operator asks at 3am is "is anything
broken?", not "is the analytics assistant broken?". One topic, one place to
subscribe, one place to see what is and is not watched.

Every alarm here treats missing data as NOT breaching. These are low-traffic,
schedule-driven functions - a Lambda that has not run in the last five minutes
is the normal state, not an incident, and alarming on it would train everyone
to ignore the topic.

Deliberately NOT covered, and worth naming rather than leaving as an implied
promise: no synthetic canary proving the APIs answer correctly, no alarm on
data freshness in the lake, and no anomaly-detection alarms on cost (only a
static budget threshold). Those matter for a real deployment and are the next
things to add.
"""
from aws_cdk import (
    CfnOutput,
    Duration,
    Stack,
    aws_budgets as budgets,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_iam as iam,
    aws_sns as sns,
)
from constructs import Construct

OPS_TOPIC_NAME = "aurora-games-ops-alerts"


class ObservabilityStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *,
                 lambda_function_names: dict, state_machine_arn: str,
                 dlq_names: list, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.ops_topic = sns.Topic(self, "OpsAlerts", topic_name=OPS_TOPIC_NAME,
                                    display_name="Aurora Games operational alerts")
        action = cw_actions.SnsAction(self.ops_topic)

        def alarm(construct_id: str, metric: cloudwatch.Metric, threshold: float,
                  description: str, evaluation_periods: int = 1) -> cloudwatch.Alarm:
            a = cloudwatch.Alarm(
                self, construct_id,
                metric=metric,
                threshold=threshold,
                evaluation_periods=evaluation_periods,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
                alarm_description=description,
            )
            a.add_alarm_action(action)
            return a

        # --- Lambda errors and throttles ---
        for label, function_name in lambda_function_names.items():
            dimensions = {"FunctionName": function_name}
            alarm(
                f"{label}Errors",
                cloudwatch.Metric(namespace="AWS/Lambda", metric_name="Errors",
                                   dimensions_map=dimensions, statistic="Sum",
                                   period=Duration.minutes(5)),
                threshold=0,
                description=f"{function_name} threw at least one unhandled exception in 5 minutes.",
            )
            alarm(
                f"{label}Throttles",
                cloudwatch.Metric(namespace="AWS/Lambda", metric_name="Throttles",
                                   dimensions_map=dimensions, statistic="Sum",
                                   period=Duration.minutes(5)),
                threshold=0,
                description=f"{function_name} was throttled - concurrency limit reached.",
            )

        # --- Step Functions ---
        alarm(
            "ExperimentLifecycleFailures",
            cloudwatch.Metric(namespace="AWS/States", metric_name="ExecutionsFailed",
                               dimensions_map={"StateMachineArn": state_machine_arn},
                               statistic="Sum", period=Duration.minutes(15)),
            threshold=0,
            description="An experiment lifecycle execution failed. An experiment may be stuck "
                        "mid-flight with no readout and no explicit stop.",
        )

        # --- Dead letter queues ---
        # A non-empty DLQ is the signal that something failed *and* was given
        # up on. Without this alarm the queues added for the alert path are
        # only useful to someone who already suspects a problem.
        for queue_name in dlq_names:
            alarm(
                f"Dlq{''.join(p.capitalize() for p in queue_name.split('-')[-3:])}",
                cloudwatch.Metric(namespace="AWS/SQS", metric_name="ApproximateNumberOfMessagesVisible",
                                   dimensions_map={"QueueName": queue_name},
                                   statistic="Maximum", period=Duration.minutes(5)),
                threshold=0,
                description=f"{queue_name} is non-empty: an alert was dropped after retries.",
            )

        # --- Cost ---
        # AWS Budgets rather than a CloudWatch alarm on AWS/Billing. The
        # billing namespace only publishes in us-east-1, and CDK rejects a
        # cross-region alarm outright ("Cannot create an Alarm in region
        # 'ap-northeast-1' based on metric 'EstimatedCharges' in 'us-east-1'"),
        # so a CloudWatch alarm would need its own us-east-1 stack. Budgets is
        # region-agnostic and is the purpose-built tool anyway - it forecasts
        # rather than only reacting, which for an account whose steady state is
        # under $0.10/month is the difference between noticing a stray
        # hourly-billed resource on day one versus at month end.
        budgets.CfnBudget(
            self, "MonthlyCostBudget",
            budget=budgets.CfnBudget.BudgetDataProperty(
                budget_type="COST",
                time_unit="MONTHLY",
                budget_limit=budgets.CfnBudget.SpendProperty(amount=5, unit="USD"),
                budget_name="aurora-games-monthly",
            ),
            notifications_with_subscribers=[
                budgets.CfnBudget.NotificationWithSubscribersProperty(
                    notification=budgets.CfnBudget.NotificationProperty(
                        comparison_operator="GREATER_THAN",
                        notification_type=notification_type,
                        threshold=threshold,
                        threshold_type="PERCENTAGE",
                    ),
                    subscribers=[budgets.CfnBudget.SubscriberProperty(
                        address=self.ops_topic.topic_arn, subscription_type="SNS")],
                )
                # Forecast first: at this spend level, being told at 80% of a $5
                # budget that the month is *heading* over is actionable, whereas
                # being told after the fact is archaeology.
                for notification_type, threshold in (("FORECASTED", 80), ("ACTUAL", 100))
            ],
        )
        # Budgets publishes from the AWS Budgets service principal, which needs
        # explicit permission on the topic.
        self.ops_topic.add_to_resource_policy(iam.PolicyStatement(
            actions=["SNS:Publish"],
            principals=[iam.ServicePrincipal("budgets.amazonaws.com")],
            resources=[self.ops_topic.topic_arn],
        ))

        CfnOutput(self, "OpsAlertsTopicArn", value=self.ops_topic.topic_arn)
