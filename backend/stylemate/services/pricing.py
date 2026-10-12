"""Custom order prices. Calculated here, never by the AI.

The assistant can explain that a dress is customizable, but every number a
customer pays comes from this module.
"""

from dataclasses import dataclass, field

from ..errors import UserInputError
from ..extensions import db
from ..models import CustomizationOption, Product, Tenant
from .sizes import sleeve_lengths, sleeve_word


# Where an order can be delivered. Each shop sets its own charge for each (on its Tenant row).
DELIVERY_AREAS = {"inside_dhaka": "Inside Dhaka", "outside_dhaka": "Outside Dhaka"}

# Body measurements for a made-to-measure piece, in inches. Length is optional: left out, it stays as shown.
REQUIRED_MEASUREMENTS = ["bust", "waist", "hip"]
MEASUREMENT_RANGE = (20, 72)
MADE_TO_MEASURE_SIZE = "Made to measure"  # stored where a ready-made piece has S, M or L

SLEEVE_GROUP = "Sleeves"  # the option group that is compared with a product's `sleeve` value


@dataclass(frozen=True)
class Quote:
    base_price_bdt: int
    extras: list[CustomizationOption] = field(default_factory=list)
    total_bdt: int = 0
    ready_in_days: int | None = None  # None for regular (non-custom) items
    details: str = ""  # for the customer and the tailor, e.g. "Sleeves: Short sleeves; Length: Shorter by 2 inches (50 in)"
    needs_measurements: bool = False  # made to measure: the order takes measurements, not a size

    @property
    def is_custom(self) -> bool:
        return bool(self.extras)

    def to_dict(self) -> dict:
        return {
            "base_price_bdt": self.base_price_bdt,
            "extras": [option.to_dict() for option in self.extras],
            "total_bdt": self.total_bdt,
            "ready_in_days": self.ready_in_days,
            "is_custom": self.is_custom,
            "needs_measurements": self.needs_measurements,
            "details": self.details,
        }


def calculate_quote(product: Product, options: list[CustomizationOption], base_days: int) -> Quote:
    """Price a product with the chosen options. Pure function: no database, easy to test."""
    if options and not product.customizable:
        raise UserInputError(f"{product.name} can't be customized.")

    groups = [option.group for option in options]
    duplicates = {group for group in groups if groups.count(group) > 1}
    if duplicates:
        raise UserInputError(f"Choose only one option for: {', '.join(sorted(duplicates))}.")
    for option in options:
        if already_has(product, option):
            raise UserInputError(f"{product.name} already has {option.label.lower()}.")
    measured = any(option.needs_measurements for option in options)
    if measured and any(option.length_change_inches for option in options):
        # A made-to-measure piece is cut to the exact length the customer gives
        raise UserInputError("With made to measure, give your exact length in your measurements instead of a length change.")

    total = product.price_bdt + sum(option.extra_price_bdt for option in options)
    days = base_days + sum(option.extra_days for option in options) if options else None
    details = "; ".join(_describe(product, option) for option in options)
    return Quote(base_price_bdt=product.price_bdt, extras=list(options),
                 total_bdt=total, ready_in_days=days, details=details, needs_measurements=measured)


def already_has(product: Product, option: CustomizationOption) -> bool:
    """Is this option what the piece is already like? E.g. "Sleeveless" on a sleeveless dress.

    Compares the option's label with the product's `sleeve` value, so the CSV should
    use the same words as the options ("Short", "Full", "Sleeveless").
    """
    return (option.group == SLEEVE_GROUP and bool(product.sleeve)
            and sleeve_word(option.label) == sleeve_word(product.sleeve))


def new_length(product: Product, option: CustomizationOption) -> int | None:
    """The piece's length in inches after this option, or None if it isn't known or doesn't change."""
    if not product.length_inches or not option.length_change_inches:
        return None
    return product.length_inches + option.length_change_inches


def _describe(product: Product, option: CustomizationOption) -> str:
    length = new_length(product, option)
    return f"{option.group}: {option.label}" + (f" ({length} in)" if length else "")



def quote_for(tenant: Tenant, product: Product, option_ids: list[int]) -> Quote:
    """Load the chosen options (only this shop's) and price the product."""
    options = load_options(tenant, option_ids)
    return calculate_quote(product, options, tenant.custom_base_days)


def load_options(tenant: Tenant, option_ids: list[int]) -> list[CustomizationOption]:
    ids = _clean_ids(option_ids)
    if not ids:
        return []
    options = db.session.scalars(
        db.select(CustomizationOption)
        .where(CustomizationOption.tenant_id == tenant.id, CustomizationOption.id.in_(ids))
    ).all()
    if len(options) != len(ids):
        raise UserInputError("One of the chosen options doesn't exist.")
    return sorted(options, key=lambda option: option.position)


def options_for(tenant: Tenant, product: Product) -> list[dict]:
    """The customization menu for one product, grouped for the product page.

    The shop's options are the same for every product, but what makes sense depends
    on the piece: an option it already has is left out, length options say what the
    new length would be when the product's length is known, and sleeve options say
    how long that sleeve is when the size guide has it.
    """
    sleeves = sleeve_lengths(tenant)
    options = db.session.scalars(
        db.select(CustomizationOption)
        .where(CustomizationOption.tenant_id == tenant.id)
        .order_by(CustomizationOption.position)
    ).all()
    groups: dict[str, dict] = {}
    for option in options:
        group = groups.setdefault(option.group, {"group": option.group, "current": "", "options": []})
        if option.length_change_inches and product.length_inches:
            group["current"] = f"{product.length_inches} in"
        if option.group == SLEEVE_GROUP:
            group["current"] = product.sleeve
        if already_has(product, option):
            continue
        group["options"].append({
            **option.to_dict(),
            "new_length_inches": new_length(product, option),
            "sleeve_length_inches": sleeves.get(sleeve_word(option.label)) if option.group == SLEEVE_GROUP else None,
        })
    return [group for group in groups.values() if group["options"]]


def _clean_ids(option_ids) -> list[int]:
    if option_ids is None:
        return []
    if not isinstance(option_ids, list):
        raise UserInputError("option_ids must be a list.")
    try:
        ids = [int(option_id) for option_id in option_ids]
    except (TypeError, ValueError):
        raise UserInputError("option_ids must be numbers.") from None
    if len(set(ids)) != len(ids):
        raise UserInputError("The same option was chosen twice.")
    return ids


def shipping_options(tenant: Tenant) -> list[dict]:
    """The delivery areas and what the shop charges for each, for the checkout page."""
    charges = {"inside_dhaka": tenant.shipping_inside_dhaka_bdt, "outside_dhaka": tenant.shipping_outside_dhaka_bdt}
    return [{"area": area, "label": label, "charge_bdt": charges[area]} for area, label in DELIVERY_AREAS.items()]


def shipping_charge(tenant: Tenant, area) -> int:
    """The delivery charge for one order. It is per order, not per piece."""
    for option in shipping_options(tenant):
        if option["area"] == area:
            return option["charge_bdt"]
    raise UserInputError("Please choose whether we deliver inside or outside Dhaka.")


def clean_measurements(measurements, *, require_all: bool = True) -> dict[str, int]:
    """Check the measurements for a made-to-measure piece. Returns whole inches, e.g. {"bust": 38, "waist": 32}.

    With require_all=False, missing ones are simply left out (used when the stylist chat
    passes on what the customer has said so far).
    """
    measurements = measurements if isinstance(measurements, dict) else {}
    low, high = MEASUREMENT_RANGE
    clean = {}
    for name in [*REQUIRED_MEASUREMENTS, "length"]:
        value = measurements.get(name)
        if value in (None, ""):
            if require_all and name in REQUIRED_MEASUREMENTS:
                raise UserInputError(f"Please give your {name} measurement in inches.")
            continue
        try:
            inches = round(float(value))
        except (TypeError, ValueError):
            raise UserInputError(f"Your {name} measurement must be a number of inches.") from None
        if not low <= inches <= high:
            raise UserInputError(f"Your {name} measurement should be between {low} and {high} inches.")
        clean[name] = inches
    return clean


def measurements_text(measurements: dict[str, int]) -> str:
    """For the tailor: "bust 38 in, waist 32 in, hip 40 in, length 36 in"."""
    return ", ".join(f"{name} {inches} in" for name, inches in measurements.items())
