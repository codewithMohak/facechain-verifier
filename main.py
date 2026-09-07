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

    # -------------------------------------------------
    # 1. FACE SCAN / INPUT
    # -------------------------------------------------
    if not os.path.exists(IMAGE_PATH):
        raise FileNotFoundError(f"Image not found: {IMAGE_PATH}")

    print(f"\n[1] Face scan / input: {IMAGE_PATH}")

    face_data = detect_and_crop_face(IMAGE_PATH)

    print(f"[OK] Faces detected: {face_data['face_count']}")
    print(f"[OK] Detection confidence: {face_data['confidence']:.4f}")
    print(f"[OK] Face crop: {face_data['face_crop_path']}")

    image = cv2.imread(IMAGE_PATH)
    if image is None:
        raise ValueError("Unable to load input image.")

    print("\n[2] Encoding face with OpenCV SFace...")
    embedding = encode_face(image, face_data)
    embedding_path = save_embedding(embedding)

    print(f"[OK] Embedding shape: {embedding.shape}")
    print(f"[OK] Embedding saved: {embedding_path}")

    # -------------------------------------------------
    # 2. WEB / SOCIAL-MEDIA SEARCH
    # -------------------------------------------------
    print("\n[3] Preparing image for Google Lens...")
    search_image = prepare_image_for_search(
        IMAGE_PATH,
        "data/search_image_main.jpg",
    )
    print(f"[OK] Search image: {search_image}")

    print("\n[4] Searching Google Lens...")
    lens_results = search_with_google_lens(search_image)
    best_match = extract_best_match(lens_results)

    print("\n[5] Verifying face against public search candidates...")

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
        match_status = "EXACT_IMAGE_MATCH"
        print("[OK] Exact image match found.")
        print(f"[OK] Source: {best_match['source']}")
        print(f"[OK] URL: {best_match['url']}")

    elif best_match["match_type"] == "visual":
        visual_candidates = best_match.get("visual_matches", [])

        if visual_candidates:
            public_face_match = find_matching_public_face(
                embedding,
                visual_candidates,
            )

        if public_face_match and public_face_match["is_match"]:
            match_status = "PUBLIC_FACE_MATCH"
            print("[OK] Same face found in a public candidate.")
            print(
                f"[OK] Face similarity: "
                f"{public_face_match['similarity']:.4f}"
            )
            print(f"[OK] Source: {public_face_match['source']}")
            print(f"[OK] URL: {public_face_match['url']}")
        else:
            match_status = "VISUAL_MATCH_ONLY"
            print("[!] No verified public face match found.")
            if public_face_match:
                print(
                    f"[i] Best face similarity: "
                    f"{public_face_match['similarity']:.4f}"
                )

    else:
        print("[!] No web matches found.")

    # -------------------------------------------------
    # Build the canonical verification record.
    # IMPORTANT: this object is what gets hashed and anchored.
    # The later 'blockchain' section is metadata about that hash
    # and is intentionally not part of the anchored record.
    # -------------------------------------------------
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

    # -------------------------------------------------
    # 3. BLOCKCHAIN UPLOAD
    # -------------------------------------------------
    blockchain_data = {
        "status": "not_configured",
        "hash": None,
        "transaction_hash": None,
        "verification": "NOT_RUN",
    }

    blockchain_enabled = (
        os.getenv("BLOCKCHAIN_ANCHOR_ENABLED", "false").lower()
        == "true"
    )

    if blockchain_enabled:
        from src.blockchain.anchor import anchor_data, get_web3
        from src.blockchain.verify import verify_data

        print("\n[6] Generating SHA-256 fingerprint and anchoring on Sepolia...")
        anchored = anchor_data(verification_data)

        print(f"[OK] SHA-256: {anchored['hash']}")
        print(f"[OK] Transaction hash: {anchored['transaction_hash']}")

        # Wait until the transaction is mined so the screen recording
        # can show a confirmed blockchain record.
        print("[i] Waiting for Sepolia transaction confirmation...")
        web3 = get_web3()
        receipt = web3.eth.wait_for_transaction_receipt(
            anchored["transaction_hash"],
            timeout=300,
            poll_latency=3,
        )

        if receipt["status"] != 1:
            raise RuntimeError("Sepolia transaction failed.")

        print(f"[OK] Transaction confirmed in block: {receipt['blockNumber']}")

        blockchain_data = {
            "status": "anchored",
            **anchored,
            "block_number": receipt["blockNumber"],
            "verification": "PENDING",
        }

        # -------------------------------------------------
        # 4. BLOCKCHAIN VERIFICATION
        # Recalculate the hash from the same canonical data,
        # retrieve the on-chain hash, and compare them.
        # -------------------------------------------------
        print("\n[7] Recalculating hash and verifying against blockchain...")
        is_verified = verify_data(
            verification_data,
            anchored["transaction_hash"],
        )

        if is_verified:
            blockchain_data["verification"] = "VERIFIED"
            print("[OK] Recalculated hash matches on-chain hash.")
            print("========================================")
            print("              VERIFIED")
            print("========================================")
        else:
            blockchain_data["verification"] = "TAMPERED"
            print("[!] Recalculated hash does NOT match on-chain hash.")
            print("========================================")
            print("              TAMPERED")
            print("========================================")
    else:
        print("\n[6] Blockchain anchoring disabled.")
        print("[i] Set BLOCKCHAIN_ANCHOR_ENABLED=true in .env for the full demo.")

    # Add blockchain transaction metadata AFTER verification_data has
    # been hashed. This metadata describes the anchored record.
    verification_data["blockchain"] = blockchain_data

    # -------------------------------------------------
    # Save final metadata
    # -------------------------------------------------
    os.makedirs(os.path.dirname(METADATA_PATH), exist_ok=True)

    with open(
        METADATA_PATH,
        "w",
        encoding="utf-8",
    ) as metadata_file:
        json.dump(
            verification_data,
            metadata_file,
            indent=4,
        )

    print(f"\n[OK] Metadata saved: {METADATA_PATH}")
    print(f"[OK] Public search status: {match_status}")
    print(
        f"[OK] Blockchain status: "
        f"{blockchain_data['verification']}"
    )

    print("\n========================================")
    print("       FACECHAIN END-TO-END COMPLETE")
    print("========================================")


if __name__ == "__main__":
    main()
