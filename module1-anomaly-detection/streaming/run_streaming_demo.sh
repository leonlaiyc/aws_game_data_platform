#!/usr/bin/env bash
# Deploy -> demo -> destroy -> VERIFY, as one command.
#
# Kinesis Data Streams bills per shard-hour with no free tier, so the risk with
# this stack is not that teardown fails loudly - it is that it fails quietly and
# nobody looks again. This script therefore ends by listing streams directly and
# exiting non-zero if one survives, rather than trusting `cdk destroy`'s exit
# code. A destroy that reports success while a resource lingers is exactly the
# case that costs money for weeks.
#
# The stack is excluded from the default CDK app (see infra/app.py), so it
# cannot be created by a plain `cdk deploy --all`.
set -uo pipefail

STACK=AuroraGamesStreamingStack
STREAM_NAME=aurora-games-live-events
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

cd "$REPO_ROOT/infra" || exit 1

echo "==> Deploying $STACK (billable from this moment)"
cdk deploy "$STACK" -c enable_streaming=true --require-approval never || {
    echo "Deploy failed - attempting teardown anyway so nothing is left running."
}

echo
echo "==> Waiting for the Kinesis event source mapping to start polling"
# The consumer starts at LATEST, which does not replay. Producing immediately
# after deploy races the poller's startup and the burst is simply missed.
sleep 45

echo
echo "==> Running the demo"
cd "$REPO_ROOT" || exit 1
python module1-anomaly-detection/streaming/demo/run_streaming_demo.py
DEMO_STATUS=$?

echo
echo "==> Destroying $STACK"
cd "$REPO_ROOT/infra" || exit 1
cdk destroy "$STACK" -c enable_streaming=true --force

echo
echo "==> Verifying teardown by listing live resources (not trusting the exit code)"
REMAINING=$(aws kinesis list-streams --query "StreamNames[?contains(@, 'aurora-games')]" --output text)
if [ -n "$REMAINING" ]; then
    echo "!! STREAM STILL EXISTS: $REMAINING"
    echo "!! Still billing at ~\$0.0195/shard-hour in ap-northeast-1. Delete it now."
    exit 1
fi

STACK_STATE=$(aws cloudformation describe-stacks --stack-name "$STACK" \
    --query "Stacks[0].StackStatus" --output text 2>/dev/null)
if [ -n "$STACK_STATE" ] && [ "$STACK_STATE" != "DELETE_COMPLETE" ]; then
    echo "!! Stack still present in state $STACK_STATE - investigate before walking away."
    exit 1
fi

echo "Verified: no aurora-games Kinesis streams remain, stack is gone."
exit $DEMO_STATUS
