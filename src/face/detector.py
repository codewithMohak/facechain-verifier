import os
import cv2


MODEL_PATH = (
    "models/face_detection_yunet_2023mar.onnx"
)


def detect_faces(image_path):
    """
    Load an image and detect faces using YuNet.
    """

    if not os.path.exists(image_path):
        raise FileNotFoundError(
            f"Image not found: {image_path}"
        )

    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"YuNet model not found: {MODEL_PATH}"
        )

    image = cv2.imread(
        image_path
    )

    if image is None:
        raise ValueError(
            f"Unable to load image: {image_path}"
        )

    height, width = image.shape[:2]

    detector = cv2.FaceDetectorYN.create(
        MODEL_PATH,
        "",
        (width, height),
        0.6,
        0.3,
        5000
    )

    _, faces = detector.detect(
        image
    )

    if faces is None or len(faces) == 0:
        raise ValueError(
            "No face detected in the image."
        )

    return image, faces


def detect_and_crop_face(
    image_path,
    output_dir="data"
):
    """
    Detect faces using YuNet, select the largest
    face, add padding around it, and save the crop.
    """

    image, faces = detect_faces(
        image_path
    )

    # ----------------------------------------
    # Select the largest detected face
    # ----------------------------------------

    largest_face = max(
        faces,
        key=lambda face:
        face[2] * face[3]
    )

    # ----------------------------------------
    # Original YuNet bounding box
    # ----------------------------------------

    original_x = int(
        largest_face[0]
    )

    original_y = int(
        largest_face[1]
    )

    original_width = int(
        largest_face[2]
    )

    original_height = int(
        largest_face[3]
    )

    image_height, image_width = (
        image.shape[:2]
    )

    # ----------------------------------------
    # Add padding
    # ----------------------------------------

    padding_x = int(
        original_width * 0.25
    )

    padding_y = int(
        original_height * 0.30
    )

    x1 = max(
        0,
        original_x - padding_x
    )

    y1 = max(
        0,
        original_y - padding_y
    )

    x2 = min(
        image_width,
        original_x +
        original_width +
        padding_x
    )

    y2 = min(
        image_height,
        original_y +
        original_height +
        padding_y
    )

    crop_width = x2 - x1
    crop_height = y2 - y1

    if crop_width <= 0 or crop_height <= 0:
        raise ValueError(
            "Invalid face crop dimensions."
        )

    # ----------------------------------------
    # Crop face
    # ----------------------------------------

    face_crop = image[
        y1:y2,
        x1:x2
    ]

    # ----------------------------------------
    # Create output directory
    # ----------------------------------------

    os.makedirs(
        output_dir,
        exist_ok=True
    )

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
            "Failed to save face crop."
        )

    # ----------------------------------------
    # Return metadata
    # ----------------------------------------

    return {
        "face_detected": True,

        "face_count": len(
            faces
        ),

        "confidence": float(
            largest_face[14]
        ),

        "bounding_box": {
            "x": original_x,
            "y": original_y,
            "width": original_width,
            "height": original_height
        },

        "crop_box": {
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "width": crop_width,
            "height": crop_height
        },

        "landmarks": {
            "right_eye": [
                float(largest_face[4]),
                float(largest_face[5])
            ],

            "left_eye": [
                float(largest_face[6]),
                float(largest_face[7])
            ],

            "nose": [
                float(largest_face[8]),
                float(largest_face[9])
            ],

            "right_mouth": [
                float(largest_face[10]),
                float(largest_face[11])
            ],

            "left_mouth": [
                float(largest_face[12]),
                float(largest_face[13])
            ]
        },

        "face_crop_path": output_path,

        "image_width": image_width,

        "image_height": image_height
    }