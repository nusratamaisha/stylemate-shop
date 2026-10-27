

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
    "categories": [{"name": "category", "separator": ""}, {"name": "occasion", "separator": ","}],
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

    def has_item_index(self) -> bool:
        """Whether the project already has the recommender's item index.

        The project's list also holds Maira's indexes (gpt_dataset, chorus, ...), seen Oct 19,
        so a list that isn't empty doesn't mean the recommender is set up.
        """
        detail = self.get_indices().get("detail") or {}
        names = detail.get("response", []) if isinstance(detail, dict) else detail
        return any(str(name).startswith("item") for name in names or [])

    def create_indices(self) -> dict:
        return self._request("POST", "/v1/indices")

    def save_mapper(self, key_map: dict) -> dict:
        """Create the column mapping, or update it if the project already has one."""
        try:
            return self._request("POST", "/v1/mappers", json={"key_map": key_map})
        except ServiceUnavailableError as create_error:
            try:
                return self._request("PUT", "/v1/mappers", json={"key_map": key_map})
            except ServiceUnavailableError as update_error:
                # Both reasons: when there is no mapping yet, the create error is the one that explains it
                raise ServiceUnavailableError(
                    f"Creating the mapping failed: {create_error}\nUpdating it failed: {update_error}"
                ) from update_error

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
