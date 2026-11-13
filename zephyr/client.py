"""HTTP client for the AIProve board: one class, stdlib urllib only.

Two reliability rules live here:

1. Every request carries a browser User-Agent, otherwise the edge
   returns 403/1010.
2. A write whose connection drops *after* the server processed it must
   never be blindly retried. Callers verify state first
   (GET /api/me/submissions) before re-issuing a write; this client
   surfaces the drop as a TransportError so the caller can do that.
"""

import json
import http.client
import time
import urllib.error
import urllib.request

from . import config


class TransportError(Exception):
    """The request never produced a usable HTTP response (dropped, DNS, ...)."""


class ApiError(Exception):
    """The server answered with a non-2xx status."""

    def __init__(self, status, body):
        super().__init__(f"HTTP {status}: {body}")
        self.status = status
        self.body = body


def mask_token(token):
    """Short masked form for logs: first 8 chars, never the whole token."""
    if not token:
        return "<none>"
    return token[:8] + "..."


def mask_signature(sig):
    """A one-time EIP-191 signature is a proof, not a secret — still mask it."""
    if not sig:
        return "<none>"
    return sig[:10] + "..." + sig[-6:]


class ArenaClient:
    """Thin wrapper over the board's REST surface (see skill.md §5)."""

    def __init__(self, base_url=config.API_BASE_URL, timeout=config.HTTP_TIMEOUT,
                 retries=config.HTTP_RETRIES):
        self.base_url = base_url
        self.timeout = timeout
        self.retries = retries
        self.token = None

    # -- low level -----------------------------------------------------
    def _request(self, method, path, payload=None, auth=False):
        url = self.base_url + path
        data = json.dumps(payload).encode() if payload is not None else None
        headers = {"User-Agent": config.USER_AGENT}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if auth:
            if not self.token:
                raise ApiError(0, "authenticated call without a session token")
            headers["Authorization"] = "Bearer " + self.token

        last_error = None
        for attempt in range(self.retries):
            req = urllib.request.Request(url, data=data, headers=headers,
                                         method=method)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return resp.status, json.loads(resp.read() or b"{}")
            except urllib.error.HTTPError as e:
                try:
                    body = json.loads(e.read() or b"{}")
                except ValueError:
                    body = {"raw": ""}
                return e.code, body
            except (urllib.error.URLError, TimeoutError, ConnectionError,
                    http.client.IncompleteRead, http.client.HTTPException) as e:
                # Dropped mid-response. GETs are idempotent: retry. Writes
                # are NOT retried here — the server may have processed
                # them, so the caller verifies state first.
                last_error = e
                if method != "GET":
                    raise TransportError(
                        f"{method} {path} transport failure: {e}")
                time.sleep(2 * (attempt + 1))
        raise TransportError(f"{method} {path} failed after {self.retries} "
                             f"attempts: {last_error}")

    # -- board surface ---------------------------------------------------
    def health(self):
        return self._request("GET", "/api/health")

    def read_skill(self):
        """GET /skill.md — returns the raw markdown text (idempotent: retried)."""
        import http.client
        last_error = None
        for attempt in range(self.retries):
            try:
                req = urllib.request.Request(
                    config.SKILL_URL, headers={"User-Agent": config.USER_AGENT})
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return resp.read().decode()
            except (urllib.error.URLError, http.client.IncompleteRead,
                    TimeoutError, ConnectionError) as e:
                last_error = e
                time.sleep(2 * (attempt + 1))
        raise TransportError(f"GET /skill.md failed: {last_error}")

    def get_challenge(self, address):
        status, body = self._request(
            "GET", f"/api/auth/challenge?address={address}")
        if status != 200 or "challenge" not in body:
            raise ApiError(status, body)
        return body["challenge"]

    def verify_signature(self, address, signature):
        status, body = self._request("POST", "/api/auth/verify",
                                     {"address": address, "signature": signature})
        if status != 200 or "token" not in body:
            raise ApiError(status, body)
        self.token = body["token"]
        return body

    def list_bounties(self, status="open"):
        code, body = self._request("GET", f"/api/bounties?status={status}")
        if code != 200:
            raise ApiError(code, body)
        if isinstance(body, list):
            return body
        return body.get("bounties", [])

    def get_bounty(self, slug):
        code, body = self._request("GET", f"/api/bounties/{slug}")
        if code != 200:
            raise ApiError(code, body)
        return body.get("bounty", body)

    def my_submissions(self):
        code, body = self._request("GET", "/api/me/submissions", auth=True)
        if code != 200:
            raise ApiError(code, body)
        if isinstance(body, list):
            return body
        return body.get("submissions", [])

    def my_state(self):
        code, body = self._request("GET", "/api/me", auth=True)
        if code != 200:
            raise ApiError(code, body)
        return body

    def enter(self, slug, handle):
        """POST /<slug>/enter — free. Returns (status, body)."""
        return self._request("POST", f"/api/bounties/{slug}/enter",
                             {"handle": handle}, auth=True)

    def submit_prediction(self, slug, prediction, handle):
        """POST /<slug>/submit with a prediction payload."""
        return self._request("POST", f"/api/bounties/{slug}/submit",
                             {"prediction": prediction, "handle": handle},
                             auth=True)

    def already_entered(self, slug):
        """State check used before any (re)try of a write."""
        try:
            subs = self.my_submissions()
        except (TransportError, ApiError):
            return None  # unknown — caller must not assume
        return any((s.get("bountySlug") or s.get("slug")) == slug for s in subs)
