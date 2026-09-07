from src.utils.hashing import generate_hash
from src.blockchain.verify import get_anchored_hash


transaction_hash = "0x308fb3998f7a1354dc7078db737339dd4d9efc82388811efc5f8d678ae258f1f"


original_data = {
    "source_url": "https://example.com/post/123",
    "image_reference": "abc123"
}


current_hash = generate_hash(original_data)

print("Current hash:")
print(current_hash)


print("\nRetrieving hash from blockchain...")

anchored_hash = get_anchored_hash(transaction_hash)

print("\nAnchored hash:")
print(anchored_hash)


print("\nVerification:")

if current_hash == anchored_hash:
    print("VERIFIED: Data matches the blockchain record")
else:
    print("TAMPERED: Data does not match the blockchain record")