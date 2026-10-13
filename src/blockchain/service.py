import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from src.blockchain.anchor import anchor_hash, get_web3
from src.blockchain.verify import get_anchored_hash, verify_data

load_dotenv()


def is_blockchain_enabled() -> bool:
    """Check if Sepolia blockchain anchoring is explicitly enabled and configured."""
    enabled = os.getenv("BLOCKCHAIN_ANCHOR_ENABLED", "false").lower() == "true"
    has_rpc = bool(os.getenv("SEPOLIA_RPC_URL"))
    has_pk = bool(os.getenv("PRIVATE_KEY"))
    has_wallet = bool(os.getenv("WALLET_ADDRESS"))
    return enabled and has_rpc and has_pk and has_wallet


def anchor_manifest_to_blockchain(
    manifest_hash: str,
    wait_for_receipt: bool = True,
    timeout_seconds: int = 120,
) -> Dict[str, Any]:
    """
    Submits the manifest SHA-256 hash to Sepolia Ethereum.
    CRITICAL: Never marks confirmed without verifying its receipt.
    States: unanchored, pending, confirmed, failed.
    """
    if not is_blockchain_enabled():
        return {
            "status": "unanchored",
            "message": "Blockchain anchoring is disabled or credentials are not configured in .env.",
            "transaction_hash": None,
            "block_number": None,
            "anchored_at": None,
            "verification": "NOT_RUN",
        }

    try:
        # Submit transaction
        tx_hash = anchor_hash(manifest_hash)
        now_utc = datetime.now(timezone.utc).isoformat()

        if not wait_for_receipt:
            return {
                "status": "pending",
                "transaction_hash": tx_hash,
                "block_number": None,
                "anchored_at": now_utc,
                "hash": manifest_hash,
                "verification": "PENDING",
            }

        # Wait for receipt to guarantee confirmed status
        web3 = get_web3()
        receipt = web3.eth.wait_for_transaction_receipt(
            tx_hash,
            timeout=timeout_seconds,
            poll_latency=3,
        )

        if receipt.get("status") == 1:
            return {
                "status": "confirmed",
                "transaction_hash": tx_hash,
                "block_number": receipt.get("blockNumber"),
                "anchored_at": now_utc,
                "hash": manifest_hash,
                "verification": "VERIFIED",
            }
        else:
            return {
                "status": "failed",
                "transaction_hash": tx_hash,
                "block_number": receipt.get("blockNumber"),
                "anchored_at": now_utc,
                "hash": manifest_hash,
                "error": "Transaction execution reverted on Sepolia (receipt status 0).",
                "verification": "FAILED",
            }

    except Exception as err:
        return {
            "status": "failed",
            "transaction_hash": None,
            "block_number": None,
            "anchored_at": None,
            "hash": manifest_hash,
            "error": str(err),
            "verification": "FAILED",
        }


def normalize_digest_bytes(digest: str) -> Optional[bytes]:
    """
    Normalizes a SHA-256 digest string to 32 raw bytes without modifying algorithms.
    Handles optional 0x prefix, leading/trailing whitespace, and case insensitivity.
    Returns None if not a valid 32-byte (64 hex character) digest.
    """
    if not digest or not isinstance(digest, str):
        return None
    cleaned = digest.strip().lower()
    if cleaned.startswith("0x"):
        cleaned = cleaned[2:]
    if len(cleaned) == 64 and all(c in "0123456789abcdef" for c in cleaned):
        try:
            return bytes.fromhex(cleaned)
        except ValueError:
            return None
    return None


def verify_anchored_manifest(
    manifest_hash: str,
    transaction_hash: str,
    anchored_at: Optional[str] = None,
    analyzed_at: Optional[str] = None,
    known_prior_hashes: Optional[list] = None,
) -> Dict[str, Any]:
    """
    Retrieves the anchored payload from Sepolia and compares against the local manifest hash.
    Classifies verification results into:
      - VERIFIED: on-chain digest matches expected manifest digest.
      - OUTDATED_ANCHOR: transaction is valid on-chain, but anchors a previous manifest digest
        (superseded by subsequent re-analysis).
      - TAMPERED / MISMATCH: transaction exists and has valid FaceChain payload, but does not match manifest.
      - MALFORMED: transaction data exists on-chain but has invalid format/non-FaceChain payload.
      - NOT_FOUND: transaction hash was not found on Sepolia ledger.
      - ERROR: Sepolia RPC node or network failure.
    """
    if not transaction_hash:
        return {
            "verified": False,
            "status": "UNANCHORED",
            "reason": "No blockchain transaction hash recorded for this evidence.",
            "manifest_hash": manifest_hash,
            "transaction_hash": None,
        }

    expected_bytes = normalize_digest_bytes(manifest_hash)
    if not expected_bytes:
        return {
            "verified": False,
            "status": "MALFORMED",
            "reason": f"Expected manifest hash is not a valid 64-character SHA-256 digest: '{manifest_hash}'.",
            "manifest_hash": manifest_hash,
            "transaction_hash": transaction_hash,
        }

    try:
        on_chain_hash_str = get_anchored_hash(transaction_hash)
    except Exception as err:
        err_str = str(err)
        err_lower = err_str.lower()

        # Differentiate RPC connection / network issues from transaction content errors
        is_rpc_network_error = any(kw in err_lower for kw in [
            "connection", "timeout", "network", "retry", "econnrefused",
            "failed to connect", "http error", "429", "502", "503", "504",
            "rate limit", "socket", "unreachable"
        ])

        if is_rpc_network_error:
            return {
                "verified": False,
                "status": "ERROR",
                "reason": f"Sepolia RPC network error: {err_str}",
                "manifest_hash": manifest_hash,
                "transaction_hash": transaction_hash,
            }
        elif "not found" in err_lower:
            return {
                "verified": False,
                "status": "NOT_FOUND",
                "reason": f"Transaction '{transaction_hash}' not found on Ethereum Sepolia ledger.",
                "manifest_hash": manifest_hash,
                "transaction_hash": transaction_hash,
            }
        else:
            return {
                "verified": False,
                "status": "MALFORMED",
                "reason": f"Malformed on-chain payload: {err_str}",
                "manifest_hash": manifest_hash,
                "transaction_hash": transaction_hash,
            }

    on_chain_bytes = normalize_digest_bytes(on_chain_hash_str)
    if not on_chain_bytes:
        return {
            "verified": False,
            "status": "MALFORMED",
            "reason": f"Retrieved on-chain payload is not a valid 32-byte digest: '{on_chain_hash_str}'.",
            "manifest_hash": manifest_hash,
            "on_chain_hash": on_chain_hash_str,
            "transaction_hash": transaction_hash,
        }

    # Strict byte-level equality comparison
    matches = (expected_bytes == on_chain_bytes)

    if matches:
        return {
            "verified": True,
            "status": "VERIFIED",
            "manifest_hash": expected_bytes.hex(),
            "on_chain_hash": on_chain_bytes.hex(),
            "transaction_hash": transaction_hash,
        }

    # Mismatch detected: determine whether this is an outdated anchor or genuine tamper/mismatch
    is_outdated = False
    outdated_details = []

    if anchored_at and analyzed_at:
        try:
            from datetime import datetime
            t_anchor = datetime.fromisoformat(anchored_at.replace("Z", "+00:00"))
            t_analyzed = datetime.fromisoformat(analyzed_at.replace("Z", "+00:00"))
            if t_analyzed > t_anchor:
                is_outdated = True
                outdated_details.append(
                    f"Evidence was re-analyzed at {analyzed_at} after anchoring at {anchored_at}."
                )
        except Exception:
            pass

    if known_prior_hashes and on_chain_hash_str in known_prior_hashes:
        is_outdated = True
        outdated_details.append(
            "On-chain digest matches a prior manifest version of this evidence."
        )

    if is_outdated:
        reason_msg = (
            f"Outdated Anchor: Sepolia transaction {transaction_hash} anchors previous manifest digest "
            f"({on_chain_bytes.hex()}), which does not match current manifest digest ({expected_bytes.hex()}). "
            + (" ".join(outdated_details))
        )
        return {
            "verified": False,
            "status": "OUTDATED_ANCHOR",
            "reason": reason_msg,
            "manifest_hash": expected_bytes.hex(),
            "on_chain_hash": on_chain_bytes.hex(),
            "transaction_hash": transaction_hash,
            "anchored_at": anchored_at,
            "analyzed_at": analyzed_at,
        }

    # Genuine mismatch
    return {
        "verified": False,
        "status": "TAMPERED",
        "reason": (
            f"Cryptographic Mismatch: Stored Sepolia transaction payload ({on_chain_bytes.hex()}) "
            f"does not match current manifest digest ({expected_bytes.hex()})."
        ),
        "manifest_hash": expected_bytes.hex(),
        "on_chain_hash": on_chain_bytes.hex(),
        "transaction_hash": transaction_hash,
    }
