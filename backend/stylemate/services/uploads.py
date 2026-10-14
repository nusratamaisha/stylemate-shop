"""Pictures customers upload: checking them and keeping them where only the owner can open them.

Two kinds are kept: a reference picture for the tailor, and a photo sent with a Help
page message (for example a wrong size being measured). A reference picture is uploaded
as soon as the customer chooses it, because the shopping bag lives in the browser and
can't hold a file. The upload returns a random name; the order then carries that name.
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


def save_picture(folder: str, mimetype: str, content: bytes) -> str:
    """Save a customer's picture and return its new, random file name."""
    check_picture(mimetype, content)
    name = f"{uuid.uuid4().hex}{PICTURE_TYPES[mimetype]}"  # never the customer's own file name
    Path(folder).mkdir(parents=True, exist_ok=True)
    (Path(folder) / name).write_bytes(content)
    return name


def picture_exists(folder: str, name: str) -> bool:
    return bool(SAVED_NAME.match(name or "")) and (Path(folder) / name).is_file()
