#!/bin/bash
# Run Zephyr against the live board. The key never lives in this repo:
# either point AGENT_SIGNER_COMMAND at a command that signs on the host
# holding the key, or export AGENT_PRIVATE_KEY for the local signer.
set -euo pipefail
cd "$(dirname "$0")"
exec python3 -m zephyr "$@"
