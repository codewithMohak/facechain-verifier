from src.utils.hashing import generate_hash
from src.blockchain.anchor import anchor_hash, get_web3


data = {
    "source_url": "https://example.com/post/123",
    "image_reference": "abc123"
}

hash_value = generate_hash(data)

print("Generated hash:", hash_value)

print("\nSending transaction to Sepolia...")

transaction_hash = anchor_hash(hash_value)

print("\nTransaction submitted!")
print("Transaction hash:", transaction_hash)

web3 = get_web3()

print("\nWaiting for confirmation...")

receipt = web3.eth.wait_for_transaction_receipt(
    transaction_hash,
    timeout=300,
    poll_latency=5
)

print("\nTransaction confirmed!")
print("Block number:", receipt["blockNumber"])
print("Transaction status:", receipt["status"])