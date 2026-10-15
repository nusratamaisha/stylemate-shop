"""Recommendations: "You may also like" on a product page and "Complete the look" in the bag.

Gigalogy's recommender suggests pieces by content (clients/recommender.py). Flask then keeps
only what this shop can really sell this customer, because the recommender knows neither our
stock nor sizes:
- a piece of this shop, not the one being viewed and not already in the bag;
- in stock, or customizable (it can be made to order);
- in the customer's usual size, when they have one saved (a customizable piece can be made
  to their measurements, so it stays).

Until `flask sync-recommender` has set the shop up (Tenant.recommender_ready), or if Gigalogy
fails, the shop's own picks fill the list: pieces from the same section that share an
occasion. The page never shows an empty box, and a failure never breaks it.
"""

import csv
import io
import logging
import time

from ..errors import ServiceUnavailableError
from ..extensions import db
from ..models import Customer, Product, Tenant
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
        return self._pick(tenant, ids, exclude={product.code}, near=[product], customer=customer)

    def for_bag(self, tenant: Tenant, codes: list[str], visitor_id: str, customer: Customer | None) -> dict:
        """For the bag: pieces that go with everything in it."""
        in_bag = [product for product in list_products(tenant) if product.code in set(codes)]
        if not in_bag:
            return {"products": [], "source": "shop"}
        bag_codes = sorted(product.code for product in in_bag)
        ids = self._ask(tenant, ("cart", *bag_codes), lambda: self._recommender.cart_items(
            user_id=visitor_id, item_ids=bag_codes, member_id=_member(customer)))
        return self._pick(tenant, ids, exclude=set(bag_codes), near=in_bag, customer=customer,
                          other_sections=True)

    def _ask(self, tenant: Tenant, key: tuple, call) -> list[str]:
        """Gigalogy's suggestions, cached; [] when it isn't set up yet or doesn't answer."""
        if not tenant.recommender_ready:
            return []
        key = (tenant.id, *key)
        cached = self._cache.get(key)
        if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
            return cached[1]
        try:
            ids = call()
        except ServiceUnavailableError as problem:  # show the shop's own picks instead of an error
            log.warning("Recommendations fell back to the shop's own picks: %s", problem)
            return []
        self._cache[key] = (time.monotonic(), ids)
        return ids

    def _pick(self, tenant: Tenant, ids: list[str], *, exclude: set[str], near: list[Product],
              customer: Customer | None, other_sections: bool = False) -> dict:
        catalogue = {product.code: product for product in list_products(tenant)}
        size = customer.preferred_size if customer else ""

        def sellable(product: Product) -> bool:
            return (product.code not in exclude
                    and (product.stock > 0 or product.customizable)
                    and (not size or size in product.size_list or product.customizable))

        chosen = [catalogue[code] for code in ids if code in catalogue and sellable(catalogue[code])][:SHOWN]
        from_gigalogy = len(chosen)
        # Fill up with the shop's own picks, closest first
        others = sorted((product for product in catalogue.values() if sellable(product) and product not in chosen),
                        key=lambda product: _closeness(product, near, other_sections))
        chosen += others[:SHOWN - len(chosen)]
        return {"products": [product.to_dict() for product in chosen],
                "source": "gigalogy" if from_gigalogy else "shop"}


def _closeness(product: Product, near: list[Product], other_sections: bool) -> tuple:
    """Sort key for the shop's own picks: shared occasions first, then the section, then a similar price.

    On a product page the same section comes first ("more dresses"); in the bag another section
    does ("a skirt for this top"), because that completes the look.
    """
    occasions = {word.strip().lower() for item in near for word in item.occasion.split(",") if word.strip()}
    shared = len(occasions & {word.strip().lower() for word in product.occasion.split(",") if word.strip()})
    sections = {item.category for item in near}
    section_rank = (product.category in sections) if other_sections else (product.category not in sections)
    price = sum(item.price_bdt for item in near) / len(near)
    return (section_rank, -shared, abs(product.price_bdt - price), product.code)


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
    """Index, mapping, catalogue and training, then switch recommendations on. Safe to run again.

    Returns the number of products sent. A failing step raises, and the shop stays on its own picks.
    """
    if not recommender.get_indices().get("detail"):
        report("Creating the item index…")
        recommender.create_indices()
    report("Saving the column mapping…")
    recommender.save_mapper(key_map)
    count = len(list_products(tenant))
    report(f"Uploading {count} products…")
    recommender.upload_items("products.csv", recommender_csv(tenant))
    report("Training…")
    recommender.train_items()
    tenant.recommender_ready = True
    db.session.commit()
    return count
