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
# The body measurements a made-to-measure piece takes: name -> (words for the tailor, lowest, highest, required).
# Only the bust is needed for every piece; waist, sleeve length and length depend on the piece.
MEASUREMENTS = {
    "bust": ("bust", 20, 72, True),
    "waist": ("waist", 20, 72, False),
    "sleeve_length": ("sleeve length", 0, 25, False),
    "length": ("length", 20, 58, False),
}
REQUIRED_MEASUREMENTS = [name for name, (_, _, _, required) in MEASUREMENTS.items() if required]
MADE_TO_MEASURE_SIZE = "Made to measure"  # stored where a ready-made piece has S, M or L

SLEEVE_GROUP = "Sleeves"  # the option group that is compared with a product's `sleeve` value


@dataclass(frozen=True)
class Quote:
    base_price_bdt: int
    extras: list[CustomizationOption] = field(default_factory=list)
    total_bdt: int = 0
    ready_in_days: int | None = None  # None for regular (non-custom) items
    details: str = ""  # for the customer and the tailor, e.g. "Sleeves: Short sleeves; Length: Shorter by 2 inches (50 in)"
    descriptions: list[str] = field(default_factory=list)  # the same wording, one per extra, for the price box
    needs_measurements: bool = False  # made to measure: the order takes measurements, not a size

    @property
    def is_custom(self) -> bool:
        return bool(self.extras)

    def to_dict(self) -> dict:
        return {
            "base_price_bdt": self.base_price_bdt,
            "extras": [{**option.to_dict(), "description": description}
                       for option, description in zip(self.extras, self.descriptions)],
            "total_bdt": self.total_bdt,
            "ready_in_days": self.ready_in_days,
            "is_custom": self.is_custom,
            "needs_measurements": self.needs_measurements,
            "details": self.details,
        }


def calculate_quote(product: Product, options: list[CustomizationOption], base_days: int,
                    measurements: dict[str, int] | None = None) -> Quote:
    """Price a product with the chosen options. Pure function: no database, easy to test.

    `measurements` is given when the options were worked out from the customer's numbers
    (measured_options()); the details then say what each piece is cut to.
    """
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
    if measured and measurements is None and any(option.length_change_inches for option in options):
        # A made-to-measure piece is cut to the exact length the customer gives
        raise UserInputError("With made to measure, give your exact length in your measurements instead of a length change.")

    total = product.price_bdt + sum(option.extra_price_bdt for option in options)
    days = base_days + sum(option.extra_days for option in options) if options else None
    descriptions = [_describe(product, option, measurements or {}) for option in options]
    return Quote(base_price_bdt=product.price_bdt, extras=list(options), total_bdt=total, ready_in_days=days,
                 details="; ".join(descriptions), descriptions=descriptions, needs_measurements=measured)


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


def _describe(product: Product, option: CustomizationOption, measurements: dict[str, int]) -> str:
    # Worked out from the customer's numbers: name the change only; the exact inches are in "Measurements: ..."
    if option.length_change_inches and "length" in measurements:
        longer = "longer" if option.length_change_inches > 0 else "shorter"
        return f"{option.group}: {longer} than shown"
    if option.group == SLEEVE_GROUP and "sleeve_length" in measurements:
        return f"{option.group}: {option.label}"
    length = new_length(product, option)
    return f"{option.group}: {option.label}" + (f" ({length} in)" if length else "")



def quote_for(tenant: Tenant, product: Product, option_ids: list[int], measurements=None) -> Quote:
    """Load the chosen options (only this shop's) and price the product.

    With measurements, the piece is made to measure and the customer doesn't pick sleeve or
    length changes: measured_options() works them out from the numbers. Any sleeve, length or
    fit option sent as well is replaced by what the numbers say (a sleeve chosen in the chat,
    "Sleeveless" for example, stays when no sleeve length is given).
    """
    options = load_options(tenant, option_ids)
    numbers = clean_measurements(measurements, require_all=False) if measurements else {}
    if not numbers:
        return calculate_quote(product, options, tenant.custom_base_days)
    replaced = [option for option in options if option.needs_measurements or option.length_change_inches
                or (option.group == SLEEVE_GROUP and "sleeve_length" in numbers)]
    options = [option for option in options if option not in replaced] + measured_options(tenant, product, numbers)
    options.sort(key=lambda option: option.position)
    return calculate_quote(product, options, tenant.custom_base_days, numbers)


def measured_options(tenant: Tenant, product: Product, numbers: dict[str, int]) -> list[CustomizationOption]:
    """The options a customer's own measurements imply, so they never have to pick them.

    Always the made-to-measure option. Then, compared with the piece as shown:
    - a sleeve length longer or shorter than this piece's sleeve (size guide lengths) picks the
      shop's sleeve option on that side that comes closest, e.g. 21 in on a short sleeve = Full sleeves;
    - a length longer or shorter than the piece picks the matching length option.
    A difference of 1 inch or less counts as unchanged.
    """
    shop = db.session.scalars(db.select(CustomizationOption)
                              .where(CustomizationOption.tenant_id == tenant.id)).all()
    chosen = [option for option in shop if option.needs_measurements][:1]

    sleeve = numbers.get("sleeve_length")
    table = {**sleeve_lengths(tenant), "sleeveless": 0}
    now = table.get(sleeve_word(product.sleeve or ""))
    if sleeve is not None and now is not None and abs(sleeve - now) > 1:
        side = [option for option in shop if option.group == SLEEVE_GROUP and not already_has(product, option)
                and sleeve_word(option.label) in table and (table[sleeve_word(option.label)] - now) * (sleeve - now) > 0]
        chosen += sorted(side, key=lambda option: abs(table[sleeve_word(option.label)] - sleeve))[:1]

    length = numbers.get("length")
    if length and product.length_inches and abs(length - product.length_inches) > 1:
        wanted = length - product.length_inches
        side = [option for option in shop if option.length_change_inches * wanted > 0]
        chosen += sorted(side, key=lambda option: abs(option.length_change_inches - wanted))[:1]
    return chosen


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
    clean = {}
    for name, (words, low, high, required) in MEASUREMENTS.items():
        value = measurements.get(name)
        if value in (None, ""):
            if require_all and required:
                raise UserInputError(f"Please give your {words} measurement in inches.")
            continue
        try:
            inches = round(float(value))
        except (TypeError, ValueError):
            raise UserInputError(f"Your {words} measurement must be a number of inches.") from None
        if not low <= inches <= high:
            raise UserInputError(f"Your {words} measurement should be between {low} and {high} inches.")
        clean[name] = inches
    return clean


def measurements_text(measurements: dict[str, int]) -> str:
    """For the tailor: "bust 38 in, waist 32 in, sleeve length 18 in, length 36 in"."""
    return ", ".join(f"{MEASUREMENTS[name][0]} {inches} in" for name, inches in measurements.items())
