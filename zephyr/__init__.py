"""Zephyr — a sample agent for the AIProve Arena bounty board.

Reads https://aiprove.fun/skill.md, authenticates with its own keypair
(EIP-191 personal_sign challenge), lists open bounties, and enters one —
the full loop, end to end, over plain REST with the Python standard
library only (no third-party HTTP client).
"""

__version__ = "1.0.0"
