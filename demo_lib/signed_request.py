"""SigV4-signed HTTP for the demo scripts.

The APIs require IAM authorisation, so a plain POST no longer works - requests
must be signed with credentials whose identity the handler then uses to decide
tenant scope (Module 3) or audit-track access (Module 4). That coupling is the
point: identity is not a header the caller fills in, it is the thing that
signed the request.

Uses botocore's signer directly rather than adding a dependency like
requests-aws4auth - botocore is already present because boto3 is.
"""
import json
import urllib.error
import urllib.request

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

OPERATOR_ROLE_NAME = "aurora-games-operator"


def role_arn(account_id: str, role_name: str) -> str:
    return f"arn:aws:iam::{account_id}:role/{role_name}"


def assume(role_name: str, session_name: str = "demo") -> boto3.Session:
    sts = boto3.client("sts")
    account_id = sts.get_caller_identity()["Account"]
    creds = sts.assume_role(
        RoleArn=role_arn(account_id, role_name), RoleSessionName=session_name
    )["Credentials"]
    return boto3.Session(
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
    )


def signed_request(
    session: boto3.Session,
    method: str,
    url: str,
    payload: dict | None = None,
    timeout: int = 45,
) -> tuple:
    """Sends a SigV4-signed JSON request. Returns (status_code, parsed_body).

    Returns rather than raises on 4xx/5xx, because several demos deliberately
    provoke a 403 to show the tenant boundary working.
    """
    body = json.dumps(payload) if payload is not None else None
    request = AWSRequest(method=method, url=url, data=body,
                          headers={"Content-Type": "application/json"})
    credentials = session.get_credentials().get_frozen_credentials()
    region = session.region_name or "ap-northeast-1"
    SigV4Auth(credentials, "execute-api", region).add_auth(request)

    req = urllib.request.Request(
        url,
        data=body.encode("utf-8") if body is not None else None,
        headers=dict(request.headers),
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {"raw": raw.decode("utf-8", "replace")}


def signed_post(session: boto3.Session, url: str, payload: dict, timeout: int = 45) -> tuple:
    return signed_request(session, "POST", url, payload, timeout)
