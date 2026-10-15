"""Talks to Gigalogy's recommender: setting up the shop's catalogue there, and asking for similar items.

The recommender keeps its own copy of the products (separate from the Maira dataset), so
`flask sync-recommender` sets it up once: an index, a mapping from our CSV columns to its
fields, the uploaded catalogue, then training. After that the shop asks it for items similar
to one product (product page) or to the whole bag (bag page).

Open question (Oct 15): the spec gives every response as {"detail": object} without its
fields, so parse_item_ids() accepts the likely shapes. Confirm the real one on the first live
call and tighten it, as was done for parse_generated_image() in maira.py.
"""

from ..errors import ServiceUnavailableError
from .base import GigalogyClient

# Our CSV columns -> the recommender's fields (POST /v1/mappers). item_id, title, availability,
# price, categories, flag and search_settings are required by the spec.
KEY_MAP = {
    "item_id": "product_id",
    "title": "name",
    "second_title": "fabric",
    "third_title": "colours",
    "availability": "availability",
    "description": "description",
    "price": "price_bdt",
    "categories": [{"name": "category", "separator": None}, {"name": "occasion", "separator": ","}],
    "flag": ["customizable"],
    "custom": [{"name": "sleeve", "data_type": "STR"}, {"name": "length_inches", "data_type": "INT"}],
    "search_settings": {  # within the ranges the spec gives; tune once it is live
        "keyword_ngram": 1, "depth": 1, "cluster_size": 5, "is_keyword_enabled": False, "top_k": 10,
    },
}


class RecommenderClient(GigalogyClient):
    service_name = "Gigalogy recommender"

    # --- Setup (flask sync-recommender) ---

    def get_indices(self) -> dict:
        return self._request("GET", "/v1/indices")

    def create_indices(self) -> dict:
        return self._request("POST", "/v1/indices")

    def save_mapper(self, key_map: dict) -> dict:
        """Create the column mapping, or update it if the project already has one."""
        try:
            return self._request("POST", "/v1/mappers", json={"key_map": key_map})
        except ServiceUnavailableError:
            return self._request("PUT", "/v1/mappers", json={"key_map": key_map})

    def upload_items(self, filename: str, content: bytes) -> dict:
        return self._request("POST", "/v1/items/save", files={"file": (filename, content, "text/csv")})

    def train_items(self) -> dict:
        return self._request("GET", "/v1/items/train", params={"train_all": "true"})

    # --- Recommendations ---

    def similar_items(self, *, user_id: str, item_id: str, member_id: str | None = None) -> list[str]:
        """Items most like this one in content (POST /v1/items/recommend), best first."""
        data = self._request("POST", "/v1/items/recommend", json={
            "user_id": user_id, "member_id": member_id, "item_id": item_id, "details": False})
        return parse_item_ids(data)

    def cart_items(self, *, user_id: str, item_ids: list[str], member_id: str | None = None,
                   size: int = 10) -> list[str]:
        """Items most like everything in the bag together (POST /v1/carts/recommend), best first."""
        data = self._request("POST", "/v1/carts/recommend", json={
            "user_id": user_id, "member_id": member_id, "item_ids": item_ids,
            "exclude_item_ids": item_ids, "size": size, "details": False})
        return parse_item_ids(data)


def parse_item_ids(data) -> list[str]:
    """The recommended item IDs in order, from whichever shape the response has.

    Accepts a list of IDs, a list of {"item_id": ...} objects, or either of those
    anywhere inside "detail" (for example {"detail": {"items": [...]}}).
    """
    found: list[str] = []

    def walk(value):
        if isinstance(value, dict):
            item_id = value.get("item_id") or value.get("id")
            if isinstance(item_id, (str, int)) and not isinstance(item_id, bool):
                found.append(str(item_id))
                return
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                if isinstance(child, str):
                    found.append(child)
                else:
                    walk(child)

    walk(data.get("detail", data) if isinstance(data, dict) else data)
    return list(dict.fromkeys(found))  # drop repeats, keep the order
