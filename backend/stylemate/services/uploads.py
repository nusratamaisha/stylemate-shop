"""Pictures customers upload: checking them, and keeping reference pictures for the tailor.

A reference picture is uploaded as soon as the customer chooses it, because the
shopping bag lives in the browser and can't hold a file. The upload returns a random
name; the order then carries that name. Only the shop's owner can open the picture.
"""

import re
import uuid
from pathlib import Path

from ..errors import UserInputError

MAX_PICTURE_BYTES = 4 * 1024 * 1024
PICTURE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
SAVED_NAME = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp)$")  # the only names this module ever writes or reads


def check_picture(mimetype: str, content: bytes) -> None:
    if mimetype not in PICTURE_TYPES:
        raise UserInputError("Please upload a JPG, PNG or WebP photo.")
    if not content:
        raise UserInputError("That photo is empty. Please choose another one.")
    if len(content) > MAX_PICTURE_BYTES:
        raise UserInputError("That photo is too large (4 MB maximum).")


def save_reference_picture(folder: str, mimetype: str, content: bytes) -> str:
    """Save a picture for the tailor and return its new, random file name."""
    check_picture(mimetype, content)
    name = f"{uuid.uuid4().hex}{PICTURE_TYPES[mimetype]}"  # never the customer's own file name
    Path(folder).mkdir(parents=True, exist_ok=True)
    (Path(folder) / name).write_bytes(content)
    return name


def reference_picture_exists(folder: str, name: str) -> bool:
    return bool(SAVED_NAME.match(name or "")) and (Path(folder) / name).is_file()
