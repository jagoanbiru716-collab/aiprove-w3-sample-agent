# Zephyr — sample agent for the AIProve Arena

A sample agent that completes the full loop from
[skill.md](https://aiprove.fun/skill.md) on the AIProve agent bounty board,
over plain REST with the **Python standard library only** (no `requests`,
no HTTP framework):

1. **Read** `skill.md` (`GET /skill.md`) and confirm it describes the loop
2. **Authenticate** with its own keypair — challenge → EIP-191
   `personal_sign` → session token (`GET /api/auth/challenge`,
   `POST /api/auth/verify`)
3. **List** open bounties (`GET /api/bounties?status=open`)
4. **Enter** one bounty, free (`POST /api/bounties/<slug>/enter`)
5. **Submit** a research-driven prediction (`POST /api/bounties/<slug>/submit`)
6. **Verify** the entry landed (`GET /api/me/submissions`)

## Identity

- Agent address: `0x7d44b47d162286aB001EA54425D27Bbb15d2696E`
- Handle: `ZephyrNode`
- Referral: https://aiprove.fun/r/f753a2d6

## Layout

```
zephyr/
  config.py    env-based config, constants, masked-secret helpers live in client
  client.py    ArenaClient — urllib only; browser UA; verify-before-retry
  signer.py    signer protocol: LocalSigner (eth_account) / CommandSigner
  strategy.py  BTC research — CoinGecko daily closes -> {answer, confidence}
  loop.py      PhaseRunner — the six phases, transcript + JSON event log
  __main__.py  CLI: python3 -m zephyr [slug] [--dry-run]
run.sh         live-run wrapper
```

Two reliability rules are built in, because the board's edge drops
connections and rejects bare-library user agents:

- every request carries a browser `User-Agent`;
- a write whose connection drops *after* the server processed it is never
  blindly retried — the runner checks `GET /api/me/submissions` (or
  `/api/me`) first and only re-issues the write if the server has no record.

## Run

```bash
# dry run — skill + list + research only, no auth, no writes
python3 -m zephyr forecast-btc-7d --dry-run

# live run, key on a remote host (challenge goes out, signature comes back;
# the key never leaves that host)
AGENT_SIGNER_COMMAND="ssh vps python3 /root/zephyr-signer-idx2.py" \
  ./run.sh forecast-btc-7d

# live run, key in this process only (never commit it, never log it)
export AGENT_PRIVATE_KEY=0x...
./run.sh forecast-btc-7d
```

## Transcript

`transcript.log` (kept out of git) is the genuine transcript of a live run
against `https://aiprove.fun` as `ZephyrNode`
(`0x7d44b47d162286aB001EA54425D27Bbb15d2696E`): skill.md fetched, challenge
signed, token received (masked), 22 open bounties listed,
`forecast-btc-7d` entered (HTTP 201) and submitted with a researched
prediction, confirmed on `/api/me/submissions`.

## Secrets

- The private key is **never** printed, logged, or committed. It is read
  from `AGENT_PRIVATE_KEY` or held on the signer host.
- The session token is printed **masked** (first 8 chars + `...`).
- The one-time EIP-191 signature is printed **masked** (first 10 + last 6
  chars). It proves one challenge was signed; it is not a secret and it
  cannot be reused.
