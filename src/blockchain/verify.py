from src.blockchain.anchor import get_web3
from src.utils.hashing import generate_hash

def get_anchored_hash(transaction_hash: str) -> str:
    """
    Retrieve the FaceChain hash stored in a transaction.
    """
    web3 = get_web3()

    transaction = web3.eth.get_transaction(
        transaction_hash
    )
    # Transaction i/p data is returned as bytes
    payload = transaction["input"]
    #bytes back to text
    decoded_payload = web3.to_text(payload)
    # print("On-chain payload:", decoded_payload)

    prefix = "FACECHAIN:v1:"

    if not decoded_payload.startswith(prefix):
        raise ValueError("The transaction does not contain a valid FaceChain hash.")

    return decoded_payload[len(prefix):]
def verify_data(data: dict, transaction_hash: str) -> bool:
    """
    Hash current data and compare it with the blockchain record.
    """

    current_hash = generate_hash(data)

    anchored_hash = get_anchored_hash(transaction_hash)

    return current_hash == anchored_hash