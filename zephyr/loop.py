"""The loop: five phases, each verified before the next starts.

  1. read_skill     — fetch skill.md, confirm it describes the loop
  2. authenticate   — challenge -> EIP-191 sign -> Bearer session
  3. list_bounties  — open bounties; pick the target slug; skip if the
                      agent already holds a submission there
  4. enter          — POST /<slug>/enter (free); verify-then-retry on drops
  5. submit         — research-driven prediction, POST /<slug>/submit
  6. verify         — GET /api/me/submissions confirms the entry landed

Every phase emits one human-readable transcript line and one JSON event
(machine-readable log). Secrets are masked at the emission point, never
at the call site, so no path can leak a token or a signature in full.
"""

import json
import time

from . import config, strategy
from .client import ApiError, ArenaClient, TransportError, mask_signature, mask_token


class PhaseRunner:
    def __init__(self, client=None, signer=None, slug=config.DEFAULT_SLUG,
                 handle=config.AGENT_HANDLE, address=config.AGENT_ADDRESS,
                 log=None):
        self.client = client or ArenaClient()
        self.signer = signer
        self.slug = slug
        self.handle = handle
        self.address = address
        self._log = log or (lambda line: print(line, flush=True))
        self.events = []

    # -- output ----------------------------------------------------------
    def emit(self, phase, message, **fields):
        event = {"ts": time.time(), "phase": phase, "msg": message, **fields}
        self.events.append(event)
        self._log(f"[{phase}] {message}")

    # -- phases ------------------------------------------------------------
    def read_skill(self):
        text = self.client.read_skill()
        assert "Authenticate" in text and "List open bounties" in text, \
            "skill.md does not describe the expected loop"
        self.emit("read_skill",
                  f"GET /skill.md -> {len(text)} chars; loop confirmed: "
                  "authenticate -> list -> enter -> submit")
        return text

    def authenticate(self):
        challenge = self.client.get_challenge(self.address)
        self.emit("authenticate",
                  f"challenge received ({len(challenge)} chars)")
        signature = self.signer.sign(challenge)
        self.emit("authenticate",
                  f"challenge signed (EIP-191 personal_sign) "
                  f"sig={mask_signature(signature)}")
        session = self.client.verify_signature(self.address, signature)
        self.emit("authenticate",
                  f"session token received token={mask_token(self.client.token)} "
                  f"expiresAt={session.get('expiresAt')}")
        return session

    def list_bounties(self):
        bounties = self.client.list_bounties(status="open")
        self.emit("list_bounties", f"{len(bounties)} open bounties")
        target = next((b for b in bounties if b.get("slug") == self.slug), None)
        if target is None:
            raise ApiError(0, f"target bounty {self.slug} is not open")
        self.emit("list_bounties",
                  f"target: {target['slug']} — {target.get('title')} "
                  f"({target.get('amt')} {target.get('unit')}, "
                  f"lane={target.get('lane')}, closes={target.get('closes')})")
        return target

    def _verified_enter(self):
        """Enter, verifying server state before any retry (see client.py)."""
        status, body = self.client.enter(self.slug, self.handle)
        if status in (200, 201):
            self.emit("enter", f"POST /{self.slug}/enter -> HTTP {status} "
                               f"entry id={body.get('id') or body.get('entryId')}")
            return body
        if status == 409:
            self.emit("enter", f"already entered (HTTP 409); continuing")
            return body
        raise ApiError(status, body)

    def enter(self):
        try:
            return self._verified_enter()
        except TransportError:
            # Connection dropped after the write may have landed: check
            # state first, only re-enter if the server has no record.
            self.emit("enter", "connection dropped mid-enter; verifying state "
                               "via GET /api/me/submissions before retrying")
            state = self.client.my_state()
            competing = [c.get("slug") for c in state.get("competing", [])]
            if self.slug in competing:
                self.emit("enter", "server already recorded the entry; "
                                   "no retry needed")
                return {"verified": True}
            return self._verified_enter()

    def submit(self):
        closes, price, change_24h = strategy.fetch_daily_closes()
        self.emit("submit", f"research: BTC ${price:,.2f} "
                            f"(24h {change_24h:+.2f}%, 7d "
                            f"{(closes[-1] / closes[0] - 1) * 100:+.2f}%) "
                            f"closes={['%.0f' % c for c in closes]}")
        prediction, reasoning = strategy.decide_btc_7d(closes, change_24h)
        self.emit("submit", f"prediction: {prediction} — {reasoning}")
        try:
            status, body = self.client.submit_prediction(
                self.slug, prediction, self.handle)
        except TransportError:
            self.emit("submit", "connection dropped mid-submit; verifying "
                                "state via GET /api/me/submissions")
            existing = self.client.already_entered(self.slug)
            if existing:
                self.emit("submit", "server already recorded the submission; "
                                    "no retry needed")
                return {"verified": True}
            status, body = self.client.submit_prediction(
                self.slug, prediction, self.handle)
        if status not in (200, 201):
            raise ApiError(status, body)
        self.emit("submit", f"POST /{self.slug}/submit -> HTTP {status} "
                            f"submission id={body.get('id')} "
                            f"status={body.get('status')}")
        return body

    def verify(self):
        subs = self.client.my_submissions()
        mine = [s for s in subs
                if (s.get("bountySlug") or s.get("slug")) == self.slug]
        if not mine:
            raise ApiError(0, f"no submission for {self.slug} on /api/me/submissions")
        entry = mine[0]
        self.emit("verify", f"confirmed on GET /api/me/submissions: "
                            f"id={entry.get('id')} status={entry.get('status')} "
                            f"({len(subs)} total submissions for this agent)")
        return entry

    def run(self):
        self.emit("loop", f"Zephyr sample agent — address={self.address} "
                          f"handle={self.handle} target={self.slug}")
        self.read_skill()
        self.authenticate()
        self.list_bounties()
        already = self.client.already_entered(self.slug)
        if already:
            self.emit("list_bounties",
                      f"already submitted to {self.slug}; refusing to duplicate")
            return self.verify()
        self.enter()
        result = self.submit()
        entry = self.verify()
        self.emit("loop", "DONE — full loop completed cleanly end to end")
        return {"submission": result, "verified": entry}


def run_loop(**kwargs):
    return PhaseRunner(**kwargs).run()


def events_json(runner):
    return json.dumps(runner.events, indent=2)
