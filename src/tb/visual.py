"""Visual perceptual hashing using imagehash (pHash).

PoC stub — computes pHash for frames but has no reference database to compare against.
Used as a fallback when audio fingerprinting fails or audio is absent.

imagehash usage (confirmed):
  - Input to imagehash.phash() MUST be a PIL Image object, not a file path string.
  - Hamming distance: h1 - h2 operator returns int 0–64.
  - Thresholds: <=5 near-duplicate, <=10 likely match.
"""

from __future__ import annotations

from pathlib import Path

import imagehash
from PIL import Image

from tb.models import Segment, SegmentResult

NEAR_DUPLICATE_THRESHOLD: int = 5   # Hamming distance <= 5
LIKELY_MATCH_THRESHOLD: int = 10    # Hamming distance <= 10


def compute_phash(image_path: Path) -> str:
    """Compute the perceptual hash (pHash) of an image file.

    Opens the image as a PIL Image (required by imagehash.phash),
    computes the hash, and returns it as a hex string.

    Args:
        image_path: Path to the image file (PNG, JPEG, etc.).

    Returns:
        pHash as a hex string (e.g., "f8f0e0c0808080c0").

    Raises:
        FileNotFoundError: If the image file does not exist.
        PIL.UnidentifiedImageError: If the file cannot be opened as an image.
    """
    img = Image.open(str(image_path))
    h = imagehash.phash(img)
    return str(h)


def compare_phash(h1: str, h2: str) -> int:
    """Compare two pHash hex strings and return the Hamming distance.

    Uses imagehash's subtraction operator: hash1 - hash2 returns int 0–64.

    Distance interpretation:
      0           = identical images
      1–5 (<=5)   = near-duplicate (NEAR_DUPLICATE_THRESHOLD)
      6–10 (<=10) = likely match (LIKELY_MATCH_THRESHOLD)
      >10         = probably different images

    Args:
        h1: First pHash hex string (from compute_phash).
        h2: Second pHash hex string (from compute_phash).

    Returns:
        Hamming distance as an integer in range [0, 64].
    """
    ih1 = imagehash.hex_to_hash(h1)
    ih2 = imagehash.hex_to_hash(h2)
    return int(ih1 - ih2)


def match_frame(
    frame_path: Path,
    reference_db: dict[str, str],
    segment: Segment,
) -> SegmentResult:
    """Compare a frame's pHash against a reference database.

    Computes the pHash of the frame at frame_path and finds the closest match
    in reference_db using Hamming distance. Returns a SegmentResult with
    method="visual" if the best distance is within LIKELY_MATCH_THRESHOLD (10),
    or method="no_match" if no close match is found or the database is empty.

    Confidence is computed as ``1.0 - distance / 64``.

    Args:
        frame_path: Path to the keyframe image (PNG, JPEG, etc.).
        reference_db: Mapping of reference ID → pHash hex string.
        segment: The Segment this frame was extracted from.

    Returns:
        SegmentResult with method, visual_hash, and confidence populated.
    """
    result = SegmentResult(segment=segment, fingerprint=None)
    query_hash = compute_phash(frame_path)
    result.visual_hash = query_hash

    if not reference_db:
        return result

    best_id: str | None = None
    best_distance = 65  # larger than max Hamming distance of 64

    for ref_id, ref_hash in reference_db.items():
        distance = compare_phash(query_hash, ref_hash)
        if distance < best_distance:
            best_distance = distance
            best_id = ref_id

    if best_id is not None and best_distance <= LIKELY_MATCH_THRESHOLD:
        result.method = "visual"
        result.source = best_id
        result.confidence = 1.0 - best_distance / 64
    else:
        result.method = "no_match"

    return result
