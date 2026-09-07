from src.face.detector import detect_and_crop_face


result = detect_and_crop_face(
    "data/input.jpg"
)

print("\nFace Detection Result")
print("---------------------")

print(f"Face detected: {result['face_detected']}")
print(f"Number of faces: {result['face_count']}")
print(f"Bounding box: {result['bounding_box']}")
print(f"Crop saved at: {result['face_crop_path']}")
print(
    f"Original image size: "
    f"{result['image_width']}x{result['image_height']}"
)