from src.blockchain.anchor import get_web3
from src.utils.hashing import generate_hash

def get_anchored_hash(transaction_hash: str) -> str:
    """
    Retrieve the FaceChain hash stored in a Sepolia transaction.
    Extracts and normalizes the 64-character SHA-256 hex digest.
    Raises ValueError on malformed payloads or missing transactions.
    """
    web3 = get_web3()

    transaction = web3.eth.get_transaction(transaction_hash)
    if not transaction:
        raise ValueError(f"Transaction '{transaction_hash}' returned empty response.")

    payload = transaction.get("input")
    if not payload:
        raise ValueError("Transaction input data is empty.")

    try:
        decoded_payload = web3.to_text(payload)
    except Exception as e:
        raise ValueError(f"Transaction input data cannot be decoded as UTF-8 text: {e}")

    prefix = "FACECHAIN:v1:"
    if not decoded_payload.startswith(prefix):
        raise ValueError("The transaction does not contain a valid FaceChain hash prefix ('FACECHAIN:v1:').")

    raw_hash = decoded_payload[len(prefix):].strip().rstrip("\x00")
    cleaned_hash = raw_hash.lower().removeprefix("0x")

    if len(cleaned_hash) != 64 or not all(c in "0123456789abcdef" for c in cleaned_hash):
        raise ValueError(f"On-chain payload does not contain a valid 64-character SHA-256 hex digest: '{raw_hash}'.")

    return cleaned_hash


def verify_data(data: dict, transaction_hash: str) -> bool:
    """
    Hash current data and compare it with the blockchain record using normalized byte values.
    """
    current_hash = generate_hash(data).strip().lower().removeprefix("0x")
    anchored_hash = get_anchored_hash(transaction_hash).strip().lower().removeprefix("0x")

    return current_hash == anchored_hash