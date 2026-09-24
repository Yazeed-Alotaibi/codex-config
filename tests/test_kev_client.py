"""Client contract tests against a disposable loopback HTTP server."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch


CLIENT_PATH = Path(__file__).resolve().parents[1] / "skills" / "kev-decisions" / "scripts" / "kev_client.py"
SPEC = importlib.util.spec_from_file_location("kev_client", CLIENT_PATH)
assert SPEC is not None and SPEC.loader is not None
kev = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(kev)
DEFAULT_LOCAL_URL = kev.LOCAL_URL


class FakeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.respond()

    def do_POST(self):
        self.respond()

    def respond(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.server.requests.append((self.command, self.path, dict(self.headers), body))
        status, headers, response = self.server.routes.get(
            (self.command, self.path), (404, {}, b"Unexpected test request")
        )
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, format, *args):
        pass


class KevClientTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="kev-client-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.state = "تأخر تسليم المضخة ثلاثة أسابيع. café — 東京\n"
        self.questions = {
            "التأخير": {
                "type": "choice",
                "instructions": "ما المشكلة المذكورة؟",
                "criteria": {"delay": "تأخير", "other": "سبب آخر"},
            },
            "mentions_delay": {"type": "noul", "instructions": "Is a delay stated?"},
            "urgency": {"type": "score", "criteria": ["Low", "Medium", "High"]},
        }
        self.state_file = self.root / "state.txt"
        self.questions_file = self.root / "questions.json"
        self.state_file.write_text(self.state, encoding="utf-8-sig")
        self.write_questions(self.questions)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeHandler)
        self.server.requests = []
        self.server.routes = {}
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        # Both selectable origins stay on the test server, including on regressions.
        self.enterContext(patch.object(kev, "LOCAL_URL", self.url))
        self.enterContext(patch.object(kev, "HOSTED_URL", self.url))
        self.enterContext(patch.dict(os.environ, {}, clear=True))

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def write_questions(self, questions):
        self.questions_file.write_text(json.dumps(questions, ensure_ascii=False), encoding="utf-8-sig")

    def route(self, method, path, body, status=200, headers=None):
        response_headers = {"Content-Type": "application/json"}
        response_headers.update(headers or {})
        if isinstance(body, bytes):
            raw = body
        else:
            raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.server.routes[(method, path)] = (status, response_headers, raw)

    def invoke(self, *arguments):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", [str(CLIENT_PATH), *arguments]), redirect_stdout(stdout), redirect_stderr(stderr):
            code = kev.main()
        if code == 0:
            self.assertEqual(stderr.getvalue(), "")
            return code, json.loads(stdout.getvalue())
        self.assertEqual(stdout.getvalue(), "")
        error = json.loads(stderr.getvalue())
        self.assertEqual(set(error), {"error"})
        return code, error

    def decide(self, *arguments):
        return self.invoke("decide", "--state-file", str(self.state_file), "--questions-file", str(self.questions_file), *arguments)

    def test_native_metadata_and_decision_preserve_questions_object_and_unicode(self):
        metadata = {"data": [{"id": "kev-test"}]}
        answers = {"التأخير": {"value": "delay", "confidence": 0.8}}
        self.route("GET", "/v1/models", metadata)
        self.route("POST", "/v1/systemone", {"model": "kev-test", "answers": answers})
        # A local connection must not use an ambient HTTP proxy.
        with patch.dict(os.environ, {"HTTP_PROXY": "http://proxy.invalid:9", "KEV_API_KEY": "test-native-token"}):
            code, readiness = self.invoke("check", "--url", self.url)
            self.assertEqual(code, 0)
            self.assertEqual(readiness, {"mode": "native-local", "endpoint": self.url, "reachable": True, "metadata": metadata})
            code, decision = self.decide("--url", self.url, "--model", "kev-test")
        self.assertEqual(code, 0)
        self.assertEqual(decision["result"]["answers"], answers)
        self.assertEqual([(r[0], r[1]) for r in self.server.requests], [("GET", "/v1/models"), ("POST", "/v1/systemone")])
        _, _, headers, body = self.server.requests[1]
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["Authorization"], "Bearer test-native-token")
        self.assertEqual(json.loads(body), {"state": self.state, "model": "kev-test", "questions": self.questions})
        self.assertIn("المضخة".encode("utf-8"), body)

    def test_http_failures_are_clean_and_do_not_echo_server_bodies(self):
        for status in (401, 422, 500):
            with self.subTest(status=status):
                self.route("POST", "/v1/systemone", {"detail": "private document and secret token"}, status=status)
                code, error = self.decide()
                self.assertEqual(code, 1)
                self.assertIn(str(status), error["error"])
                self.assertNotIn("private document", error["error"])
                self.assertNotIn("secret token", error["error"])

    def test_missing_or_malformed_input_fails_before_any_request(self):
        code, _ = self.invoke("decide", "--state-file", str(self.state_file))
        self.assertEqual(code, 1)
        invalid = (
            {}, [], {"": {"type": "noul"}}, {"issue": []},
            {"issue": {"type": "unknown"}},
            {"issue": {"type": "choice", "criteria": []}},
            {"issue": {"type": "score", "criteria": ["only one"]}},
        )
        for questions in invalid:
            with self.subTest(questions=questions):
                self.write_questions(questions)
                self.assertEqual(self.decide()[0], 1)
        for raw in ('{"issue":', '{"issue": {"type": "noul", "value": NaN}}'):
            with self.subTest(raw=raw):
                self.questions_file.write_text(raw, encoding="utf-8")
                self.assertEqual(self.decide()[0], 1)
        self.write_questions(self.questions)
        self.state_file.write_text(" \n", encoding="utf-8")
        self.assertEqual(self.decide()[0], 1)
        self.assertEqual(self.server.requests, [])

    def test_remote_native_requires_consent_and_https(self):
        args = kev.parser().parse_args(["check", "--url", "https://example.invalid"])
        with self.assertRaisesRegex(kev.KevError, "allow-remote"):
            kev.choose_endpoint(args)
        args.allow_remote = True
        self.assertEqual(kev.choose_endpoint(args), ("https://example.invalid", False, None))
        args.url = "http://example.invalid"
        with self.assertRaisesRegex(kev.KevError, "HTTPS"):
            kev.choose_endpoint(args)
        with patch.dict(os.environ, {"KEV_BASE_URL": "https://example.invalid"}):
            with self.assertRaisesRegex(kev.KevError, "allow-remote"):
                kev.choose_endpoint(kev.parser().parse_args(["check"]))
        self.assertEqual(self.server.requests, [])

    def test_invalid_origins_and_conflicting_endpoint_flags_are_rejected(self):
        origins = ("ftp://localhost", "http://user:pass@localhost", "http://localhost/path", "http://localhost?x=1", "http://localhost#fragment", "http://")
        for origin in origins:
            with self.subTest(origin=origin):
                self.assertEqual(self.invoke("check", "--url", origin)[0], 1)
        self.assertEqual(self.invoke("check", "--hosted", "--url", self.url)[0], 1)
        self.assertEqual(self.server.requests, [])

    def test_default_is_local_and_failure_never_falls_back_to_hosted(self):
        self.assertEqual(DEFAULT_LOCAL_URL, "http://127.0.0.1:8009")
        self.route("GET", "/v1/models", {"detail": "offline"}, status=503)
        self.route("GET", "/gradio_api/info", {"named_endpoints": {"/decide": {"parameters": []}}})
        code, error = self.invoke("check")
        self.assertEqual(code, 1)
        self.assertIn("503", error["error"])
        self.assertEqual([(r[0], r[1]) for r in self.server.requests], [("GET", "/v1/models")])

    def test_redirects_are_not_followed_for_metadata_or_documents(self):
        self.route("GET", "/v1/models", b"", status=302, headers={"Location": self.url + "/forbidden"})
        self.route("POST", "/v1/systemone", b"", status=307, headers={"Location": self.url + "/forbidden"})
        self.assertEqual(self.invoke("check")[0], 1)
        self.assertEqual(self.decide()[0], 1)
        self.assertEqual([r[1] for r in self.server.requests], ["/v1/models", "/v1/systemone"])

    def test_hosted_payload_uses_json_string_and_reads_complete_after_heartbeat(self):
        result = {"التأخير": {"value": "delay"}}
        complete = json.dumps(["<p>untrusted HTML</p>", result, "تقرير: تأخير"], ensure_ascii=False)
        stream = (": comment\r\nevent: heartbeat\r\ndata: null\r\n\r\n"
                  "event: generating\ndata: []\n\n"
                  f"event: complete\ndata: {complete}\n\n").encode("utf-8")
        self.route("POST", "/gradio_api/call/v2/decide", {"event_id": "event_1-safe"})
        self.route("GET", "/gradio_api/call/decide/event_1-safe", stream, headers={"Content-Type": "text/event-stream"})
        with patch.dict(os.environ, {"HF_TOKEN": "test-hosted-token"}):
            code, output = self.decide("--hosted", "--hosted-model", "Kev-0.8B", "--calibrated", "--date-facts", "--check-stability", "--n-perm", "6")
        self.assertEqual(code, 0)
        self.assertEqual(output, {"mode": "hosted-gradio", "endpoint": self.url, "result": result, "report": "تقرير: تأخير"})
        method, path, headers, raw = self.server.requests[0]
        self.assertEqual((method, path), ("POST", "/gradio_api/call/v2/decide"))
        payload = json.loads(raw)
        self.assertIsInstance(payload["questions_json"], str)
        self.assertEqual(json.loads(payload.pop("questions_json")), self.questions)
        self.assertEqual(payload, {"state_text": self.state, "model_choice": "Kev-0.8B", "calibrated": True, "date_facts": True, "check_stability": True, "n_perm": 6})
        self.assertEqual(headers["Authorization"], "Bearer test-hosted-token")
        self.assertEqual(self.server.requests[1][1], "/gradio_api/call/decide/event_1-safe")

    def test_hosted_stream_errors_incomplete_streams_and_bad_results_fail_cleanly(self):
        self.route("POST", "/gradio_api/call/v2/decide", {"event_id": "event1"})
        streams = (
            b"event: error\ndata: private server error\n\n",
            b"event: heartbeat\ndata: null\n\n",
            b"event: complete\ndata: [1, 2]\n\n",
            b"event: complete\ndata: not-json\n\n",
        )
        for stream in streams:
            with self.subTest(stream=stream):
                self.route("GET", "/gradio_api/call/decide/event1", stream, headers={"Content-Type": "text/event-stream"})
                code, error = self.decide("--hosted")
                self.assertEqual(code, 1)
                self.assertNotIn("private server error", error["error"])

    def test_bad_hosted_event_ids_fail_without_fetching_an_event(self):
        for event_id in (None, "", "../other", "event?token=secret", 123, [], "事件"):
            with self.subTest(event_id=event_id):
                self.server.requests.clear()
                self.route("POST", "/gradio_api/call/v2/decide", {"event_id": event_id})
                self.assertEqual(self.decide("--hosted")[0], 1)
                self.assertEqual([r[1] for r in self.server.requests], ["/gradio_api/call/v2/decide"])

    def test_wrong_response_shapes_fail_as_client_errors(self):
        for metadata in ([], {}, {"data": {}}):
            with self.subTest(native_metadata=metadata):
                self.route("GET", "/v1/models", metadata)
                self.assertEqual(self.invoke("check")[0], 1)
        for decision in ([], {}, {"answers": []}):
            with self.subTest(native_decision=decision):
                self.route("POST", "/v1/systemone", decision)
                self.assertEqual(self.decide()[0], 1)
        for metadata in ([], {"named_endpoints": []}, {"named_endpoints": {"/decide": "invalid"}}, {"named_endpoints": {"/decide": {"parameters": [None]}}}):
            with self.subTest(hosted_metadata=metadata):
                self.route("GET", "/gradio_api/info", metadata)
                self.assertEqual(self.invoke("check", "--hosted")[0], 1)
        self.route("POST", "/gradio_api/call/v2/decide", [])
        self.assertEqual(self.decide("--hosted")[0], 1)


if __name__ == "__main__":
    unittest.main()
