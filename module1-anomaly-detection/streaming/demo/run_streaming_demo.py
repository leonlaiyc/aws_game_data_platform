"""Demo for the real-time streaming path: pushes a small "normal" burst of
bet events into Kinesis, then a large burst with an anomalous RTP (return
to player) - simulating a payout bug or exploit - which should trip both
the RTP threshold and the volume threshold within the same processing
window, firing exactly one SNS alert (not one per Kinesis batch).

Requires: infra/ deploy of AuroraGamesStreamingStack (see
module1-anomaly-detection/streaming/README.md for the full run -> verify
-> teardown sequence - this stack should not be left running).
"""
import json
import time
import uuid

import boto3

STACK_NAME = "AuroraGamesStreamingStack"
CLIENT_SITE_ID = "site_a"
GAME_ID = "game_01"

NORMAL_EVENTS = 20
NORMAL_BET, NORMAL_WIN = 10.0, 6.0     # RTP 0.60 - ordinary house edge

ANOMALOUS_EVENTS = 250
ANOMALOUS_BET, ANOMALOUS_WIN = 10.0, 9.9  # RTP 0.99 - simulates a payout exploit/bug

session = boto3.Session()
cfn = session.client("cloudformation")
kinesis = session.client("kinesis")
dynamodb = session.resource("dynamodb")


def stack_outputs(stack_name: str) -> dict:
    resp = cfn.describe_stacks(StackName=stack_name)
    return {o["OutputKey"]: o["OutputValue"] for o in resp["Stacks"][0]["Outputs"]}


def make_event(bet: float, win: float) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "event_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "client_site_id": CLIENT_SITE_ID,
        "game_id": GAME_ID,
        "bet_amount": bet,
        "win_amount": win,
    }


def put_burst(stream_name: str, count: int, bet: float, win: float, label: str):
    print(f"Sending {count} {label} events (bet={bet}, win={win}, RTP={win / bet:.2f}) ...")
    events = [make_event(bet, win) for _ in range(count)]
    for i in range(0, len(events), 100):
        chunk = events[i:i + 100]
        records = [
            {"Data": json.dumps(e).encode("utf-8"), "PartitionKey": e["client_site_id"]}
            for e in chunk
        ]
        resp = kinesis.put_records(StreamName=stream_name, Records=records)
        if resp["FailedRecordCount"]:
            raise RuntimeError(f"{resp['FailedRecordCount']} records failed to put")


def main():
    outputs = stack_outputs(STACK_NAME)
    stream_name = outputs["StreamName"]

    put_burst(stream_name, NORMAL_EVENTS, NORMAL_BET, NORMAL_WIN, "normal")
    put_burst(stream_name, ANOMALOUS_EVENTS, ANOMALOUS_BET, ANOMALOUS_WIN, "anomalous")

    print("\nWaiting for the Lambda consumer to process the batches ...")
    time.sleep(15)

    window_minute = time.strftime("%Y-%m-%dT%H:%M", time.gmtime())
    window_id = f"{CLIENT_SITE_ID}#{window_minute}"
    table = dynamodb.Table("aurora-games-streaming-windows")
    item = table.get_item(Key={"window_id": window_id}).get("Item")

    print(f"\n=== Window state: {window_id} ===")
    if item:
        bet_total, win_total, event_count = float(item["bet_total"]), float(item["win_total"]), int(item["event_count"])
        print(f"bet_total={bet_total:.2f} win_total={win_total:.2f} event_count={event_count} "
              f"rtp={win_total / bet_total:.4f}")
        print(f"alerted={item.get('alerted', False)}")
    else:
        print("No window item found yet - the events may have landed in the next minute's window; "
              "check aurora-games-streaming-windows directly for nearby window_ids.")


if __name__ == "__main__":
    main()
