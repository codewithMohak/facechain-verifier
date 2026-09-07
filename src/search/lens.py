import os
import requests

from PIL import Image
from dotenv import load_dotenv


load_dotenv()


IMAGE_API_URL = "https://serpapi.com/image"
SEARCH_API_URL = "https://serpapi.com/search"


def prepare_image_for_search(
    image_path,
    output_path="data/search_image.jpg"
):
    """
    Resize and compress an image so it stays
    below SerpApi's upload limit.
    """

    if not os.path.exists(image_path):
        raise FileNotFoundError(
            f"Image not found: {image_path}"
        )

    image = Image.open(image_path)

    if image.mode != "RGB":
        image = image.convert("RGB")

    max_dimension = 1200

    image.thumbnail(
        (max_dimension, max_dimension)
    )

    os.makedirs(
        os.path.dirname(output_path) or ".",
        exist_ok=True
    )

    quality = 75

    while quality >= 30:

        image.save(
            output_path,
            "JPEG",
            quality=quality,
            optimize=True
        )

        file_size_kb = (
            os.path.getsize(output_path)
            / 1024
        )

        if file_size_kb <= 490:

            print(
                f"Search image size: "
                f"{file_size_kb:.2f} KB"
            )

            return output_path

        quality -= 5

    raise ValueError(
        "Unable to compress image below 500 KB."
    )


def search_with_google_lens(
    image_path
):
    """
    Upload an image to SerpApi and perform
    a Google Lens search.
    """

    api_key = os.getenv(
        "SERPAPI_KEY"
    )

    if not api_key:
        raise ValueError(
            "SERPAPI_KEY is missing from .env"
        )

    if not os.path.exists(image_path):
        raise FileNotFoundError(
            f"Image not found: {image_path}"
        )

    print(
        "Uploading image to SerpApi..."
    )

    with open(
        image_path,
        "rb"
    ) as image_file:

        response = requests.post(
            IMAGE_API_URL,
            data={
                "api_key": api_key
            },
            files={
                "image": image_file
            },
            timeout=60
        )

    if not response.ok:

        print(
            "SerpApi upload response:"
        )

        print(
            response.text
        )

    response.raise_for_status()

    upload_result = (
        response.json()
    )

    if "error" in upload_result:

        raise RuntimeError(
            upload_result["error"]
        )

    image_id = upload_result.get(
        "image_id"
    )

    if not image_id:

        raise RuntimeError(
            "SerpApi did not return an image_id."
        )

    print(
        "Image uploaded successfully."
    )

    print(
        f"Image ID: {image_id}"
    )

    print(
        "Searching Google Lens..."
    )

    search_response = requests.get(
        SEARCH_API_URL,
        params={
            "engine": "google_lens",
            "image_id": image_id,
            "api_key": api_key,
            "hl": "en",
            "type": "all"
        },
        timeout=60
    )

    if not search_response.ok:

        print(
            "Google Lens response:"
        )

        print(
            search_response.text
        )

    search_response.raise_for_status()

    results = search_response.json()

    if "error" in results:

        # Lens sometimes returns an error
        # when no indexed results exist.
        print(
            f"Google Lens returned: "
            f"{results['error']}"
        )

        return {
            "exact_matches": [],
            "visual_matches": [],
            "search_error": results["error"]
        }

    print(
        "Google Lens search completed."
    )

    print(
        f"Exact matches: "
        f"{len(results.get('exact_matches', []))}"
    )

    print(
        f"Visual matches: "
        f"{len(results.get('visual_matches', []))}"
    )

    return results


def extract_best_match(results):
    """
    Extract the strongest available web match.

    Exact matches are treated as strong evidence.
    Visual matches are returned only as supporting
    evidence and are NOT treated as exact identity matches.
    """

    exact_matches = results.get(
        "exact_matches",
        []
    )

    # ----------------------------------------
    # Priority 1: Exact match
    # ----------------------------------------

    for match in exact_matches:

        link = match.get(
            "link"
        )

        if link:

            return {
                "match_type": "exact",
                "verification_level": "strong",
                "title": match.get(
                    "title",
                    "Unknown"
                ),
                "url": link,
                "source": match.get(
                    "source",
                    "Unknown"
                ),
                "thumbnail": match.get(
                    "thumbnail"
                )
            }


    # ----------------------------------------
    # Priority 2: Visual matches
    # ----------------------------------------

    visual_matches = results.get(
        "visual_matches",
        []
    )

    visual_results = []

    for match in visual_matches:

        link = match.get(
            "link"
        )

        if not link:
            continue

        visual_results.append(
            {
                "title": match.get(
                    "title",
                    "Unknown"
                ),
                "url": link,
                "source": match.get(
                    "source",
                    "Unknown"
                ),
                "thumbnail": match.get(
                    "thumbnail"
                ),
                "image": match.get(
                    "image"
                )
            }
        )

    if visual_results:

        return {
            "match_type": "visual",
            "verification_level": "weak",
            "title": visual_results[0][
                "title"
            ],
            "url": visual_results[0][
                "url"
            ],
            "source": visual_results[0][
                "source"
            ],
            "thumbnail": visual_results[0][
                "thumbnail"
            ],
            "visual_match_count": len(
                visual_results
            ),
            "visual_matches": visual_results[:5]
        }


    # ----------------------------------------
    # No results
    # ----------------------------------------

    return {
        "match_type": "none",
        "verification_level": "none",
        "title": None,
        "url": None,
        "source": None,
        "thumbnail": None,
        "visual_match_count": 0,
        "visual_matches": []
    }