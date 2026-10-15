"""Command-line tasks. Run with: uv run flask --app stylemate <command>"""

import os

import click
from flask import Flask, current_app

from .config import DATA_DIR
from .errors import ServiceUnavailableError, UserInputError
from .extensions import db
from .models import CustomizationOption, FaqItem, SizeGuideRow, SleeveLength, Tenant, User
from .services.catalog import parse_products_csv, save_products

SHOP = {
    "slug": "house-of-m",
    "name": "Closet Corner",
    "tagline": "Everyday elegance, made to fit you.",
    "custom_base_days": 7,
    "shipping_inside_dhaka_bdt": 80,
    "shipping_outside_dhaka_bdt": 150,
    # Sample contact details: replace with the shop's own
    "contact_phone": "+880 1700-000000",
    "contact_email": "hello@closetcorner.example",
    "contact_address": "House 12, Road 5, Dhanmondi, Dhaka 1205",
    "contact_hours": "Saturday to Thursday, 10 am to 8 pm",
    # Sample wallet numbers: replace with the shop's own, or customers send money to a stranger
    "bkash_number": "01700-000000",
    "nagad_number": "01700-000000",
    "rocket_number": "01700-000000",
}
# Details a shop created earlier may not have yet; seed fills in the empty ones
CONTACT_FIELDS = ["contact_phone", "contact_email", "contact_address", "contact_hours",
                  "bkash_number", "nagad_number", "rocket_number"]

# (question, answer). Returns, parcel checks, delivery charges and payment methods are the shop's
# own rules (Oct 13); delivery times are still sample text.
DEFAULT_FAQ = [
    ("How do I choose my size?",
     "Open the Size guide from the top menu, or tap \"Size guide\" beside the sizes on any product page. "
     "It lists the bust, waist and hip each size is cut for. Between two sizes, choose the larger one."),
    ("Can I change a dress to suit me?",
     "Yes, on pieces marked \"Can be customized\". Under \"Make it yours\" you can change the sleeves, length, "
     "lining or fit, and the price updates as you choose."),
    ("How long does a customized piece take?",
     "We make it to order. It is ready in about 7 days, plus the extra days shown for each change you choose. "
     "The product page shows the expected date before you order."),
    ("What is the picture preview?",
     "On some pieces, \"See it first\" draws a picture of the piece with your changes, and on you if you add your photo. "
     "It is drawn by AI as a guide only, so the finished piece may look different. Your photo is not saved by the shop."),
    ("What should I check when my parcel arrives?",
     "Please open the parcel and check everything fully while the delivery person is still with you. "
     "Once the delivery person has left, we can't accept a claim for a tear or a stain."),
    ("Can I return or exchange an order?",
     "No, we don't offer returns or exchanges. If we sent you the wrong size, measure the piece with a "
     "measuring tape and send us a photo of the measurement, using the message form on this page. "
     "We will sort it out for you."),
    ("Where do you deliver, and how long does it take?",
     "We deliver across Bangladesh. Delivery costs ৳80 inside Dhaka and ৳150 anywhere outside Dhaka, per order. "
     "Ready-made pieces usually arrive in 2 to 3 days inside Dhaka and 3 to 5 days elsewhere."),
    ("How do I pay?",
     "You can pay cash on delivery, or by bKash, Nagad or Rocket. For a wallet payment, send the order total "
     "to the number shown at checkout and enter the transaction ID (TrxID) from the confirmation message. "
     "We confirm the order once we have seen the payment."),
    ("Can the stylist chat answer everything?",
     "The stylist answers only from this shop's catalogue, so it won't guess. For anything it can't answer, "
     "send us a message from this page."),
]

# (group, label, change to the price in taka, extra days, change to the length in inches, needs measurements)
# A change that uses less fabric lowers the price (a negative number); one that uses more raises it.
DEFAULT_OPTIONS = [
    ("Sleeves", "Short sleeves", -100, 2, 0, False),
    ("Sleeves", "Full sleeves", 200, 2, 0, False),
    ("Sleeves", "Sleeveless", -150, 1, 0, False),
    ("Length", "Shorter by 2 inches", -100, 1, -2, False),
    ("Length", "Longer by 2 inches", 250, 2, 2, False),
    ("Lining", "Add full cotton lining", 300, 2, 0, False),
    ("Fit", "Made to your measurements", 300, 3, 0, True),
]

# (size, bust, waist, hip): the body each size is cut for, in inches
DEFAULT_SIZES = [
    ("XS", 32, 26, 35),
    ("S", 34, 28, 37),
    ("M", 36, 30, 39),
    ("L", 38, 32, 41),
    ("XL", 40, 34, 43),
    ("XXL", 42, 36, 45),
]

# (sleeve, length in inches from the shoulder seam)
DEFAULT_SLEEVE_LENGTHS = [
    ("Short", 7),
    ("Three-quarter", 16),
    ("Full", 23),
]


def register_cli(app: Flask) -> None:
    app.cli.add_command(seed)
    app.cli.add_command(sync_help)


@click.command("sync-help")
def sync_help() -> None:
    """Send the FAQ, size guide and contact details to Maira, so the stylist chat can answer from them.

    Run it again whenever those change. The first run creates the shop's help dataset.
    """
    tenant = db.session.scalar(db.select(Tenant).where(Tenant.slug == current_app.config["SHOP_SLUG"]))
    if tenant is None:
        raise click.ClickException("The shop isn't set up yet. Run: uv run flask seed")
    try:
        count = current_app.extensions["stylemate"].help_publisher.publish(tenant)
    except (UserInputError, ServiceUnavailableError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Sent {count} answers to Maira dataset {tenant.maira_help_dataset_id}. "
               "The assistant learns them in about a minute.")


@click.command("seed")
@click.option("--owner-email", prompt="Owner email")
@click.option("--owner-password", prompt="Owner password", hide_input=True, confirmation_prompt=True)
@click.option("--products", "products_csv", default=str(DATA_DIR / "products_sample.csv"),
              show_default=True, help="CSV of products to load into the database.")
def seed(owner_email: str, owner_password: str, products_csv: str) -> None:
    """Set up Closet Corner: shop, customization options, products and owner login.

    Safe to run again: it updates what already exists.
    """
    tenant = _upsert_shop()
    _add_default_options(tenant)
    if add_default_faq(tenant):
        click.echo(f"Help page: {len(DEFAULT_FAQ)} questions added.")
    if add_default_size_guide(tenant):
        click.echo(f"Size guide: {len(DEFAULT_SIZES)} sizes and {len(DEFAULT_SLEEVE_LENGTHS)} sleeve lengths added.")

    with open(products_csv, "rb") as file:
        result = save_products(tenant, parse_products_csv(file.read()))
    click.echo(f"Products: {result.created} added, {result.updated} updated.")

    _upsert_owner(tenant, owner_email.strip().lower(), owner_password)
    click.echo(f"Owner login ready for {owner_email}.")

    if not (tenant.maira_profile_id and tenant.maira_dataset_id):
        click.echo("Warning: MAIRA_PROFILE_ID or MAIRA_DATASET_ID is empty in .env. "
                   "Fill them in and run seed again, or the assistant won't work.")
    click.echo("Done.")


def _upsert_shop() -> Tenant:
    slug = current_app.config["SHOP_SLUG"]
    tenant = db.session.scalar(db.select(Tenant).where(Tenant.slug == slug))
    if tenant is None:
        tenant = Tenant(**{**SHOP, "slug": slug})
        db.session.add(tenant)
    for field in CONTACT_FIELDS:  # fill in contact details a shop created earlier doesn't have yet
        if not getattr(tenant, field):
            setattr(tenant, field, SHOP[field])
    tenant.maira_profile_id = os.environ.get("MAIRA_PROFILE_ID", tenant.maira_profile_id or "")
    tenant.maira_dataset_id = os.environ.get("MAIRA_DATASET_ID", tenant.maira_dataset_id or "")
    tenant.maira_image_profile_id = os.environ.get("MAIRA_IMAGE_PROFILE_ID", tenant.maira_image_profile_id or "")
    db.session.commit()
    click.echo(f"Shop: {tenant.name} ({tenant.slug})")
    return tenant


def _add_default_options(tenant: Tenant) -> None:
    exists = db.session.scalar(db.select(CustomizationOption).where(CustomizationOption.tenant_id == tenant.id))
    if exists:
        return
    for position, (group, label, price, days, length_change, measured) in enumerate(DEFAULT_OPTIONS):
        db.session.add(CustomizationOption(tenant_id=tenant.id, group=group, label=label,
                                           extra_price_bdt=price, extra_days=days, length_change_inches=length_change,
                                           needs_measurements=measured, position=position))
    db.session.commit()
    click.echo(f"Customization options: {len(DEFAULT_OPTIONS)} added.")


def add_default_faq(tenant: Tenant) -> bool:
    """Give the shop starting questions and answers, unless it already has some. Returns True if added."""
    if db.session.scalar(db.select(FaqItem).where(FaqItem.tenant_id == tenant.id)):
        return False
    for position, (question, answer) in enumerate(DEFAULT_FAQ):
        db.session.add(FaqItem(tenant_id=tenant.id, question=question, answer=answer, position=position))
    db.session.commit()
    return True


def add_default_size_guide(tenant: Tenant) -> bool:
    """Give the shop a starting size guide, unless it already has one. Returns True if rows were added."""
    if db.session.scalar(db.select(SizeGuideRow).where(SizeGuideRow.tenant_id == tenant.id)):
        return False
    for position, (size, bust, waist, hip) in enumerate(DEFAULT_SIZES):
        db.session.add(SizeGuideRow(tenant_id=tenant.id, size=size, bust_inches=bust,
                                    waist_inches=waist, hip_inches=hip, position=position))
    for position, (name, length) in enumerate(DEFAULT_SLEEVE_LENGTHS):
        db.session.add(SleeveLength(tenant_id=tenant.id, name=name, length_inches=length, position=position))
    db.session.commit()
    return True


def _upsert_owner(tenant: Tenant, email: str, password: str) -> None:
    user = db.session.scalar(db.select(User).where(User.email == email))
    if user is None:
        user = User(tenant_id=tenant.id, email=email)
        db.session.add(user)
    user.set_password(password)
    db.session.commit()
