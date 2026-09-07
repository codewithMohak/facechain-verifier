from src.blockchain.anchor import anchor_data, get_web3
from src.blockchain.verify import verify_data


data = {
    "source_url": "https://example.com/post/123",
    "image_reference": "abc123"
}


print("=== ANCHORING ===")

result = anchor_data(data)

print("Data hash:", result["hash"])
print("Transaction hash:", result["transaction_hash"])


print("\nWaiting for confirmation...")

web3 = get_web3()

receipt = web3.eth.wait_for_transaction_receipt(
    result["transaction_hash"],
    timeout=300,
    poll_latency=5
)

print("Confirmed!")
print("Block:", receipt["blockNumber"])


print("\n=== VERIFYING ===")

is_verified = verify_data(
    data,
    result["transaction_hash"]
)

if is_verified:
    print("VERIFIED: Data matches blockchain record")
else:
    print("TAMPERED: Data does not match blockchain record")

print("\n=== TAMPERING TEST ===")

tampered_data = {
    "source_url": "https://example.com/post/999",
    "image_reference": "abc123"
}

is_tampered_verified = verify_data(
    tampered_data,
    result["transaction_hash"]
)

if is_tampered_verified:
    print("VERIFIED")
else:
    print("TAMPER DETECTED")