"""CLI entrypoint: python3 -m zephyr [slug] [--dry-run]

Modes:
  live      full loop against https://aiprove.fun (default)
  --dry-run read skill.md + list bounties + research the prediction only;
            no auth, no enter, no submit. For testing the code path.
"""

import argparse
import sys

from . import config, strategy
from .client import ArenaClient
from .loop import PhaseRunner
from .signer import SignerError, default_signer


def dry_run(client, slug):
    print("[read_skill] fetching skill.md ...")
    text = client.read_skill()
    print(f"[read_skill] {len(text)} chars; loop confirmed")
    bounties = client.list_bounties(status="open")
    print(f"[list_bounties] {len(bounties)} open bounties")
    target = next((b for b in bounties if b.get("slug") == slug), None)
    print(f"[list_bounties] target: {target}")
    closes, price, change_24h = strategy.fetch_daily_closes()
    prediction, reasoning = strategy.decide_btc_7d(closes, change_24h)
    print(f"[research] BTC ${price:,.2f} (24h {change_24h:+.2f}%) "
          f"closes={['%.0f' % c for c in closes]}")
    print(f"[research] prediction for {slug}: {prediction} — {reasoning}")
    print("[dry-run] DONE — no auth, no enter, no submit performed")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="zephyr",
        description="Sample agent for the AIProve Arena bounty board.")
    parser.add_argument("slug", nargs="?", default=config.DEFAULT_SLUG,
                        help="bounty slug to enter (default: forecast-btc-7d)")
    parser.add_argument("--dry-run", action="store_true",
                        help="skill + list + research only; no auth or writes")
    parser.add_argument("--address", default=config.AGENT_ADDRESS)
    parser.add_argument("--handle", default=config.AGENT_HANDLE)
    args = parser.parse_args(argv)

    client = ArenaClient()
    if args.dry_run:
        return dry_run(client, args.slug)

    try:
        signer = default_signer()
    except SignerError as e:
        print(f"signer error: {e}", file=sys.stderr)
        return 2

    runner = PhaseRunner(client=client, signer=signer, slug=args.slug,
                         handle=args.handle, address=args.address)
    runner.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
