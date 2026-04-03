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
