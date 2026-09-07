import json
import os

import cv2
from dotenv import load_dotenv

from src.face.detector import detect_and_crop_face
from src.face.encoder import encode_face, save_embedding
from src.search.face_matcher import find_matching_public_face
from src.search.lens import (
    extract_best_match,
    prepare_image_for_search,
    search_with_google_lens,
)


IMAGE_PATH = "data/IMG-20260324-WA0013.jpg"
METADATA_PATH = "data/verification_metadata.json"

load_dotenv()


def main():
    print("\n========================================")
    print("        FACECHAIN VERIFIER")
    print("========================================")

    if not os.path.exists(IMAGE_PATH):
        raise FileNotFoundError(f"Image not found: {IMAGE_PATH}")

    print(f"\n[1] Input: {IMAGE_PATH}")
    face_data = detect_and_crop_face(IMAGE_PATH)
    print(f"[2] Faces detected: {face_data['face_count']}")

    image = cv2.imread(IMAGE_PATH)
    if image is None:
        raise ValueError("Unable to load input image.")

    embedding = encode_face(image, face_data)
    embedding_path = save_embedding(embedding)
    print(f"[3] Embedding saved: {embedding_path}")

    search_image = prepare_image_for_search(
        IMAGE_PATH,
        "data/search_image_main.jpg"
    )
    lens_results = search_with_google_lens(search_image)
    best_match = extract_best_match(lens_results)

    print("\n[4] Verifying face against public search candidates...")
    public_face_match = None
    match_status = "NO_MATCH"

    if best_match["match_type"] == "exact":
        public_face_match = {
            "public_face_found": True,
            "verification_method": "exact_image_match",
            "similarity": None,
            "title": best_match["title"],
            "source": best_match["source"],
            "url": best_match["url"],
        }
        match_status = "EXACT_MATCH"
        print("[OK] Exact image match found.")
    elif best_match["match_type"] == "visual":
        visual_candidates = best_match.get("visual_matches", [])
        if visual_candidates:
            public_face_match = find_matching_public_face(
                embedding,
                visual_candidates
            )

        if public_face_match and public_face_match["is_match"]:
            match_status = "PUBLIC_FACE_MATCH"
            print("[OK] Same face found in public candidate.")
        else:
            match_status = "VISUAL_MATCH_ONLY"
            print("[!] No verified public face match found.")
    else:
        print("[!] No web matches found.")

    verification_data = {
        "version": "1.0",
        "input_image": os.path.basename(IMAGE_PATH),
        "face": {
            "detected": face_data["face_detected"],
            "face_count": face_data["face_count"],
            "confidence": face_data["confidence"],
            "bounding_box": face_data["bounding_box"],
            "landmarks": face_data["landmarks"],
        },
        "face_embedding": {
            "model": "OpenCV SFace",
            "dimensions": int(embedding.shape[-1]),
            "embedding_file": embedding_path,
        },
        "web_search": {
            "status": match_status,
            "match": best_match,
            "public_face_match": public_face_match,
        },
    }

    blockchain_data = {
        "status": "not_configured",
        "hash": None,
        "transaction_hash": None,
    }

    blockchain_enabled = os.getenv(
        "BLOCKCHAIN_ANCHOR_ENABLED",
        "false"
    ).lower() == "true"

    if blockchain_enabled:
        from src.blockchain.anchor import anchor_data

        print("\n[5] Anchoring verification on Sepolia...")
        anchored = anchor_data(verification_data)
        blockchain_data = {
            "status": "anchored",
            **anchored,
        }
        print(
            f"[OK] Blockchain transaction: "
            f"{anchored['transaction_hash']}"
        )
    else:
        print("\n[5] Blockchain anchoring disabled.")

    verification_data["blockchain"] = blockchain_data

    os.makedirs(os.path.dirname(METADATA_PATH), exist_ok=True)
    with open(METADATA_PATH, "w", encoding="utf-8") as metadata_file:
        json.dump(verification_data, metadata_file, indent=4)

    print(f"[6] Metadata saved: {METADATA_PATH}")
    print(f"[OK] Verification status: {match_status}")


if __name__ == "__main__":
    main()