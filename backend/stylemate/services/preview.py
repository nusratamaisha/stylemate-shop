"""Image preview: a generated picture of a dress with the customer's changes.

Two uses, one flow:
- "show me this dress with short sleeves": the chosen options and a typed wish;
- "show me wearing it": the same, plus the customer's own photo.

The picture is only a preview. It never sets a price: chosen options are checked
and described by pricing.py, the same code that prices the order.
"""

from dataclasses import dataclass
from pathlib import Path

from ..clients import ReferenceImage
from ..errors import UserInputError
from ..models import Product, Tenant
from . import pricing
from .uploads import check_picture

MAX_WISH_LENGTH = 200
IMAGE_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


@dataclass(frozen=True)
class Preview:
    image_url: str
    details: str  # the priced options shown in the picture, e.g. "Sleeves: Short sleeves"
    wish: str
    on_customer: bool

    def to_dict(self) -> dict:
        return self.__dict__.copy()


class PreviewService:
    def __init__(self, maira, images_dir: str):
        self._maira = maira  # anything with a generate_image() method: the real client or a test fake
        self._images_dir = Path(images_dir)

    def create(self, tenant: Tenant, product: Product, *, visitor_id: str, colour: str = "",
               option_ids: list | None = None, wish: str = "",
               photo: ReferenceImage | None = None, before_drawing=None) -> Preview:
        if not tenant.maira_image_profile_id:
            raise UserInputError("Picture previews aren't available for this shop yet.")

        wish = " ".join((wish or "").split())
        if len(wish) > MAX_WISH_LENGTH:
            raise UserInputError(f"Please keep your idea under {MAX_WISH_LENGTH} characters.")
        if wish and not product.customizable:
            raise UserInputError(f"{product.name} can't be customized.")
        colour = _check_colour(product, colour)
        if photo:
            check_picture(photo.mimetype, photo.content)

        # DRY: pricing.py already checks the options (this shop's, one per group, product is customizable)
        quote = pricing.quote_for(tenant, product, option_ids or [])
        if not (quote.is_custom or wish or photo):
            raise UserInputError("Choose a change, describe an idea, or add your photo first.")

        # The customer's photo goes first so the prompt can point to it by position.
        references = [image for image in (photo, self._product_photo(product)) if image]
        prompt = build_prompt(product, colour, quote.details, wish,
                              on_customer=photo is not None,
                              has_dress_photo=len(references) > (1 if photo else 0))
        if before_drawing:
            before_drawing()  # the daily limit: a refused request never reaches the paid call
        image = self._maira.generate_image(
            user_id=visitor_id,
            prompt=prompt,
            profile_id=tenant.maira_image_profile_id,
            reference_images=references,
        )
        return Preview(image_url=image.url, details=quote.details, wish=wish, on_customer=photo is not None)

    def _product_photo(self, product: Product) -> ReferenceImage | None:
        """The shop's real photo of the dress, if one has been added, to keep the picture true to it."""
        if not product.image:
            return None
        path = self._images_dir / Path(product.image).name  # .name: never read outside the images folder
        mimetype = IMAGE_TYPES.get(path.suffix.lower())
        if not mimetype or not path.is_file():
            return None
        return ReferenceImage(path.name, path.read_bytes(), mimetype)


def build_prompt(product: Product, colour: str, details: str, wish: str, *,
                 on_customer: bool, has_dress_photo: bool) -> str:
    """The text sent to the image model. Pure function: no database, easy to test."""
    lines = [
        f"A realistic full-length fashion photo of a model wearing this piece: {product.name} ({product.category}).",
        f"Colour: {colour}. Fabric: {product.fabric}." if product.fabric else f"Colour: {colour}.",
        product.description,
        f"As sold, it is {product.length_inches} inches long from shoulder to hem." if product.length_inches else "",
        f"As sold, its sleeves are: {product.sleeve}." if product.sleeve else "",
    ]
    if on_customer:
        lines.append("The first reference image is the customer. Show that same person wearing the piece. "
                     "Keep their face, hair, skin tone and body shape exactly as they are.")
    if has_dress_photo:
        lines.append(f"The {'second' if on_customer else 'first'} reference image is the real piece. "
                     "Keep its design and pattern, apart from the changes below.")
    if details:
        lines.append(f"Changes to make: {details}.")
    if wish:
        lines.append(f"The customer also asks: {wish}")
    lines.append("Modest styling, plain light studio background, no text, no logos.")
    return "\n".join(line for line in lines if line)


def _check_colour(product: Product, colour: str) -> str:
    colours = product.colour_list
    if not colour:
        return colours[0] if colours else ""
    if colour not in colours:
        raise UserInputError(f"{product.name} doesn't come in {colour}.")
    return colour
