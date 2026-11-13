"""Signers: how the agent proves it owns its address.

The agent never holds a private key unless the operator explicitly hands
it one. Two implementations of one tiny protocol — sign(challenge) ->
hex signature — so the key can live wherever the operator keeps it:

* LocalSigner   — eth_account, key from AGENT_PRIVATE_KEY. For an operator
                  running the agent where the key already lives.
* CommandSigner — shells out to an external command that receives the
                  challenge as its only argument and prints the signature.
                  The key stays on the remote host; only the challenge and
                  the one-time signature cross the wire.

The runner picks CommandSigner when AGENT_SIGNER_COMMAND is set, else
LocalSigner when AGENT_PRIVATE_KEY is set, and refuses to run otherwise.
"""

import subprocess

from . import config


class SignerError(Exception):
    pass


class LocalSigner:
    """Sign with a key supplied via AGENT_PRIVATE_KEY (kept out of logs)."""

    def __init__(self, private_key=config.AGENT_PRIVATE_KEY,
                 address=config.AGENT_ADDRESS):
        if not private_key:
            raise SignerError("AGENT_PRIVATE_KEY is not set")
        try:
            from eth_account import Account
            from eth_account.messages import encode_defunct
        except ImportError as e:  # pragma: no cover
            raise SignerError("eth_account is required for the local signer; "
                              "pip install eth-account") from e
        self._encode = encode_defunct
        self._account = Account.from_key(private_key)
        if self._account.address.lower() != address.lower():
            raise SignerError("AGENT_PRIVATE_KEY does not match AGENT_ADDRESS")

    def sign(self, challenge):
        message = self._encode(text=challenge)
        return self._account.sign_message(message).signature.hex()


class CommandSigner:
    """Sign by delegating to an external command (key never leaves its host).

    The command is invoked as: <AGENT_SIGNER_COMMAND> <challenge>
    and must print exactly one hex signature on stdout.
    """

    def __init__(self, command=config.SIGNER_COMMAND):
        if not command:
            raise SignerError("AGENT_SIGNER_COMMAND is not set")
        self._command = command

    def sign(self, challenge):
        proc = subprocess.run(
            self._command.split() + [challenge],
            capture_output=True, text=True, timeout=60,
        )
        if proc.returncode != 0:
            raise SignerError(f"signer command failed: {proc.stderr.strip()[:200]}")
        signature = proc.stdout.strip().split()[-1]
        if signature.startswith("0x"):
            signature = signature[2:]
        if len(signature) != 130 or not all(
                c in "0123456789abcdefABCDEF" for c in signature):
            raise SignerError("signer command did not return a 65-byte hex signature")
        return "0x" + signature.lower()


def default_signer():
    """Resolve the signer from the environment, command first."""
    if config.SIGNER_COMMAND:
        return CommandSigner()
    if config.AGENT_PRIVATE_KEY:
        return LocalSigner()
    raise SignerError(
        "no signer configured: set AGENT_SIGNER_COMMAND (key stays remote) "
        "or AGENT_PRIVATE_KEY (key in this process only)"
    )
