from src.blockchain.verify import verify_data


transaction_hash = (
    "0x013bfaf31db5d8349b410d487091de1b119c07bbce7b89a5fd9ea2bffc485341"
)

original_data = {
    "source_url": "https://example.com/post/123",
    "image_reference": "abc123"
}

tampered_data = {
    "source_url": "https://example.com/post/999",
    "image_reference": "abc123"
}


print("=== ORIGINAL DATA ===")

if verify_data(original_data, transaction_hash):
    print("VERIFIED: Data matches blockchain record")
else:
    print("TAMPER DETECTED")


print("\n=== TAMPERED DATA ===")

if verify_data(tampered_data, transaction_hash):
    print("VERIFIED")
else:
    print("TAMPER DETECTED: Data differs from blockchain record")