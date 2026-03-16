"""
Artifact creator: converts a generated spec into a concrete CTF artifact.

Currently supports: crypto_text_web
Other task types will be added in subsequent chunks.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from app.services.ai_generator.crypto_utils import apply_chain, CryptoError

logger = logging.getLogger(__name__)


@dataclass
class ArtifactResult:
    # For crypto: the ciphertext string
    # For forensics/xss: not used directly (file_url is the artifact)
    content: Optional[str] = None
    # S3 URL for file-based artifacts (forensics, xss)
    file_url: Optional[str] = None
    # Data needed for validation (e.g. the chain used, flag location)
    verification_data: dict[str, Any] = field(default_factory=dict)
    # Error message if artifact creation failed
    error: Optional[str] = None


class ArtifactCreationError(RuntimeError):
    pass


async def create_artifact(task_type: str, spec: dict[str, Any]) -> ArtifactResult:
    """Dispatch to the appropriate artifact creator based on task_type."""
    if task_type == "crypto_text_web":
        return _create_crypto_text(spec)
    return ArtifactResult(error=f"Unsupported task_type for artifact creation: {task_type!r}")


def _create_crypto_text(spec: dict[str, Any]) -> ArtifactResult:
    """
    Apply the crypto_chain to the flag to produce ciphertext.

    Expected spec keys: flag, crypto_chain (list of {cipher, params})
    """
    flag = (spec.get("flag") or "").strip()
    crypto_chain = spec.get("crypto_chain") or []

    if not flag:
        return ArtifactResult(error="spec missing 'flag'")
    if not crypto_chain or not isinstance(crypto_chain, list):
        return ArtifactResult(error="spec missing or invalid 'crypto_chain'")

    try:
        ciphertext = apply_chain(flag, crypto_chain)
    except CryptoError as exc:
        return ArtifactResult(error=f"apply_chain failed: {exc}")
    except Exception as exc:
        logger.exception("Unexpected error in apply_chain")
        return ArtifactResult(error=f"apply_chain unexpected error: {exc}")

    return ArtifactResult(
        content=ciphertext,
        verification_data={"chain": crypto_chain, "flag": flag},
    )
