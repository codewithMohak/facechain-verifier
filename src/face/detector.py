import os
import cv2

def detect_and_crop_face(image_path, output_dir="data"):
    if not os.path.exists(image_path):
        raise FileNotFoundError(
            f"Input image not found {image_path}"
        )

    image = cv2.imread(image_path)

    if image is None:
        raise ValueError(
            f"Unable to load image:{image_path}"
        )

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"

    face_cascade = cv2.CascadeClassifier(cascade_path)

    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(50, 50)
    )

    if len(faces) == 0:
        raise ValueError("No face detected in the image.")

    largest_face = max(
        faces,
        key=lambda rectangle: rectangle[2] * rectangle[3]
    )

    x, y, width, height = largest_face

    face_crop = image[
        y:y + height,
        x:x + width
    ]

    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(
        output_dir,
        "face_crop.jpg"
    )

    success = cv2.imwrite(
        output_path,
        face_crop
    )

    if not success:
        raise IOError(
            "Failed to save cropped face."
        )

    return {
        "face_detected": True,
        "face_count": len(faces),
        "bounding_box": {
            "x": int(x),
            "y": int(y),
            "width": int(width),
            "height": int(height)
        },
        "face_crop_path": output_path,
        "image_width": image.shape[1],
        "image_height": image.shape[0]
        }