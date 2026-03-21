"""
Pure cipher functions for crypto_text_web CTF challenges.

All functions are synchronous and have no external dependencies (except
aes_ecb which uses the `cryptography` package already in requirements.txt).
apply_chain / reverse_chain are the main entry points.

Supported cipher names (use in crypto_chain[].cipher):
  Classical:   caesar, rot13, vigenere, atbash, beaufort, substitution, rail_fence
  Encoding:    base64, base32, base58, hex, url
  Modern:      xor, aes_ecb
  Misc:        reverse
"""
import base64
from typing import Any
from urllib.parse import quote, unquote


class CryptoError(ValueError):
    pass


# ── Classical ciphers ────────────────────────────────────────────────────────

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


def atbash(text: str) -> str:
    """Atbash substitution: A↔Z, B↔Y, etc. Self-inverse."""
    result = []
    for ch in text:
        if ch.isalpha():
            base = ord("A") if ch.isupper() else ord("a")
            result.append(chr(base + 25 - (ord(ch) - base)))
        else:
            result.append(ch)
    return "".join(result)


def beaufort(text: str, key: str) -> str:
    """Beaufort cipher: C = (K - P) mod 26. Self-inverse (encrypt == decrypt)."""
    if not key or not key.isalpha():
        raise CryptoError("Beaufort key must be non-empty alphabetic string")
    key = key.upper()
    result = []
    key_idx = 0
    for ch in text:
        if ch.isalpha():
            k = ord(key[key_idx % len(key)]) - ord("A")
            p = ord(ch.upper()) - ord("A")
            c = (k - p) % 26
            result.append(chr(c + (ord("A") if ch.isupper() else ord("a"))))
            key_idx += 1
        else:
            result.append(ch)
    return "".join(result)


def substitution_encrypt(text: str, key: str) -> str:
    """Monoalphabetic substitution. key must be 26 unique alpha chars (A-Z mapping)."""
    key = key.upper()
    if len(key) != 26 or not key.isalpha() or len(set(key)) != 26:
        raise CryptoError("Substitution key must be 26 unique alphabetic characters")
    result = []
    for ch in text:
        if ch.isalpha():
            idx = ord(ch.upper()) - ord("A")
            c = key[idx]
            result.append(c if ch.isupper() else c.lower())
        else:
            result.append(ch)
    return "".join(result)


def substitution_decrypt(text: str, key: str) -> str:
    key = key.upper()
    if len(key) != 26 or not key.isalpha() or len(set(key)) != 26:
        raise CryptoError("Substitution key must be 26 unique alphabetic characters")
    reverse = [""] * 26
    for i, k in enumerate(key):
        reverse[ord(k) - ord("A")] = chr(ord("A") + i)
    result = []
    for ch in text:
        if ch.isalpha():
            idx = ord(ch.upper()) - ord("A")
            c = reverse[idx]
            result.append(c if ch.isupper() else c.lower())
        else:
            result.append(ch)
    return "".join(result)


def rail_fence_encrypt(text: str, rails: int) -> str:
    if rails < 2 or rails >= len(text):
        return text
    fence: list[list[str]] = [[] for _ in range(rails)]
    rail, direction = 0, 1
    for ch in text:
        fence[rail].append(ch)
        if rail == 0:
            direction = 1
        elif rail == rails - 1:
            direction = -1
        rail += direction
    return "".join("".join(r) for r in fence)


def rail_fence_decrypt(text: str, rails: int) -> str:
    if rails < 2 or rails >= len(text):
        return text
    n = len(text)
    # Build position pattern
    pattern: list[int] = []
    rail, direction = 0, 1
    for _ in range(n):
        pattern.append(rail)
        if rail == 0:
            direction = 1
        elif rail == rails - 1:
            direction = -1
        rail += direction
    # Map original positions sorted by rail
    indices = sorted(range(n), key=lambda i: pattern[i])
    result = [""] * n
    for pos, orig_idx in enumerate(indices):
        result[orig_idx] = text[pos]
    return "".join(result)


# ── Encoding ─────────────────────────────────────────────────────────────────

def base64_encode(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def base64_decode(text: str) -> str:
    try:
        return base64.b64decode(text.encode("ascii")).decode("utf-8", errors="replace")
    except Exception as exc:
        raise CryptoError(f"Base64 decode failed: {exc}") from exc


def base32_encode(text: str) -> str:
    return base64.b32encode(text.encode("utf-8")).decode("ascii")


def base32_decode(text: str) -> str:
    try:
        padded = text.upper()
        missing = len(padded) % 8
        if missing:
            padded += "=" * (8 - missing)
        return base64.b32decode(padded).decode("utf-8", errors="replace")
    except Exception as exc:
        raise CryptoError(f"Base32 decode failed: {exc}") from exc


_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def base58_encode(text: str) -> str:
    data = text.encode("utf-8")
    if not data:
        return ""
    n = int.from_bytes(data, "big")
    result: list[str] = []
    while n > 0:
        n, rem = divmod(n, 58)
        result.append(_B58_ALPHABET[rem])
    leading = sum(1 for b in data if b == 0)
    return _B58_ALPHABET[0] * leading + "".join(reversed(result))


def base58_decode(text: str) -> str:
    if not text:
        return ""
    n = 0
    for ch in text:
        idx = _B58_ALPHABET.find(ch)
        if idx == -1:
            raise CryptoError(f"Invalid Base58 character: {ch!r}")
        n = n * 58 + idx
    leading = sum(1 for ch in text if ch == _B58_ALPHABET[0])
    if n == 0:
        result_bytes = b"\x00" * leading
    else:
        byte_len = (n.bit_length() + 7) // 8
        result_bytes = b"\x00" * leading + n.to_bytes(byte_len, "big")
    return result_bytes.decode("utf-8", errors="replace")


def hex_encode(text: str) -> str:
    return text.encode("utf-8").hex()


def hex_decode(text: str) -> str:
    try:
        return bytes.fromhex(text).decode("utf-8", errors="replace")
    except ValueError as exc:
        raise CryptoError(f"Hex decode failed: {exc}") from exc


def url_encode(text: str) -> str:
    return quote(text, safe="")


def url_decode(text: str) -> str:
    return unquote(text)


def reverse_string(text: str) -> str:
    return text[::-1]


# ── Modern symmetric ─────────────────────────────────────────────────────────

def xor_encrypt(text: str, key: str) -> str:
    if not key:
        raise CryptoError("XOR key must be non-empty")
    key_bytes = key.encode("utf-8")
    text_bytes = text.encode("utf-8")
    result = bytes(b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(text_bytes))
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


def aes_ecb_encrypt(text: str, key_hex: str) -> str:
    """AES-ECB encrypt. key_hex: 32/48/64 hex chars (16/24/32 byte key)."""
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding as _padding
    except ImportError as exc:
        raise CryptoError("cryptography package required for AES") from exc
    try:
        key = bytes.fromhex(key_hex)
    except ValueError as exc:
        raise CryptoError(f"AES key must be hex-encoded: {exc}") from exc
    if len(key) not in (16, 24, 32):
        raise CryptoError(f"AES key must be 16, 24 or 32 bytes; got {len(key)}")
    padder = _padding.PKCS7(128).padder()
    data = padder.update(text.encode("utf-8")) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.ECB())
    enc = cipher.encryptor()
    return (enc.update(data) + enc.finalize()).hex()


def aes_ecb_decrypt(text: str, key_hex: str) -> str:
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding as _padding
    except ImportError as exc:
        raise CryptoError("cryptography package required for AES") from exc
    try:
        key = bytes.fromhex(key_hex)
        ct = bytes.fromhex(text)
    except ValueError as exc:
        raise CryptoError(f"AES decrypt: invalid hex input — {exc}") from exc
    if len(key) not in (16, 24, 32):
        raise CryptoError(f"AES key must be 16, 24 or 32 bytes; got {len(key)}")
    cipher = Cipher(algorithms.AES(key), modes.ECB())
    dec = cipher.decryptor()
    padded = dec.update(ct) + dec.finalize()
    unpadder = _padding.PKCS7(128).unpadder()
    return (unpadder.update(padded) + unpadder.finalize()).decode("utf-8", errors="replace")


# ── Chain apply / reverse ────────────────────────────────────────────────────

def _apply_single(text: str, op: dict[str, Any]) -> str:
    name = (op.get("cipher") or op.get("type") or "").lower()
    params = op.get("params", {}) or {}

    if name == "caesar":
        return caesar_encrypt(text, int(params.get("shift", 3)))
    elif name == "rot13":
        return caesar_encrypt(text, 13)
    elif name == "vigenere":
        return vigenere_encrypt(text, str(params.get("key", "KEY")))
    elif name == "atbash":
        return atbash(text)
    elif name == "beaufort":
        return beaufort(text, str(params.get("key", "KEY")))
    elif name == "substitution":
        return substitution_encrypt(text, str(params.get("key", "ZYXWVUTSRQPONMLKJIHGFEDCBA")))
    elif name == "rail_fence":
        return rail_fence_encrypt(text, int(params.get("rails", 3)))
    elif name == "xor":
        return xor_encrypt(text, str(params.get("key", "K")))
    elif name == "aes_ecb":
        return aes_ecb_encrypt(text, str(params.get("key", "00" * 16)))
    elif name == "base64":
        return base64_encode(text)
    elif name == "base32":
        return base32_encode(text)
    elif name == "base58":
        return base58_encode(text)
    elif name == "hex":
        return hex_encode(text)
    elif name == "url":
        return url_encode(text)
    elif name == "reverse":
        return reverse_string(text)
    else:
        raise CryptoError(f"Unknown cipher: {name!r}")


def _reverse_single(text: str, op: dict[str, Any]) -> str:
    name = (op.get("cipher") or op.get("type") or "").lower()
    params = op.get("params", {}) or {}

    if name == "caesar":
        return caesar_decrypt(text, int(params.get("shift", 3)))
    elif name == "rot13":
        return caesar_encrypt(text, 13)   # rot13 is self-inverse
    elif name == "vigenere":
        return vigenere_decrypt(text, str(params.get("key", "KEY")))
    elif name == "atbash":
        return atbash(text)               # self-inverse
    elif name == "beaufort":
        return beaufort(text, str(params.get("key", "KEY")))  # self-inverse
    elif name == "substitution":
        return substitution_decrypt(text, str(params.get("key", "ZYXWVUTSRQPONMLKJIHGFEDCBA")))
    elif name == "rail_fence":
        return rail_fence_decrypt(text, int(params.get("rails", 3)))
    elif name == "xor":
        return xor_decrypt(text, str(params.get("key", "K")))
    elif name == "aes_ecb":
        return aes_ecb_decrypt(text, str(params.get("key", "00" * 16)))
    elif name == "base64":
        return base64_decode(text)
    elif name == "base32":
        return base32_decode(text)
    elif name == "base58":
        return base58_decode(text)
    elif name == "hex":
        return hex_decode(text)
    elif name == "url":
        return url_decode(text)
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
