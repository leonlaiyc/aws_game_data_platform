"""Local recording console backed by the deployed AWS demo stacks.

The browser only talks to localhost. This process invokes Lambda or makes
SigV4-signed API requests, so temporary AWS credentials never reach the page.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import threading
import time
import uuid
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, urlparse

import boto3
from botocore.exceptions import ClientError


REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "demo_lib"))
sys.path.insert(0, str(REPO_ROOT / "module2-experimentation-platform" / "demo"))
sys.path.insert(0, str(REPO_ROOT / "module2-experimentation-platform" / "dashboard"))

from signed_request import assume, signed_post, signed_request  # noqa: E402
import demo_lib as experiment_lib  # noqa: E402
from view_model import build_view_model  # noqa: E402


REGION = boto3.Session().region_name or "ap-northeast-1"
ANOMALY_STACK = "AuroraGamesAnomalyStack"
ASSISTANT_STACK = "AuroraGamesAnalyticsAssistantStack"
FOUNDATION_STACK = "AuroraGamesFoundationStack"
REGISTRY_STACK = "AuroraGamesRegistryStack"
SUPPORT_STACK = "AuroraGamesSupportChatbotStack"
REPORT_KEY = "gold/first_look_reports/site_b_2026-06-10.json"

cfn = boto3.client("cloudformation")
lambda_client = boto3.client("lambda")
s3 = boto3.client("s3")
_outputs: dict[str, dict] = {}
_roles: dict[str, boto3.Session] = {}


def stack_outputs(stack_name: str) -> dict:
    if stack_name not in _outputs:
        response = cfn.describe_stacks(StackName=stack_name)
        _outputs[stack_name] = {
            output["OutputKey"]: output["OutputValue"]
            for output in response["Stacks"][0]["Outputs"]
        }
    return _outputs[stack_name]


def role_session(role_name: str) -> boto3.Session:
    if role_name not in _roles:
        _roles[role_name] = assume(role_name, "operation-video")
    return _roles[role_name]


def invoke(function_name: str, payload: dict) -> dict:
    response = lambda_client.invoke(
        FunctionName=function_name,
        Payload=json.dumps(payload).encode("utf-8"),
    )
    body = json.loads(response["Payload"].read())
    if response.get("FunctionError"):
        raise RuntimeError(f"{function_name} failed: {body}")
    return body


def evidence_metadata(bucket: str, key: str) -> dict:
    head = s3.head_object(Bucket=bucket, Key=key)
    return {
        "bucket": bucket,
        "key": key,
        "last_modified": head["LastModified"].astimezone(timezone.utc).isoformat(),
        "etag": head["ETag"].strip('"'),
    }


def run_anomaly_scan() -> dict:
    outputs = stack_outputs(ANOMALY_STACK)
    started = time.perf_counter()
    result = invoke(
        outputs["AnomalyDetectorFunctionName"],
        {"client_site_id": "site_b", "as_of_date": "2026-06-10"},
    )
    result["request"] = {
        "service": "AWS Lambda + Athena",
        "region": REGION,
        "duration_ms": round((time.perf_counter() - started) * 1000),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    result["evidence"] = {
        "key": "gold/anomaly_alerts/site_b_2026-06-10.json",
        "notification": "Amazon SNS anomaly-alerts",
    }
    return result


def incidents_snapshot() -> tuple[int, dict]:
    outputs = stack_outputs(ANOMALY_STACK)
    return signed_request(
        role_session("aurora-games-operator"),
        "GET",
        f"{outputs['IncidentApiUrl']}incidents",
    )


def update_incident_status(incident_id: str, status: str) -> tuple[int, dict]:
    outputs = stack_outputs(ANOMALY_STACK)
    encoded_id = quote(incident_id, safe="")
    return signed_post(
        role_session("aurora-games-operator"),
        f"{outputs['IncidentApiUrl']}incidents/{encoded_id}/status",
        {"status": status},
    )


def latest_first_look() -> dict:
    bucket = stack_outputs(FOUNDATION_STACK)["LakeBucketName"]
    raw = s3.get_object(Bucket=bucket, Key=REPORT_KEY)["Body"].read()
    report = json.loads(raw)
    report["evidence"] = evidence_metadata(bucket, REPORT_KEY)
    report["request"] = {
        "service": "Amazon S3 first-look output",
        "region": REGION,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    return report


def analytics_ask(question: str) -> tuple[int, dict]:
    outputs = stack_outputs(ASSISTANT_STACK)
    started = time.perf_counter()
    status, result = signed_post(
        role_session("aurora-games-operator"),
        f"{outputs['AskApiUrl']}ask",
        {"question": question},
        timeout=60,
    )
    result["request"] = {
        "service": "IAM + API Gateway + governed analytics",
        "identity": "all-authorised-sites",
        "region": REGION,
        "duration_ms": round((time.perf_counter() - started) * 1000),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    return status, result


def experiments_snapshot() -> dict:
    outputs = stack_outputs(REGISTRY_STACK)
    response = experiment_lib.api_request(outputs["ExperimentsApiUrl"], "GET", "/experiments")
    model = build_view_model(response.get("experiments", []))
    model["request"] = {
        "service": "API Gateway + DynamoDB",
        "region": REGION,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    return model


def partner_chat(question: str, session_id: str | None = None) -> tuple[int, dict]:
    outputs = stack_outputs(SUPPORT_STACK)
    session_id = session_id or f"video-{uuid.uuid4().hex[:12]}"
    started = time.perf_counter()
    status, result = signed_post(
        role_session("aurora-games-client-operator-partner"),
        f"{outputs['ChatApiUrl']}chat",
        {"question": question, "session_id": session_id},
        timeout=60,
    )
    result["session_id"] = session_id
    model_invoked = bool(result.get("model_invoked"))
    result["request"] = {
        "service": (
            "API Gateway + Lambda + Amazon Bedrock"
            if model_invoked
            else "API Gateway + Lambda + governed knowledge"
        ),
        "identity": "client-operator-partner",
        "region": REGION,
        "duration_ms": round((time.perf_counter() - started) * 1000),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    return status, result


class ConsoleHandler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, status: int, body: dict) -> None:
        self._send(
            status,
            json.dumps(body, ensure_ascii=False, default=str).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path == "/api/health":
                self._json(200, {"status": "ready", "region": REGION, "mode": "live-aws"})
                return
            if path == "/api/m3/report":
                self._json(200, latest_first_look())
                return
            if path == "/api/m1/incidents":
                status, result = incidents_snapshot()
                self._json(status, result)
                return
            if path == "/api/m2/experiments":
                self._json(200, experiments_snapshot())
                return
            filename = "index.html" if path in {"", "/"} else path.lstrip("/")
            candidate = (STATIC_ROOT / filename).resolve()
            if STATIC_ROOT not in candidate.parents and candidate != STATIC_ROOT:
                self._send(403, b"forbidden", "text/plain")
                return
            if not candidate.is_file():
                self._send(404, b"not found", "text/plain")
                return
            content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
            if content_type.startswith("text/") or content_type in {"application/javascript", "application/json"}:
                content_type += "; charset=utf-8"
            self._send(200, candidate.read_bytes(), content_type)
        except Exception as error:  # pragma: no cover - exercised against AWS
            self._json(502, {"error": f"{type(error).__name__}: {error}"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            body = self._read_json()
            if path == "/api/m1/run":
                self._json(200, run_anomaly_scan())
                return
            if path == "/api/m1/incidents/status":
                incident_id = str(body.get("incident_id", "")).strip()
                status_value = str(body.get("status", "")).strip()
                if not incident_id or not status_value:
                    self._json(400, {"error": "incident_id and status are required"})
                    return
                status, result = update_incident_status(incident_id, status_value)
                self._json(status, result)
                return
            if path == "/api/m4/chat":
                question = str(body.get("question", "")).strip()
                if not question:
                    self._json(400, {"error": "question is required"})
                    return
                status, result = partner_chat(question, body.get("session_id"))
                self._json(status, result)
                return
            if path == "/api/m3/ask":
                question = str(body.get("question", "")).strip()
                if not question:
                    self._json(400, {"error": "question is required"})
                    return
                status, result = analytics_ask(question)
                self._json(status, result)
                return
            self._json(404, {"error": "not found"})
        except (ClientError, RuntimeError, ValueError, json.JSONDecodeError) as error:
            self._json(502, {"error": f"{type(error).__name__}: {error}"})

    def log_message(self, fmt: str, *values) -> None:
        print(f"[demo-console] {fmt % values}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the live AWS operation demo console.")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), ConsoleHandler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"Live AWS demo console: {url}")
    print("The browser receives no AWS credentials. Press Ctrl+C to stop.")
    if not args.no_open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDemo console stopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
