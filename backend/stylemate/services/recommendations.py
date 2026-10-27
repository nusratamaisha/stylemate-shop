"""Recommendations: "You may also like" on a product page (POST /v1/items/recommend only).

Only Gigalogy's recommender chooses the pieces (clients/recommender.py), by content. Flask then
keeps only what this shop can really sell this customer, because the recommender knows neither
our stock nor sizes:
- a piece of this shop, not the one being viewed;
- in stock, or customizable (it can be made to order);
- in the customer's usual size, when they have one saved (a customizable piece can be made
  to their measurements, so it stays).

Flask never picks pieces itself. Until `flask sync-recommender` has set the shop up
(Tenant.recommender_ready), on a plan without smart suggestions, or if Gigalogy fails, the list
is empty and the page simply shows no suggestion row. A failure never breaks the page.
"""

import csv
import io
import logging
import time

from ..errors import ServiceUnavailableError
from ..extensions import db
from ..models import Customer, Product, Tenant
from . import plans
from .catalog import get_product, list_products

log = logging.getLogger(__name__)

SHOWN = 4  # one row of cards
CACHE_SECONDS = 600  # a product page viewed again within 10 minutes costs no new API call


class RecommendationService:
    def __init__(self, recommender):
        self._recommender = recommender
        self._cache: dict[tuple, tuple[float, list[str]]] = {}

    def similar(self, tenant: Tenant, code: str, visitor_id: str, customer: Customer | None) -> dict:
        """For a product page: pieces like this one."""
        product = get_product(tenant, code)
        ids = self._ask(tenant, ("item", product.code), lambda: self._recommender.similar_items(
            user_id=visitor_id, item_id=product.code, member_id=_member(customer)))
        return self._pick(tenant, ids, exclude={product.code}, customer=customer)

    def _ask(self, tenant: Tenant, key: tuple, call) -> list[str]:
        """Gigalogy's suggestions, cached; [] when it isn't set up, not in the shop's plan, or doesn't answer."""
        if not (tenant.recommender_ready and plans.plan_of(tenant).smart_recommendations):
            return []
        key = (tenant.id, *key)
        cached = self._cache.get(key)
        if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
            return cached[1]
        try:
            ids = call()
        except ServiceUnavailableError as problem:  # no suggestion row rather than an error
            log.warning("No recommendations shown, Gigalogy didn't answer: %s", problem)
            return []
        self._cache[key] = (time.monotonic(), ids)
        return ids

    def _pick(self, tenant: Tenant, ids: list[str], *, exclude: set[str], customer: Customer | None) -> dict:
        """Gigalogy's order, keeping only pieces this shop can sell this customer."""
        catalogue = {product.code: product for product in list_products(tenant)}
        size = customer.preferred_size if customer else ""

        def sellable(product: Product) -> bool:
            return (product.code not in exclude
                    and (product.stock > 0 or product.customizable)
                    and (not size or size in product.size_list or product.customizable))

        chosen = [catalogue[code] for code in ids if code in catalogue and sellable(catalogue[code])][:SHOWN]
        return {"products": [product.to_dict() for product in chosen]}


def _member(customer: Customer | None) -> str | None:
    """The recommender's member_id: a logged-in customer, the same on every device."""
    return f"customer-{customer.id}" if customer else None


# --- Setup: `flask sync-recommender` ---

def recommender_csv(tenant: Tenant) -> bytes:
    """The catalogue as the recommender reads it (columns named in clients/recommender.KEY_MAP)."""
    columns = ["product_id", "name", "category", "occasion", "colours", "fabric", "sleeve", "length_inches",
               "price_bdt", "availability", "customizable", "description"]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for product in list_products(tenant):
        writer.writerow({
            "product_id": product.code, "name": product.name, "category": product.category,
            "occasion": product.occasion, "colours": product.colours, "fabric": product.fabric,
            "sleeve": product.sleeve, "length_inches": product.length_inches or "",
            "price_bdt": product.price_bdt,
            "availability": "in_stock" if product.stock > 0 or product.customizable else "out_of_stock",
            "customizable": "true" if product.customizable else "false", "description": product.description,
        })
    return out.getvalue().encode("utf-8")


def set_up_recommender(tenant: Tenant, recommender, key_map: dict, report=print) -> int:
    """Mapping, index, catalogue and training, then switch recommendations on. Safe to run again.

    Returns the number of products sent. A failing step raises, and suggestions stay off.
    The mapping comes first: creating the index without one returns 404 "Mapper Not found" (Oct 19).
    """
    report("Saving the column mapping…")
    recommender.save_mapper(key_map)
    if not recommender.has_item_index():
        report("Creating the item index…")
        recommender.create_indices()
    count = len(list_products(tenant))
    report(f"Uploading {count} products…")
    recommender.upload_items("products.csv", recommender_csv(tenant))
    report("Training…")
    recommender.train_items()
    tenant.recommender_ready = True
    db.session.commit()
    return count
