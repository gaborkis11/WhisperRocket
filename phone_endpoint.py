#!/usr/bin/env python3
"""
WhisperRocket - Phone dictation endpoint

Receives an audio recording from an iPhone Shortcut over Tailscale and answers
with the finished text, ready for the phone's clipboard.

WHY THIS MODULE IMPORTS NOTHING FROM THE APP
--------------------------------------------
Everything here is standard library. That is the security design, not an
accident: this is the only code in WhisperRocket that a remote machine can
reach, so it is built so that it *cannot* touch the user's settings, history,
dictionary, style profile or file transcription - there is no import through
which it could. It knows how to speak HTTP, check a token and hand bytes to a
callback, and that is the whole of it.

The same idea guards the AI path, where ai_enhancer's import list is what
guarantees dictated text never reaches a memory system. A promise in a comment
is worth little; an import list is checkable.

Anything app-shaped is injected by the caller:
  - `dictate`      turns audio bytes into text
  - `ready_check`  answers whether the model is loaded yet
  - `messages`     the user-visible strings, already in the user's language

DESIGN NOTES
------------
Responses are plain text so the Shortcut can put the body straight on the
clipboard without a JSON-parsing step. Errors are short, speakable sentences,
because the Shortcut reads them aloud with Speak Text - the user is driving.

Failure never produces an empty 200. A silent empty clipboard is the one outcome
a driver cannot interpret.
"""
import hmac
import secrets
import sys
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Dict, Optional
from urllib.parse import parse_qs, urlparse

DEFAULT_PORT = 8771

# 25 MB is roughly 100 minutes of the m4a the Shortcut records. Generous for
# dictation, small enough that a bad request cannot exhaust memory.
DEFAULT_MAX_BYTES = 25 * 1024 * 1024

# Used only by the measurement helper on /health.
MAX_HEALTH_DELAY = 120

TOKEN_ENV_NAME = "WHISPERROCKET_PHONE_TOKEN"

# Per-socket-operation, not per-request: a dictation legitimately takes 25
# seconds to answer, but no single read or write should ever hang that long.
SOCKET_TIMEOUT = 60

DICTATE_PATH = "/dictate"
HEALTH_PATH = "/health"


@dataclass
class DictationOutcome:
    """What the injected callback hands back for one recording"""
    text: str = ""
    mode: str = "transcript"          # transcript | compose
    enhanced: bool = False            # did the AI cleanup deliver, or is this raw
    error: Optional[str] = None       # no_speech | not_ready | failed


# Which HTTP status each failure maps to. 422 rather than 200-with-empty-body so
# the Shortcut can branch and say something out loud.
ERROR_STATUS = {
    "no_speech": 422,
    "not_ready": 503,
    "failed": 500,
}

# English fallbacks, so the module runs standalone in tests. The app passes in
# translated versions of exactly these keys.
DEFAULT_MESSAGES = {
    "bad_request": "The recording did not arrive correctly.",
    "bad_token": "Wrong access key.",
    "not_found": "Unknown address.",
    "too_large": "The recording is too long.",
    "no_speech": "I did not hear any speech.",
    "busy": "The computer is busy, try again.",
    "not_ready": "The model is still loading.",
    "failed": "Something went wrong on the computer.",
    "health_ok": "WhisperRocket is ready.",
}


def generate_token() -> str:
    """A fresh bearer token for the phone to present"""
    return secrets.token_urlsafe(32)


def clamp_delay(raw) -> int:
    """
    Seconds the measurement helper should sleep, clamped to a sane range.

    A free function rather than a method so it can be tested without actually
    waiting - the first version could only be checked by sleeping through it.
    """
    try:
        return max(0, min(int(raw), MAX_HEALTH_DELAY))
    except (TypeError, ValueError):
        return 0


class _Server(ThreadingHTTPServer):
    """Threading server that carries a reference back to its endpoint"""
    daemon_threads = True
    endpoint = None       # set by PhoneEndpoint.start()

    def handle_error(self, request, client_address):
        """
        Report a client that hung up as one line rather than a traceback.

        This is not an edge case: the phone gives up after about a minute, so
        every dictation that outlasts its patience ends with the write failing
        here. Measured on an iPhone, the cutoff is between 60 and 70 seconds.

        The default handler dumps a full traceback, which looks like the server
        crashed when nothing is wrong with it - and it would appear exactly when
        the user is in the car wondering why there was no answer. Anything other
        than a dropped connection still gets the traceback, because that would be
        a real fault.
        """
        error = sys.exc_info()[1]
        if isinstance(error, (BrokenPipeError, ConnectionResetError)):
            host = client_address[0] if client_address else "?"
            print(f"[PHONE] {host} gave up waiting before the answer was sent")
            return
        super().handle_error(request, client_address)


class _Handler(BaseHTTPRequestHandler):
    # Announce as little as possible about what is running here.
    server_version = "WhisperRocket"
    sys_version = ""

    # HTTP/1.0 closes the connection after every response. Keep-alive would buy
    # nothing here - one recording, one answer - and closing means an oversized
    # request can be refused without reading its body at all.
    protocol_version = "HTTP/1.0"

    timeout = SOCKET_TIMEOUT

    # -- plumbing ---------------------------------------------------------

    def log_message(self, fmt, *args):
        """Route request logs into the app's own stdout log"""
        print(f"[PHONE] {self.address_string()} {fmt % args}")

    @property
    def _endpoint(self):
        return self.server.endpoint

    def _message(self, key: str) -> str:
        return self._endpoint.messages.get(key, DEFAULT_MESSAGES.get(key, key))

    def _respond(self, status: int, body: str, extra_headers: Optional[Dict] = None):
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(payload)

    def _authorized(self) -> bool:
        """
        Constant-time bearer token check.

        compare_digest rather than == so the comparison cannot be timed to
        recover the token character by character. The empty-token guard matters
        because compare_digest("", "") is True, and an endpoint that started
        without a token would otherwise accept everyone.
        """
        expected = self._endpoint.token or ""
        if not expected:
            return False

        header = self.headers.get("Authorization", "") or ""
        prefix = "Bearer "
        presented = header[len(prefix):] if header.startswith(prefix) else ""
        if not presented:
            return False

        return hmac.compare_digest(presented.encode("utf-8"), expected.encode("utf-8"))

    # -- routes -----------------------------------------------------------

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != HEALTH_PATH:
            return self._respond(404, self._message("not_found"))
        if not self._authorized():
            return self._respond(401, self._message("bad_token"))

        delay = self._requested_delay(parsed.query)
        if delay:
            # Measurement helper: answers how long the iPhone Shortcut is willing
            # to wait, which Apple does not document and which reports put
            # anywhere between 25 and 60 seconds. Bounded, token-protected, and
            # limited to two at a time so it cannot be used to tie the box up.
            if not self._endpoint.health_slot.acquire(blocking=False):
                return self._respond(429, self._message("busy"))
            try:
                time.sleep(delay)
            finally:
                self._endpoint.health_slot.release()

        ready_check = self._endpoint.ready_check
        if ready_check is not None and not ready_check():
            return self._respond(503, self._message("not_ready"))

        return self._respond(200, self._message("health_ok"))

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != DICTATE_PATH:
            return self._respond(404, self._message("not_found"))
        if not self._authorized():
            return self._respond(401, self._message("bad_token"))

        length = self._content_length()
        if length is None:
            return self._respond(400, self._message("bad_request"))
        if length > self._endpoint.max_bytes:
            # Refused on the header alone. With Connection: close we can answer
            # and hang up without ever reading the oversized body.
            return self._respond(413, self._message("too_large"))

        # One recording at a time. The second caller is told to retry rather than
        # queued, so a phone that gave up cannot leave work running behind it.
        if not self._endpoint.dictate_slot.acquire(blocking=False):
            return self._respond(429, self._message("busy"))

        try:
            audio = self.rfile.read(length)
            if len(audio) != length:
                return self._respond(400, self._message("bad_request"))

            try:
                outcome = self._endpoint.dictate(audio)
            except Exception as error:
                # A failure in the pipeline must not take the server down with
                # it - the next dictation should still work.
                print(f"[PHONE] dictation failed: {error}")
                return self._respond(500, self._message("failed"))

            if outcome.error:
                status = ERROR_STATUS.get(outcome.error, 500)
                return self._respond(status, self._message(outcome.error))

            if not outcome.text.strip():
                return self._respond(422, self._message("no_speech"))

            return self._respond(200, outcome.text, {
                "X-WhisperRocket-Mode": outcome.mode,
                "X-WhisperRocket-Enhanced": "1" if outcome.enhanced else "0",
            })
        finally:
            self._endpoint.dictate_slot.release()

    # -- request parsing --------------------------------------------------

    def _content_length(self) -> Optional[int]:
        raw = self.headers.get("Content-Length")
        if raw is None:
            return None
        try:
            length = int(raw)
        except (TypeError, ValueError):
            return None
        return length if length > 0 else None

    def _requested_delay(self, query: str) -> int:
        return clamp_delay(parse_qs(query).get("delay", ["0"])[0])


class PhoneEndpoint:
    """
    The HTTP server, started and stopped from the tray app.

    `host` must be the machine's Tailscale address. The caller establishes that -
    checking it here would mean importing the Tailscale helper, and the whole
    point of this module is that its import list stays empty of everything else.
    What is refused here is the mistake that would hurt most: binding to a
    wildcard address, which would put a dictation endpoint on every interface
    the machine has, including the one facing the router.
    """

    def __init__(self, host: str, port: int, token: str,
                 dictate: Callable[[bytes], DictationOutcome],
                 ready_check: Optional[Callable[[], bool]] = None,
                 messages: Optional[Dict[str, str]] = None,
                 max_bytes: int = DEFAULT_MAX_BYTES):
        self.host = host
        self.port = int(port)
        self.token = token
        self.dictate = dictate
        self.ready_check = ready_check
        self.messages = dict(DEFAULT_MESSAGES)
        if messages:
            self.messages.update(messages)
        self.max_bytes = max_bytes

        self.dictate_slot = threading.Semaphore(1)
        self.health_slot = threading.Semaphore(2)

        self._server = None
        self._thread = None

    @property
    def is_running(self) -> bool:
        return self._server is not None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}{DICTATE_PATH}"

    def start(self):
        """
        Bind and serve. Raises on a refused bind so the caller can show why.

        A wildcard host or a missing token is refused outright rather than
        started in a weaker configuration - both are mistakes that would only
        show up later, as an endpoint quietly reachable by more people than
        intended.
        """
        if self.is_running:
            return

        if self.host in ("", "0.0.0.0", "::", "*"):
            raise ValueError(
                "refusing to bind the phone endpoint to every interface - "
                "it must bind to the Tailscale address only"
            )
        if not self.token:
            raise ValueError("refusing to start the phone endpoint without a token")

        server = _Server((self.host, self.port), _Handler)
        server.endpoint = self

        self._server = server
        self._thread = threading.Thread(
            target=server.serve_forever,
            name="whisperrocket-phone-endpoint",
            daemon=True,
        )
        self._thread.start()
        print(f"[PHONE] listening on {self.url}")

    def stop(self):
        """Shut the server down and release the port. Safe to call twice."""
        server, thread = self._server, self._thread
        self._server, self._thread = None, None

        if server is None:
            return

        try:
            server.shutdown()
        except Exception:
            pass
        try:
            server.server_close()
        except Exception:
            pass
        if thread is not None:
            thread.join(timeout=5)
        print("[PHONE] stopped")
