"""Database tables.

Every table has a tenant_id, so one StyleMate installation can serve many shops.
Today there is one shop (The House of "M"); adding another is a new Tenant row.
"""

from datetime import date, datetime, timezone

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def split_list(value: str) -> list[str]:
    """Turn "S, M, L" into ["S", "M", "L"]."""
    return [part.strip() for part in value.split(",") if part.strip()]


class Tenant(db.Model):
    """A shop using StyleMate, with the Maira IDs that keep its data separate."""

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    tagline: Mapped[str] = mapped_column(String(200), default="")
    maira_profile_id: Mapped[str] = mapped_column(String(64), default="")
    maira_dataset_id: Mapped[str] = mapped_column(String(64), default="")
    maira_help_dataset_id: Mapped[str] = mapped_column(String(64), default="")  # FAQ and size guide; made by `flask sync-help`
    maira_image_profile_id: Mapped[str] = mapped_column(String(64), default="")  # empty: no image preview
    custom_base_days: Mapped[int] = mapped_column(default=7)
    shipping_inside_dhaka_bdt: Mapped[int] = mapped_column(default=80)
    shipping_outside_dhaka_bdt: Mapped[int] = mapped_column(default=150)
    # Shown on the Help page. An empty one is simply left out.
    contact_phone: Mapped[str] = mapped_column(String(40), default="")
    contact_email: Mapped[str] = mapped_column(String(200), default="")
    contact_address: Mapped[str] = mapped_column(String(300), default="")
    contact_hours: Mapped[str] = mapped_column(String(200), default="")


class User(db.Model):
    """A shop owner who can log in to the dashboard."""

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"))
    email: Mapped[str] = mapped_column(String(200), unique=True)
    password_hash: Mapped[str] = mapped_column(String(300))

    tenant: Mapped[Tenant] = relationship()

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Customer(db.Model):
    """A shopper with an account. Kept apart from User, so a customer login can never open the owner dashboard."""

    __table_args__ = (UniqueConstraint("tenant_id", "email"),)  # the same person can shop at two shops

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"))
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(40), default="")
    password_hash: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_dict(self) -> dict:
        return {"name": self.name, "email": self.email, "phone": self.phone}


class Product(db.Model):
    """One product, with the same columns as the CSV uploaded to Maira."""

    __table_args__ = (UniqueConstraint("tenant_id", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"))
    code: Mapped[str] = mapped_column(String(40))  # "product_id" in the CSV, e.g. SR-001
    name: Mapped[str] = mapped_column(String(200))
    image: Mapped[str] = mapped_column(String(200), default="")
    category: Mapped[str] = mapped_column(String(80))
    occasion: Mapped[str] = mapped_column(String(200), default="")
    sizes: Mapped[str] = mapped_column(String(200))
    colours: Mapped[str] = mapped_column(String(200))
    fabric: Mapped[str] = mapped_column(String(200), default="")
    length_inches: Mapped[int | None]  # shoulder to hem; None when the shop hasn't measured it
    sleeve: Mapped[str] = mapped_column(String(60), default="")  # e.g. "Three-quarter", "Sleeveless"
    price_bdt: Mapped[int]
    stock: Mapped[int] = mapped_column(default=0)
    customizable: Mapped[bool] = mapped_column(default=False)
    description: Mapped[str] = mapped_column(Text, default="")

    @property
    def size_list(self) -> list[str]:
        return split_list(self.sizes)

    @property
    def colour_list(self) -> list[str]:
        return split_list(self.colours)

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "image_url": f"/api/images/{self.image}" if self.image else None,
            "category": self.category,
            "occasions": split_list(self.occasion),
            "sizes": self.size_list,
            "colours": self.colour_list,
            "fabric": self.fabric,
            "length_inches": self.length_inches,
            "sleeve": self.sleeve,
            "price_bdt": self.price_bdt,
            "stock": self.stock,
            "in_stock": self.stock > 0,
            "customizable": self.customizable,
            "description": self.description,
        }


class CustomizationOption(db.Model):
    """One change a customer can order, e.g. group "Sleeves", label "Full sleeves", +৳200.

    extra_price_bdt can be negative: a change that uses less fabric (short sleeves,
    a shorter length) makes the piece cheaper.

    Options are rows, not code: a shop adds a new option by adding a row.
    """

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"))
    group: Mapped[str] = mapped_column(String(60))
    label: Mapped[str] = mapped_column(String(120))
    extra_price_bdt: Mapped[int] = mapped_column(default=0)
    extra_days: Mapped[int] = mapped_column(default=0)
    length_change_inches: Mapped[int] = mapped_column(default=0)  # -2 for "Shorter by 2 inches"
    needs_measurements: Mapped[bool] = mapped_column(default=False)  # made to measure: no S/M/L, measurements instead
    position: Mapped[int] = mapped_column(default=0)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "group": self.group,
            "label": self.label,
            "extra_price_bdt": self.extra_price_bdt,
            "extra_days": self.extra_days,
            "needs_measurements": self.needs_measurements,
        }


class SizeGuideRow(db.Model):
    """One row of the shop's size chart: the body a size is cut for, in inches."""

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"))
    size: Mapped[str] = mapped_column(String(20))  # matches the sizes in the product CSV, e.g. "XL"
    bust_inches: Mapped[int]
    waist_inches: Mapped[int]
    hip_inches: Mapped[int]
    position: Mapped[int] = mapped_column(default=0)

    def to_dict(self) -> dict:
        return {"size": self.size, "bust_inches": self.bust_inches,
                "waist_inches": self.waist_inches, "hip_inches": self.hip_inches}


class SleeveLength(db.Model):
    """How long one kind of sleeve is, from the shoulder seam to the sleeve's edge."""

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"))
    name: Mapped[str] = mapped_column(String(60))  # same words as a product's `sleeve`, e.g. "Short"
    length_inches: Mapped[int]
    position: Mapped[int] = mapped_column(default=0)

    def to_dict(self) -> dict:
        return {"name": self.name, "length_inches": self.length_inches}


class FaqItem(db.Model):
    """One question and answer on the shop's Help page."""

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"))
    question: Mapped[str] = mapped_column(String(300))
    answer: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(default=0)

    def to_dict(self) -> dict:
        return {"id": self.id, "question": self.question, "answer": self.answer}


class ContactMessage(db.Model):
    """A message a customer sent from the Help page. The owner reads these in the dashboard."""

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"))
    name: Mapped[str] = mapped_column(String(120))
    contact: Mapped[str] = mapped_column(String(200))  # the phone number or email to reply to
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "contact": self.contact,
                "message": self.message, "sent_at": self.created_at.isoformat()}


class RateLimitEvent(db.Model):
    """One use of a limited action (a contact message, a picture preview) by one sender."""

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"))
    action: Mapped[str] = mapped_column(String(40))
    sender_key: Mapped[str] = mapped_column(String(64), index=True)  # a hash of the IP address, never the address
    created_at: Mapped[datetime] = mapped_column(default=utc_now)


class Review(db.Model):
    """A customer's rating of a product they ordered. One per customer per product."""

    __table_args__ = (UniqueConstraint("customer_id", "product_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"))
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"))
    rating: Mapped[int]  # 1 to 5 stars
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    customer: Mapped[Customer] = relationship()


class ChatTurn(db.Model):
    """One customer question and the assistant's answer. Feeds the owner dashboard."""

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"))
    visitor_id: Mapped[str] = mapped_column(String(64))
    session_id: Mapped[str] = mapped_column(String(64), default="")
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    top_score: Mapped[float | None]
    answered: Mapped[bool]
    via_voice: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)


class Order(db.Model):
    """A checkout (no real payment)."""

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"))
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customer.id"))  # None for a guest checkout
    customer_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(40))
    address: Mapped[str] = mapped_column(Text)
    delivery_area: Mapped[str] = mapped_column(String(20), default="")  # "inside_dhaka" or "outside_dhaka"
    shipping_bdt: Mapped[int] = mapped_column(default=0)
    total_bdt: Mapped[int]  # items plus shipping
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order")

    def to_dict(self) -> dict:
        return {
            "order_id": self.id,
            "ordered_at": self.created_at.isoformat(),
            "delivery_area": self.delivery_area,
            "subtotal_bdt": self.total_bdt - self.shipping_bdt,
            "shipping_bdt": self.shipping_bdt,
            "total_bdt": self.total_bdt,
            "items": [item.to_dict() for item in self.items],
        }


class OrderItem(db.Model):
    """One line of an order. Customized lines go into the owner's custom order queue."""

    STATUSES = ("new", "in_production", "shipped")

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"))
    order_id: Mapped[int] = mapped_column(ForeignKey("order.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"))
    size: Mapped[str] = mapped_column(String(20))
    colour: Mapped[str] = mapped_column(String(60))
    quantity: Mapped[int]
    unit_price_bdt: Mapped[int]
    is_custom: Mapped[bool] = mapped_column(default=False)
    custom_details: Mapped[str] = mapped_column(Text, default="")  # "Sleeves: Short sleeves; Length: ..."
    notes: Mapped[str] = mapped_column(Text, default="")
    reference_image: Mapped[str] = mapped_column(String(60), default="")  # the customer's picture for the tailor
    ready_by: Mapped[date | None]
    status: Mapped[str] = mapped_column(String(20), default="new")

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "order_id": self.order_id,
            "product_code": self.product.code,
            "product_name": self.product.name,
            "size": self.size,
            "colour": self.colour,
            "quantity": self.quantity,
            "unit_price_bdt": self.unit_price_bdt,
            "is_custom": self.is_custom,
            "custom_details": self.custom_details,
            "notes": self.notes,
            "has_reference_image": bool(self.reference_image),
            "ready_by": self.ready_by.isoformat() if self.ready_by else None,
            "status": self.status,
            "customer_name": self.order.customer_name,
            "phone": self.order.phone,
            "ordered_at": self.order.created_at.isoformat(),
        }

