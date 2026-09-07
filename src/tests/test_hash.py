from src.utils.hashing import generate_hash

data = {
    "source_url" : "https://example.com/post/123",
    "image_reference": "abc123"
}

hash_value = generate_hash(data)

print("original data:", data)
print("hash value:", hash_value)
print("hash length:", len(hash_value))
