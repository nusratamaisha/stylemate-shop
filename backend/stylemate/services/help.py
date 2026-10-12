"""The Help page: frequently asked questions, the shop's contact details, and messages from customers.

The same answers are also sent to Maira (HelpPublisher), so the stylist chat can
answer "can I return this?" or "what size is XL?" from the shop's own words.
"""

import csv
import io

from ..errors import UserInputError
from ..extensions import db
from ..models import ContactMessage, FaqItem, Tenant
from .sizes import size_guide

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


def save_message(tenant: Tenant, name: str, contact: str, message: str) -> ContactMessage:
    saved = ContactMessage(tenant_id=tenant.id, name=name, contact=contact, message=message)
    db.session.add(saved)
    db.session.commit()
    return saved


def messages(tenant: Tenant) -> list[ContactMessage]:
    """The shop's messages, newest first."""
    return db.session.scalars(
        db.select(ContactMessage).where(ContactMessage.tenant_id == tenant.id)
        .order_by(ContactMessage.created_at.desc(), ContactMessage.id.desc())
    ).all()


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

    contact = page["contact"]
    parts = [f"{label}: {contact[key]}" for key, label in
             (("phone", "Phone"), ("email", "Email"), ("address", "Address"), ("hours", "Opening hours")) if contact[key]]
    if parts:
        rows.append({"help_id": "CONTACT", "topic": "Contact",
                     "question": "How can I contact the shop?",
                     "answer": ". ".join(parts) + ". You can also send a message from the Help page of the website."})
    return rows


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
