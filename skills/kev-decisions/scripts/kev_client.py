#!/usr/bin/env python3
"""Minimal native Kev / explicitly selected hosted Gradio client (stdlib only)."""
from __future__ import annotations

import argparse
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

LOCAL_URL = "http://127.0.0.1:8009"
HOSTED_URL = "https://jaredpalmer-kev.hf.space"


class KevError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise KevError("Redirect refused; verify the configured endpoint.")


def is_loopback(host: str | None) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host or "").is_loopback
    except ValueError:
        return False


def choose_endpoint(args):
    if args.hosted and args.url:
        raise KevError("Use either --hosted or --url, not both.")
    url = HOSTED_URL if args.hosted else (args.url or os.environ.get("KEV_BASE_URL") or LOCAL_URL)
    parsed = urlsplit(url)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {"", "/"}):
        raise KevError("Endpoint must be an http(s) origin, without credentials, path, query or fragment.")
    local = is_loopback(parsed.hostname)
    if not args.hosted and not local and not args.allow_remote:
        raise KevError("Non-loopback endpoint requires --allow-remote. No hosted fallback was attempted.")
    if not local and parsed.scheme != "https":
        raise KevError("Remote endpoints require HTTPS; use a localhost tunnel for a private native server.")
    token = os.environ.get("HF_TOKEN" if args.hosted else "KEV_API_KEY")
    if token and (not token.isascii() or any(ord(char) < 32 or ord(char) == 127 for char in token)):
        raise KevError("Authentication environment variable contains invalid characters.")
    return url.rstrip("/"), local, token


def validate_questions(questions):
    if not isinstance(questions, dict) or not questions:
        raise KevError("Questions must be a nonempty JSON object keyed by question ID.")
    for name, question in questions.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(question, dict):
            raise KevError("Each question needs a nonempty string ID and an object definition.")
        kind = question.get("type")
        criteria = question.get("criteria")
        if kind not in {"choice", "noul", "score"}:
            raise KevError("Question type must be choice, noul or score.")
        if kind == "choice" and (not isinstance(criteria, dict) or not criteria):
            raise KevError("Choice questions need a nonempty criteria object.")
        if kind == "score" and (not isinstance(criteria, list) or len(criteria) < 2):
            raise KevError("Score questions need an ordered criteria list with at least two levels.")


def strict_json(text):
    def reject_constant(value):
        raise KevError("JSON contains a non-finite numeric constant.")
    return json.loads(text, parse_constant=reject_constant)


class Client:
    def __init__(self, url, local, token=None, timeout=120):
        self.url, self.timeout = url, timeout
        self.headers = {"Accept": "application/json"}
        if token:
            self.headers["Authorization"] = "Bearer " + token
        handlers = [NoRedirect()]
        if local:
            handlers.append(ProxyHandler({}))
        self.opener = build_opener(*handlers)

    def open(self, path, payload=None, timeout=None):
        data = None if payload is None else json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        headers = dict(self.headers)
        if data is not None:
            headers["Content-Type"] = "application/json"
        return self.opener.open(Request(self.url + path, data=data, headers=headers), timeout=timeout or self.timeout)

    def json(self, path, payload=None):
        with self.open(path, payload) as response:
            return strict_json(response.read().decode("utf-8"))

    def hosted_result(self, event_id):
        if not isinstance(event_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", event_id):
            raise KevError("Service did not return a valid event_id.")
        deadline = time.monotonic() + self.timeout
        event, parts = "", []
        with self.open("/gradio_api/call/decide/" + event_id) as response:
            for raw in response:
                if time.monotonic() > deadline:
                    raise KevError("Timed out waiting for the hosted result.")
                line = raw.decode("utf-8").rstrip("\r\n")
                if line.startswith("event:"):
                    event = line[6:].strip()
                elif line.startswith("data:"):
                    parts.append(line[5:].lstrip())
                elif not line:
                    if event == "error":
                        raise KevError("Hosted inference reported an error; no decision was produced.")
                    if event == "complete":
                        data = strict_json("\n".join(parts))
                        if not isinstance(data, list) or len(data) != 3:
                            raise KevError("Unexpected hosted result schema; inspect /gradio_api/info.")
                        return {"result": data[1], "report": data[2]}
                    event, parts = "", []
        raise KevError("Hosted stream ended without a completed result.")


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["check", "decide"])
    p.add_argument("--url", help="Native server origin; default KEV_BASE_URL or localhost:8009")
    p.add_argument("--hosted", action="store_true", help="Explicitly use the Hugging Face Space")
    p.add_argument("--allow-remote", action="store_true", help="Allow a non-loopback native HTTPS server")
    p.add_argument("--timeout", type=float, default=120)
    p.add_argument("--state-file", type=Path)
    p.add_argument("--questions-file", type=Path)
    p.add_argument("--model", default="kev-latest", help="Native server model ID")
    p.add_argument("--hosted-model", choices=["Kev-4B", "Kev-0.8B", "Both"], default="Kev-4B")
    p.add_argument("--calibrated", action="store_true", help="Hosted calibration checkbox; native uses server config")
    p.add_argument("--date-facts", action="store_true", help="Hosted date preprocessing")
    p.add_argument("--check-stability", action="store_true", help="Hosted option-order check")
    p.add_argument("--n-perm", type=int, choices=[2, 3, 4, 6, 8], default=4)
    return p


def run(args):
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        raise KevError("Timeout must be a positive finite number.")
    url, local, token = choose_endpoint(args)
    if not args.hosted and (args.calibrated or args.date_facts or args.check_stability):
        raise KevError("These switches are hosted-only; see references/api.md for native settings.")
    # Validate/read inputs before making any network request.
    if args.command == "decide":
        if not args.state_file or not args.questions_file:
            raise KevError("decide requires --state-file and --questions-file.")
        state = args.state_file.read_text(encoding="utf-8-sig")
        if not state.strip():
            raise KevError("Document text is empty.")
        questions = strict_json(args.questions_file.read_text(encoding="utf-8-sig"))
        validate_questions(questions)
    client = Client(url, local, token, args.timeout)
    mode = "hosted-gradio" if args.hosted else ("native-local" if local else "native-remote")
    if args.command == "check":
        info = client.json("/gradio_api/info" if args.hosted else "/v1/models")
        if not isinstance(info, dict):
            raise KevError("Unexpected server metadata response.")
        if args.hosted:
            endpoints = info.get("named_endpoints")
            endpoint = endpoints.get("/decide") if isinstance(endpoints, dict) else None
            params = endpoint.get("parameters") if isinstance(endpoint, dict) else None
            if not isinstance(params, list) or not params or any(
                not isinstance(item, dict) or not isinstance(item.get("parameter_name"), str)
                for item in params
            ):
                raise KevError("Unexpected hosted /decide schema; inspect /gradio_api/info.")
            info = {"endpoint": "/decide", "parameters": [x["parameter_name"] for x in params]}
        elif not isinstance(info, dict) or not isinstance(info.get("data"), list):
            raise KevError("Unexpected native metadata response; verify /v1/models.")
        return {"mode": mode, "endpoint": url, "reachable": True, "metadata": info}
    if args.hosted:
        job = client.json("/gradio_api/call/v2/decide", {
            "state_text": state,
            "questions_json": json.dumps(questions, ensure_ascii=False),
            "model_choice": args.hosted_model,
            "calibrated": args.calibrated,
            "date_facts": args.date_facts,
            "check_stability": args.check_stability,
            "n_perm": args.n_perm,
        })
        if not isinstance(job, dict):
            raise KevError("Unexpected hosted submission response.")
        result = client.hosted_result(job.get("event_id"))
    else:
        result = {"result": client.json("/v1/systemone", {"state": state, "model": args.model, "questions": questions})}
        if not isinstance(result["result"], dict) or not isinstance(result["result"].get("answers"), dict):
            raise KevError("Unexpected native decision response; no valid answers object.")
    return {"mode": mode, "endpoint": url, **result}


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        result = run(parser().parse_args())
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except HTTPError as exc:
        message = f"Server returned HTTP {exc.code}; verify availability, credentials and request limits."
    except (URLError, TimeoutError, ConnectionError):
        message = "Could not reach the selected server. No automatic cloud fallback was attempted."
    except (KevError, OSError, ValueError) as exc:
        # Do not print server response bodies or credentials.
        message = str(exc)
    print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
