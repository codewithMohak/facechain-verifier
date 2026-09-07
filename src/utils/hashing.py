import hashlib
import json

def generate_hash(data: dict) -> str:
    canonical_data = json.dumps(
        data,
        sort_keys = True,
        separators=(",", ":")
    )
    return hashlib.sha256(
        canonical_data.encode("utf-8")
    ).hexdigest()