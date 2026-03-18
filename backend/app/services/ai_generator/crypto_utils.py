"""
Pure cipher functions for crypto_text_web CTF challenges.

All functions are synchronous and have no external dependencies.
apply_chain / reverse_chain are the main entry points.
"""
import base64
from typing import Any


class CryptoError(ValueError):
    pass


# ── Individual ciphers ──────────────────────────────────────────────────────

def caesar_encrypt(text: str, shift: int) -> str:
    shift = shift % 26
    result = []
    for ch in text:
        if ch.isalpha():
            base = ord("A") if ch.isupper() else ord("a")
            result.append(chr((ord(ch) - base + shift) % 26 + base))
        else:
            result.append(ch)
    return "".join(result)


def caesar_decrypt(text: str, shift: int) -> str:
    return caesar_encrypt(text, -shift)


def vigenere_encrypt(text: str, key: str) -> str:
    if not key or not key.isalpha():
        raise CryptoError("Vigenere key must be non-empty alphabetic string")
    key = key.upper()
    result = []
    key_idx = 0
    for ch in text:
        if ch.isalpha():
            shift = ord(key[key_idx % len(key)]) - ord("A")
            base = ord("A") if ch.isupper() else ord("a")
            result.append(chr((ord(ch) - base + shift) % 26 + base))
            key_idx += 1
        else:
            result.append(ch)
    return "".join(result)


def vigenere_decrypt(text: str, key: str) -> str:
    if not key or not key.isalpha():
        raise CryptoError("Vigenere key must be non-empty alphabetic string")
    key = key.upper()
    result = []
    key_idx = 0
    for ch in text:
        if ch.isalpha():
            shift = ord(key[key_idx % len(key)]) - ord("A")
            base = ord("A") if ch.isupper() else ord("a")
            result.append(chr((ord(ch) - base - shift) % 26 + base))
            key_idx += 1
        else:
            result.append(ch)
    return "".join(result)


def xor_encrypt(text: str, key: str) -> str:
    if not key:
        raise CryptoError("XOR key must be non-empty")
    key_bytes = key.encode("utf-8")
    text_bytes = text.encode("utf-8")
    result = bytes(b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(text_bytes))
    # Return as hex so it stays printable
    return result.hex()


def xor_decrypt(text: str, key: str) -> str:
    if not key:
        raise CryptoError("XOR key must be non-empty")
    try:
        data = bytes.fromhex(text)
    except ValueError as exc:
        raise CryptoError(f"XOR decrypt: invalid hex input — {exc}") from exc
    key_bytes = key.encode("utf-8")
    result = bytes(b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(data))
    return result.decode("utf-8", errors="replace")


def base64_encode(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def base64_decode(text: str) -> str:
    try:
        return base64.b64decode(text.encode("ascii")).decode("utf-8", errors="replace")
    except Exception as exc:
        raise CryptoError(f"Base64 decode failed: {exc}") from exc


def reverse_string(text: str) -> str:
    return text[::-1]


# ── Chain apply / reverse ────────────────────────────────────────────────────

def _apply_single(text: str, op: dict[str, Any]) -> str:
    """Apply one operation from a crypto_chain spec."""
    name = op.get("cipher") or op.get("type") or ""
    params = op.get("params", {}) or {}

    if name == "caesar":
        return caesar_encrypt(text, int(params.get("shift", 3)))
    elif name == "vigenere":
        return vigenere_encrypt(text, str(params.get("key", "KEY")))
    elif name == "xor":
        return xor_encrypt(text, str(params.get("key", "K")))
    elif name == "base64":
        return base64_encode(text)
    elif name == "reverse":
        return reverse_string(text)
    else:
        raise CryptoError(f"Unknown cipher: {name!r}")


def _reverse_single(text: str, op: dict[str, Any]) -> str:
    """Reverse one operation from a crypto_chain spec."""
    name = op.get("cipher") or op.get("type") or ""
    params = op.get("params", {}) or {}

    if name == "caesar":
        return caesar_decrypt(text, int(params.get("shift", 3)))
    elif name == "vigenere":
        return vigenere_decrypt(text, str(params.get("key", "KEY")))
    elif name == "xor":
        return xor_decrypt(text, str(params.get("key", "K")))
    elif name == "base64":
        return base64_decode(text)
    elif name == "reverse":
        return reverse_string(text)
    else:
        raise CryptoError(f"Unknown cipher: {name!r}")


def apply_chain(plaintext: str, chain: list[dict[str, Any]]) -> str:
    """Apply a list of cipher operations sequentially."""
    result = plaintext
    for op in chain:
        result = _apply_single(result, op)
    return result


def reverse_chain(ciphertext: str, chain: list[dict[str, Any]]) -> str:
    """Apply inverse operations in reverse order to recover plaintext."""
    result = ciphertext
    for op in reversed(chain):
        result = _reverse_single(result, op)
    return result
