"""The Help page: frequently asked questions, the shop's contact details, and messages from customers.

The same answers are also sent to Maira (HelpPublisher), so the stylist chat can
answer "can I return this?", "what size is XL?" or "what do longer sleeves cost?"
from the shop's own words and prices.
"""

import csv
import io

from ..errors import UserInputError
from ..extensions import db
from ..models import ContactMessage, CustomizationOption, FaqItem, Tenant
from .pricing import MEASUREMENTS, SLEEVE_GROUP
from .sizes import size_guide, sleeve_word

HELP_COLUMNS = ["help_id", "topic", "question", "answer"]

MAX_NAME_LENGTH = 120
MAX_CONTACT_LENGTH = 200
MAX_MESSAGE_LENGTH = 1000


def help_page(tenant: Tenant) -> dict:
    items = db.session.scalars(
        db.select(FaqItem).where(FaqItem.tenant_id == tenant.id).order_by(FaqItem.position)
    ).all()
    return {
        "faq": [item.to_dict() for item in items],
        "contact": {
            "phone": tenant.contact_phone,
            "email": tenant.contact_email,
            "address": tenant.contact_address,
            "hours": tenant.contact_hours,
        },
    }


def check_message(name, contact, message) -> tuple[str, str, str]:
    """Tidy and check a contact message. Raises UserInputError saying what is wrong."""
    name, contact, message = (str(value or "").strip() for value in (name, contact, message))
    if not name:
        raise UserInputError("Please tell us your name.")
    if not contact:
        raise UserInputError("Please give a phone number or email so we can reply.")
    if not message:
        raise UserInputError("Please write your message.")
    if len(name) > MAX_NAME_LENGTH or len(contact) > MAX_CONTACT_LENGTH:
        raise UserInputError("Your name or contact details are too long.")
    if len(message) > MAX_MESSAGE_LENGTH:
        raise UserInputError(f"Please keep your message under {MAX_MESSAGE_LENGTH} characters.")
    return name, contact, message


def save_message(tenant: Tenant, name: str, contact: str, message: str, picture: str = "") -> ContactMessage:
    """`picture` is the saved file name of an attached photo (see services/uploads.py), or ""."""
    saved = ContactMessage(tenant_id=tenant.id, name=name, contact=contact, message=message, picture=picture)
    db.session.add(saved)
    db.session.commit()
    return saved


def messages(tenant: Tenant) -> list[ContactMessage]:
    """The shop's messages, newest first."""
    return db.session.scalars(
        db.select(ContactMessage).where(ContactMessage.tenant_id == tenant.id)
        .order_by(ContactMessage.created_at.desc(), ContactMessage.id.desc())
    ).all()


def message_picture_name(tenant: Tenant, message_id: int) -> str:
    """The file name of a message's photo, for this shop's owner only."""
    message = db.session.scalar(
        db.select(ContactMessage).where(ContactMessage.tenant_id == tenant.id, ContactMessage.id == message_id)
    )
    if message is None or not message.picture:
        raise UserInputError("That message has no photo.")
    return message.picture


def help_documents(tenant: Tenant) -> list[dict]:
    """Everything on the Help and Size guide pages as question-and-answer rows for Maira.

    Each row has a stable ID, so sending them again replaces the old answers
    instead of adding duplicates.
    """
    page = help_page(tenant)
    rows = [{"help_id": f"FAQ-{item['id']}", "topic": "Frequently asked question",
             "question": item["question"], "answer": item["answer"]} for item in page["faq"]]

    guide = size_guide(tenant)
    for size in guide["sizes"]:
        rows.append({
            "help_id": f"SIZE-{size['size']}", "topic": "Size guide",
            "question": f"What body measurements is size {size['size']} for?",
            "answer": (f"Size {size['size']} is cut for a bust of {size['bust_inches']} inches, a waist of "
                       f"{size['waist_inches']} inches and a hip of {size['hip_inches']} inches."),
        })
    for sleeve in guide["sleeves"]:
        name = sleeve["name"].lower()
        rows.append({
            "help_id": f"SLEEVE-{sleeve['name']}", "topic": "Size guide",
            "question": f"How long are {name} sleeves?",
            "answer": (f"{sleeve['name']} sleeves are about {sleeve['length_inches']} inches long, "
                       "measured from the shoulder seam to the edge of the sleeve."),
        })

    rows += customization_documents(tenant, guide["sleeves"])

    contact = page["contact"]
    parts = [f"{label}: {contact[key]}" for key, label in
             (("phone", "Phone"), ("email", "Email"), ("address", "Address"), ("hours", "Opening hours")) if contact[key]]
    if parts:
        rows.append({"help_id": "CONTACT", "topic": "Contact",
                     "question": "How can I contact the shop?",
                     "answer": ". ".join(parts) + ". You can also send a message from the Help page of the website."})
    return rows


def customization_documents(tenant: Tenant, sleeves: list[dict]) -> list[dict]:
    """What changes cost and how the product page works them out, from the shop's own option rows.

    Built from the database, not written by hand, so the assistant's prices can't drift from
    what pricing.py charges. Without these the assistant said the price of longer sleeves
    "isn't specified" (Oct 15).
    """
    options = db.session.scalars(db.select(CustomizationOption).where(CustomizationOption.tenant_id == tenant.id)
                                 .order_by(CustomizationOption.position)).all()
    if not options:
        return []
    inches = {sleeve_word(row["name"]): row["length_inches"] for row in sleeves}
    groups: dict[str, list[str]] = {}
    for option in options:
        about = inches.get(sleeve_word(option.label)) if option.group == SLEEVE_GROUP else None
        # A length is cut to the number typed, so "Shorter by 2 inches" would mislead here
        label = (("Longer" if option.length_change_inches > 0 else "Shorter") + " length"
                 if option.length_change_inches else option.label)
        groups.setdefault(option.group, []).append(
            f"{label}{f' (about {about} inches)' if about else ''}: {_price_words(option.extra_price_bdt)}"
            f", {option.extra_days} extra day{'s' if option.extra_days != 1 else ''}")
    charges = "; ".join(f"{group}: {', '.join(lines)}" for group, lines in groups.items())
    boxes = ", ".join(words for words, *_ in MEASUREMENTS.values())
    base = tenant.custom_base_days

    rows = [
        ("CUSTOM-CHARGES", "What does each change to a piece cost?",
         f"Only pieces marked \"Can be customized\" can be changed. The price of a changed piece is the piece's own "
         f"price plus these charges (a minus is a discount, because the change uses less fabric): {charges}. "
         f"A changed piece is made to order: ready in about {base} days plus the extra days of each change. "
         "Sleeves and length are worked out from the measurements typed on the product page; for a lining "
         "or sleeveless, tell the stylist when ordering in the chat."),
        ("CUSTOM-HOW", "How do I customize a piece or order it to my measurements?",
         f"On the product page, under \"Make it yours\", type your measurements in inches: {boxes}. Only the bust "
         "is needed. Typing them makes the piece made to measure at no extra charge, with no S, M or L to choose; "
         "leaving them empty orders a standard size. The sleeve and length charges are added from your numbers "
         "and the page shows the final price before you order. You can also tell the stylist in the chat."),
    ]
    sleeve_options = [option for option in options if option.group == SLEEVE_GROUP]
    if sleeve_options:
        table = ", ".join(f"{name} about {length} inches" for name, length in inches.items())
        rows.append(("CUSTOM-SLEEVES", "How much do longer or shorter sleeves cost?",
                     f"Sleeve lengths are measured from the shoulder seam: {table}. If the sleeve length you type "
                     "is more than an inch longer than the piece's own sleeve, the nearest longer sleeve is charged; "
                     "more than an inch shorter, the nearest shorter sleeve. "
                     + "; ".join(f"{option.label}: {_price_words(option.extra_price_bdt)}" for option in sleeve_options)
                     + _sleeve_example(sleeve_options, inches)))
    length_options = [option for option in options if option.length_change_inches]
    if length_options:
        longer = [option for option in length_options if option.length_change_inches > 0]
        shorter = [option for option in length_options if option.length_change_inches < 0]
        parts = ([f"more than an inch longer than the piece costs {_price_words(longer[0].extra_price_bdt)}"]
                 if longer else []) + \
                ([f"more than an inch shorter costs {_price_words(shorter[0].extra_price_bdt)}"] if shorter else [])
        rows.append(("CUSTOM-LENGTH", "How much does a longer or shorter length cost?",
                     "Type the length you want in inches and the piece is cut to exactly that. A length "
                     f"{'; a length '.join(parts)}, however many inches it changes. "
                     "Each product page shows the piece's own length."))
    return [{"help_id": help_id, "topic": "Customization", "question": question, "answer": answer}
            for help_id, question, answer in rows]


def _sleeve_example(sleeve_options: list[CustomizationOption], inches: dict[str, int]) -> str:
    """". For example, a short-sleeved piece costing 1,900 taka …", with the shop's own longest sleeve and price."""
    known = [option for option in sleeve_options if sleeve_word(option.label) in inches]
    if "short" not in inches or not known:
        return "."
    longest = max(known, key=lambda option: inches[sleeve_word(option.label)])
    if inches[sleeve_word(longest.label)] <= inches["short"]:
        return "."
    typed, total = inches[sleeve_word(longest.label)] - 2, 1900 + longest.extra_price_bdt
    return (f". For example, a short-sleeved piece costing 1,900 taka with sleeves of about {typed} inches gets "
            f"{longest.label.lower()}, so it costs 1,900 {'+' if longest.extra_price_bdt >= 0 else '-'} "
            f"{abs(longest.extra_price_bdt)} = {total:,} taka.")


def _price_words(amount: int) -> str:
    if amount > 0:
        return f"{amount} taka extra"
    if amount < 0:
        return f"{-amount} taka less"
    return "no extra charge"


def help_csv(tenant: Tenant) -> bytes:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=HELP_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(help_documents(tenant))
    return out.getvalue().encode("utf-8")


class HelpPublisher:
    """Sends the shop's help answers to their own Maira dataset, creating it the first time."""

    def __init__(self, maira):
        self._maira = maira

    def publish(self, tenant: Tenant) -> int:
        """Upload and train. Returns the number of answers sent."""
        if not tenant.maira_dataset_id:
            raise UserInputError("The shop has no Maira product dataset yet, so its tag can't be copied.")
        if not tenant.maira_help_dataset_id:
            # Same tags as the product dataset: the chat profile searches by tag,
            # so the new dataset is found without touching the profile.
            tags = self._maira.get_dataset(tenant.maira_dataset_id).get("tags") or []
            tenant.maira_help_dataset_id = self._maira.create_dataset(
                name=f"{tenant.slug}-help", idx_column="help_id", tags=tags,
                description=f"FAQ, size guide and contact details for {tenant.name}",
            )
            db.session.commit()  # remember the ID even if the upload below fails
        rows = help_documents(tenant)
        self._maira.upload_and_train(tenant.maira_help_dataset_id, "help.csv", help_csv(tenant))
        return len(rows)
