"""Products: reading them, and importing them from a CSV file.

The CSV has the same columns as the file uploaded to Maira, so one file
updates both the shop's database and the assistant's knowledge.
"""

import csv
import io
from dataclasses import dataclass, field

from ..errors import ServiceUnavailableError, UserInputError
from ..extensions import db
from ..models import Product, Tenant

REQUIRED_COLUMNS = ["product_id", "name", "category", "sizes", "colours", "price_bdt", "stock",
                    "customizable", "description"]
OPTIONAL_COLUMNS = ["image", "occasion", "fabric", "length_inches", "sleeve"]


def list_products(tenant: Tenant) -> list[Product]:
    return db.session.scalars(
        db.select(Product).where(Product.tenant_id == tenant.id).order_by(Product.code)
    ).all()


def get_product(tenant: Tenant, code: str) -> Product:
    product = db.session.scalar(
        db.select(Product).where(Product.tenant_id == tenant.id, Product.code == code)
    )
    if product is None:
        raise UserInputError(f"No product with code {code}.")
    return product


@dataclass
class ImportResult:
    created: int = 0
    updated: int = 0
    assistant_status: str = "not_synced"  # "updating", "not_configured" or "failed"
    assistant_message: str = ""
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def parse_products_csv(content: bytes) -> list[dict]:
    """Read and check every row. Raises UserInputError listing every problem found."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise UserInputError("The file must be a UTF-8 CSV.") from None

    reader = csv.DictReader(io.StringIO(text))
    missing = [column for column in REQUIRED_COLUMNS if column not in (reader.fieldnames or [])]
    if missing:
        raise UserInputError(f"Missing columns: {', '.join(missing)}.")

    rows, errors, seen = [], [], set()
    for line, raw in enumerate(reader, start=2):  # line 1 is the header
        try:
            row = _clean_row(raw)
        except UserInputError as exc:
            errors.append(f"Row {line}: {exc}")
            continue
        if row["code"] in seen:
            errors.append(f"Row {line}: product_id {row['code']} appears twice.")
            continue
        seen.add(row["code"])
        rows.append(row)

    if errors:
        raise UserInputError(" ".join(errors[:10]))
    if not rows:
        raise UserInputError("The file has no products.")
    return rows


def save_products(tenant: Tenant, rows: list[dict]) -> ImportResult:
    """Create new products and update existing ones (matched by product_id)."""
    result = ImportResult()
    existing = {product.code: product for product in list_products(tenant)}
    for row in rows:
        product = existing.get(row["code"])
        if product is None:
            product = Product(tenant_id=tenant.id, **row)
            db.session.add(product)
            result.created += 1
        else:
            for key, value in row.items():
                setattr(product, key, value)
            result.updated += 1
    db.session.commit()
    return result


class CatalogImporter:
    """Imports a CSV into the database, then sends the same file to the shop's Maira dataset."""

    def __init__(self, maira):
        self._maira = maira

    def import_csv(self, tenant: Tenant, filename: str, content: bytes) -> ImportResult:
        rows = parse_products_csv(content)
        result = save_products(tenant, rows)

        if not tenant.maira_dataset_id:
            result.assistant_status = "not_configured"
            result.assistant_message = "Products saved. The shop has no Maira dataset ID, so the assistant was not updated."
            return result
        try:
            self._maira.upload_and_train(tenant.maira_dataset_id, filename, content)
        except ServiceUnavailableError as exc:
            result.assistant_status = "failed"
            result.assistant_message = f"Products saved, but the assistant could not be updated: {exc}"
            return result

        result.assistant_status = "updating"
        result.assistant_message = "Products saved. The assistant is learning the changes; this takes about a minute."
        return result


def _clean_row(raw: dict) -> dict:
    def text(column: str) -> str:
        return (raw.get(column) or "").strip()

    code = text("product_id")
    if not code:
        raise UserInputError("product_id is empty.")
    for column in ("name", "category", "sizes", "colours"):
        if not text(column):
            raise UserInputError(f"{column} is empty.")
    customizable = text("customizable").lower()
    if customizable not in ("yes", "no"):
        raise UserInputError("customizable must be yes or no.")

    return {
        "code": code,
        "name": text("name"),
        "image": text("image"),
        "category": text("category"),
        "occasion": text("occasion"),
        "sizes": text("sizes"),
        "colours": text("colours"),
        "fabric": text("fabric"),
        "length_inches": _whole_number(text("length_inches"), "length_inches") if text("length_inches") else None,
        "sleeve": text("sleeve"),
        "price_bdt": _whole_number(text("price_bdt"), "price_bdt"),
        "stock": _whole_number(text("stock"), "stock"),
        "customizable": customizable == "yes",
        "description": text("description"),
    }


def _whole_number(value: str, column: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise UserInputError(f"{column} must be a whole number.") from None
    if number < 0:
        raise UserInputError(f"{column} can't be negative.")
    return number
