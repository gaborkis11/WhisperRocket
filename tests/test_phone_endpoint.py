#!/usr/bin/env python3
"""
Tests for phone_endpoint.py - the security-critical, network-facing module.

Runs the real HTTP server on 127.0.0.1 with a fake dictate callback, so the
security behaviour is proven without a model, a config or any user files being
anywhere near it. Standard library only - no test framework, no dependencies:

    python3 tests/test_phone_endpoint.py

Exit code 0 when every check passes.
"""
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phone_endpoint import DictationOutcome, PhoneEndpoint, generate_token

HOST = "127.0.0.1"
PORT = 8799
TOKEN = generate_token()

passed = 0
failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  {detail}")


def request(method="GET", path="/health", token=TOKEN, body=None, headers=None):
    """Returns (status, body_text, headers_dict). Never raises on HTTP errors."""
    url = f"http://{HOST}:{PORT}{path}"
    req = urllib.request.Request(url, method=method, data=body)
    if token is not None:
        req.add_header("Authorization", f"Bearer {token}")
    for name, value in (headers or {}).items():
        req.add_header(name, value)

    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            return response.status, response.read().decode("utf-8"), dict(response.headers)
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8"), dict(error.headers)


# --- the fake pipeline ---------------------------------------------------

calls = []
behaviour = {"mode": "ok", "sleep": 0.0}


def fake_dictate(audio_bytes):
    calls.append(len(audio_bytes))
    if behaviour["sleep"]:
        time.sleep(behaviour["sleep"])

    if behaviour["mode"] == "silence":
        return DictationOutcome(error="no_speech")
    if behaviour["mode"] == "not_ready":
        return DictationOutcome(error="not_ready")
    if behaviour["mode"] == "raise":
        raise RuntimeError("pipeline blew up")
    if behaviour["mode"] == "empty":
        return DictationOutcome(text="   ")
    if behaviour["mode"] == "compose":
        return DictationOutcome(text="megfogalmazott szoveg", mode="compose", enhanced=True)
    return DictationOutcome(text="ez a kesz szoveg", mode="transcript", enhanced=True)


ready = {"value": True}

endpoint = PhoneEndpoint(
    host=HOST, port=PORT, token=TOKEN,
    dictate=fake_dictate,
    ready_check=lambda: ready["value"],
)


# --- tests ---------------------------------------------------------------

def test_refuses_bad_configuration():
    print("\n[1] Refuses a dangerous configuration before binding")

    for bad_host in ("0.0.0.0", "", "::", "*"):
        try:
            PhoneEndpoint(bad_host, PORT, TOKEN, fake_dictate).start()
            check(f"wildcard host {bad_host!r} refused", False, "it started!")
        except ValueError:
            check(f"wildcard host {bad_host!r} refused", True)
        except Exception as error:
            check(f"wildcard host {bad_host!r} refused", False, f"wrong error: {error}")

    try:
        PhoneEndpoint(HOST, PORT, "", fake_dictate).start()
        check("empty token refused", False, "it started!")
    except ValueError:
        check("empty token refused", True)


def test_auth():
    print("\n[2] Token")

    status, body, _ = request(token=None)
    check("no Authorization header -> 401", status == 401, f"got {status}")
    check("401 body is a speakable sentence", body and not body.startswith("<"), repr(body))

    status, _, _ = request(token="wrong-token")
    check("wrong token -> 401", status == 401, f"got {status}")

    status, _, _ = request(token=TOKEN[:-1])
    check("token missing last char -> 401", status == 401, f"got {status}")

    status, _, _ = request(token=TOKEN + "x")
    check("token with extra char -> 401", status == 401, f"got {status}")

    status, _, _ = request(token=TOKEN)
    check("correct token -> 200", status == 200, f"got {status}")


def test_routes():
    print("\n[3] Only two routes exist")

    for path in ("/", "/config.json", "/../config.json", "/history", "/dictate/../health"):
        status, _, _ = request(method="GET", path=path)
        check(f"GET {path} -> 404", status == 404, f"got {status}")

    status, _, _ = request(method="POST", path="/health", body=b"x")
    check("POST /health -> 404", status == 404, f"got {status}")

    status, _, _ = request(method="GET", path="/dictate")
    check("GET /dictate -> 404", status == 404, f"got {status}")


def test_unauthorised_before_anything_else():
    print("\n[4] Auth is checked before the body is touched")

    calls.clear()
    status, _, _ = request(method="POST", path="/dictate", token="wrong", body=b"audio")
    check("bad token on /dictate -> 401", status == 401, f"got {status}")
    check("pipeline never ran", not calls, f"calls={calls}")


def test_size_limit():
    print("\n[5] Size limit")

    calls.clear()
    status, _, _ = request(
        method="POST", path="/dictate", body=b"x",
        headers={"Content-Length": str(endpoint.max_bytes + 1)},
    )
    check("oversized Content-Length -> 413", status == 413, f"got {status}")
    check("oversized body never reached the pipeline", not calls, f"calls={calls}")

    status, _, _ = request(method="POST", path="/dictate", body=b"")
    check("empty body -> 400", status == 400, f"got {status}")


def test_success():
    print("\n[6] A successful dictation")

    behaviour["mode"] = "ok"
    calls.clear()
    status, body, headers = request(method="POST", path="/dictate", body=b"pretend-m4a-bytes")

    check("200", status == 200, f"got {status}")
    check("body is the text itself", body == "ez a kesz szoveg", repr(body))
    check("pipeline saw the bytes", calls == [17], f"calls={calls}")
    check("mode header", headers.get("X-WhisperRocket-Mode") == "transcript", str(headers))
    check("enhanced header", headers.get("X-WhisperRocket-Enhanced") == "1", str(headers))
    check("utf-8 content type",
          "utf-8" in headers.get("Content-Type", "").lower(), str(headers))

    behaviour["mode"] = "compose"
    status, body, headers = request(method="POST", path="/dictate", body=b"audio")
    check("compose mode reported in header",
          headers.get("X-WhisperRocket-Mode") == "compose", str(headers))


def test_multipart_upload():
    """
    Android's Tasker always wraps a file in multipart/form-data, so the raw-body
    shape that iOS Shortcuts sends is not enough on its own.
    """
    print("\n[6b] Multipart upload (how Android sends it)")

    audio = b"\x00\x01PRETEND-M4A-BYTES\xff\xfe"
    boundary = "----WhisperRocketTestBoundary"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="../../etc/passwd"\r\n'
        "Content-Type: audio/m4a\r\n\r\n"
    ).encode() + audio + f"\r\n--{boundary}--\r\n".encode()

    behaviour["mode"] = "ok"
    calls.clear()
    status, text, _ = request(
        method="POST", path="/dictate", body=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    check("multipart accepted", status == 200, f"got {status} {text}")
    check("exact file bytes reached the pipeline", calls == [len(audio)],
          f"calls={calls} expected {[len(audio)]}")

    # A hostile filename must not matter, because it is never read.
    from phone_endpoint import extract_multipart_file
    got = extract_multipart_file(body, f"multipart/form-data; boundary={boundary}")
    check("extracted bytes are byte-identical", got == audio, repr(got[:40]))

    quoted = extract_multipart_file(body, f'multipart/form-data; boundary="{boundary}"')
    check("quoted boundary handled", quoted == audio)

    check("no boundary -> body returned unchanged",
          extract_multipart_file(b"raw", "multipart/form-data") == b"raw")
    check("garbage multipart -> body returned unchanged",
          extract_multipart_file(b"raw", "multipart/form-data; boundary=") == b"raw")

    calls.clear()
    unparseable = b"nothing-parseable-here"
    status, _, _ = request(
        method="POST", path="/dictate", body=unparseable,
        headers={"Content-Type": "multipart/form-data; boundary=zzz"},
    )
    check("unparseable multipart still reaches the pipeline as raw bytes",
          status == 200 and calls == [len(unparseable)], f"status={status} calls={calls}")


def test_utf8_text():
    print("\n[7] Hungarian accents survive the round trip")

    original = "Árvíztűrő tükörfúrógép, basszus, hogy őrizze meg."

    def accented(_audio):
        return DictationOutcome(text=original, enhanced=True)

    endpoint.dictate = accented
    try:
        status, body, _ = request(method="POST", path="/dictate", body=b"audio")
        check("200", status == 200, f"got {status}")
        check("text identical byte for byte", body == original, repr(body))
        check("swearing kept", "basszus" in body, repr(body))
    finally:
        endpoint.dictate = fake_dictate


def test_failure_modes():
    print("\n[8] Failures never produce an empty 200")

    behaviour["mode"] = "silence"
    status, body, _ = request(method="POST", path="/dictate", body=b"audio")
    check("silence -> 422", status == 422, f"got {status}")
    check("422 has a spoken message", bool(body.strip()), repr(body))

    behaviour["mode"] = "empty"
    status, body, _ = request(method="POST", path="/dictate", body=b"audio")
    check("whitespace-only text -> 422", status == 422, f"got {status}")

    behaviour["mode"] = "not_ready"
    status, _, _ = request(method="POST", path="/dictate", body=b"audio")
    check("model loading -> 503", status == 503, f"got {status}")

    behaviour["mode"] = "raise"
    status, body, _ = request(method="POST", path="/dictate", body=b"audio")
    check("pipeline exception -> 500", status == 500, f"got {status}")
    check("500 has a spoken message", bool(body.strip()), repr(body))

    behaviour["mode"] = "ok"
    status, _, _ = request(method="POST", path="/dictate", body=b"audio")
    check("server still alive after the exception", status == 200, f"got {status}")


def test_concurrency():
    print("\n[9] One dictation at a time")

    behaviour["mode"] = "ok"
    behaviour["sleep"] = 2.0
    results = {}

    def slow_call():
        results["first"] = request(method="POST", path="/dictate", body=b"audio")[0]

    thread = threading.Thread(target=slow_call)
    thread.start()
    time.sleep(0.4)

    status, _, _ = request(method="POST", path="/dictate", body=b"audio")
    check("second concurrent dictation -> 429", status == 429, f"got {status}")

    thread.join()
    check("first dictation still succeeded", results.get("first") == 200, str(results))

    behaviour["sleep"] = 0.0
    status, _, _ = request(method="POST", path="/dictate", body=b"audio")
    check("slot released afterwards", status == 200, f"got {status}")


def test_health_and_delay():
    print("\n[10] /health and the timeout measurement helper")

    ready["value"] = True
    status, body, _ = request(path="/health")
    check("healthy -> 200", status == 200, f"got {status}")
    check("has a message", bool(body.strip()), repr(body))

    ready["value"] = False
    status, _, _ = request(path="/health")
    check("model not loaded -> 503", status == 503, f"got {status}")
    ready["value"] = True

    started = time.time()
    status, _, _ = request(path="/health?delay=3")
    elapsed = time.time() - started
    check("delay=3 answers 200", status == 200, f"got {status}")
    check("delay=3 really waited ~3s", 2.5 <= elapsed <= 9.0, f"{elapsed:.2f}s")

    status, _, _ = request(path="/health?delay=abc")
    check("garbage delay ignored", status == 200, f"got {status}")

    status, _, _ = request(path="/health?delay=-5")
    check("negative delay ignored", status == 200, f"got {status}")


def test_delay_clamping():
    """Checked directly rather than by sleeping through it"""
    print("\n[10b] The delay parameter cannot be used to tie the machine up")

    from phone_endpoint import MAX_HEALTH_DELAY, clamp_delay

    check("9999 clamped to the maximum", clamp_delay("9999") == MAX_HEALTH_DELAY,
          str(clamp_delay("9999")))
    check("negative becomes 0", clamp_delay("-5") == 0)
    check("garbage becomes 0", clamp_delay("abc") == 0)
    check("None becomes 0", clamp_delay(None) == 0)
    check("empty becomes 0", clamp_delay("") == 0)
    check("float string becomes 0", clamp_delay("3.5") == 0)
    check("a normal value passes through", clamp_delay("30") == 30)
    check("the maximum is well past any plausible Shortcuts timeout",
          MAX_HEALTH_DELAY >= 90, str(MAX_HEALTH_DELAY))


def test_binding_is_local_only():
    print("\n[11] The socket is bound to one address, not to everything")

    import socket

    # The server runs on 127.0.0.1 here. Reaching it on any other local address
    # would prove the bind is wider than asked for - the same check that matters
    # for the Tailscale address in production.
    other_addresses = []
    hostname = socket.gethostname()
    try:
        for info in socket.getaddrinfo(hostname, PORT, socket.AF_INET, socket.SOCK_STREAM):
            address = info[4][0]
            if address != "127.0.0.1":
                other_addresses.append(address)
    except Exception:
        pass

    if not other_addresses:
        print("      (no second local address to try - skipped)")
        return

    for address in set(other_addresses):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        reachable = sock.connect_ex((address, PORT)) == 0
        sock.close()
        check(f"not reachable on {address}", not reachable,
              "the endpoint is listening more widely than intended")


def test_client_hangup_is_not_a_crash():
    """
    The phone gives up after about a minute; measured cutoff 60-70s on an iPhone.
    Every dictation that outlasts it ends with the response write failing, so
    that path has to read as one calm line rather than a traceback.
    """
    print("\n[11b] A client that hangs up mid-answer")

    import contextlib
    import io
    import socket

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((HOST, PORT))
        sock.sendall(
            f"GET /health?delay=3 HTTP/1.0\r\n"
            f"Authorization: Bearer {TOKEN}\r\n\r\n".encode()
        )
        time.sleep(0.3)
        sock.close()          # walk away before the answer comes
        time.sleep(4.5)       # let the server finish its sleep and try to write

    output = captured.getvalue()
    check("logs a plain line, not a traceback", "Traceback" not in output, output[:300])
    check("says the client gave up", "gave up waiting" in output, output[:300])

    status, _, _ = request(path="/health")
    check("server still serving afterwards", status == 200, f"got {status}")


def test_stop_releases_port():
    print("\n[12] Stopping releases the port")

    endpoint.stop()
    check("is_running false after stop", not endpoint.is_running)

    endpoint.stop()
    check("stopping twice is harmless", True)

    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    refused = sock.connect_ex((HOST, PORT)) != 0
    sock.close()
    check("port no longer accepts connections", refused)

    endpoint.start()
    status, _, _ = request(path="/health")
    check("restart works", status == 200, f"got {status}")


def main():
    test_refuses_bad_configuration()

    endpoint.start()
    time.sleep(0.3)
    try:
        test_auth()
        test_routes()
        test_unauthorised_before_anything_else()
        test_size_limit()
        test_success()
        test_multipart_upload()
        test_utf8_text()
        test_failure_modes()
        test_concurrency()
        test_health_and_delay()
        test_delay_clamping()
        test_binding_is_local_only()
        test_client_hangup_is_not_a_crash()
        test_stop_releases_port()
    finally:
        endpoint.stop()

    print(f"\n{'='*50}")
    print(f"passed: {passed}   failed: {failed}")
    print(f"{'='*50}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
