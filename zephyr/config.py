"""Configuration: every tunable lives here, read from the environment.

No secrets are ever hard-coded. The private key is supplied either through
the AGENT_PRIVATE_KEY environment variable (local signer) or through an
external signer command (see zephyr/signer.py); the session token is held
in memory only and is masked in all output.
"""

import os

API_BASE_URL = os.environ.get("API_BASE_URL", "https://aiprove.fun").rstrip("/")
SKILL_URL = API_BASE_URL + "/skill.md"

# The agent's own identity: its Ethereum-style address. Public by design —
# it is how the board knows the agent.
AGENT_ADDRESS = os.environ.get(
    "AGENT_ADDRESS", "0x7d44b47d162286aB001EA54425D27Bbb15d2696E"
)
AGENT_HANDLE = os.environ.get("AGENT_HANDLE", "ZephyrNode")

# Which bounty the loop should enter. Default is the 7-day BTC direction
# call; any open slug can be passed on the command line instead.
DEFAULT_SLUG = os.environ.get("BOUNTY_SLUG", "forecast-btc-7d")

# Browser-style User-Agent: the board's edge rejects bare/library UAs.
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

HTTP_TIMEOUT = float(os.environ.get("HTTP_TIMEOUT", "30"))
HTTP_RETRIES = int(os.environ.get("HTTP_RETRIES", "5"))

# External signer command. It receives the challenge as its single argument
# and must print the EIP-191 signature as one hex string on stdout.
# Example: an ssh call to a host that holds the key.
SIGNER_COMMAND = os.environ.get("AGENT_SIGNER_COMMAND", "")

# Private key for the built-in local signer (never logged, never written).
AGENT_PRIVATE_KEY = os.environ.get("AGENT_PRIVATE_KEY", "")
