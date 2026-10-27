"""What a gateway model costs today, from the proxy's public cost map.

Plain functions over the parsed map; the client does the fetching. A model absent from
the map simply has no price: the picker is never worse off for the map being missing.
"""
from dataclasses import dataclass
from typing import Dict, Optional

# Where the list price of a deployed model may be filed.
_LIST_KEY_PREFIXES = ("", "anthropic/", "vertex_ai/", "gemini/", "openai/")


@dataclass(frozen=True)
class ModelPrice:
    """USD per token."""

    input: float
    output: Optional[float] = None

    @property
    def free(self) -> bool:
        return self.input == 0

    def describe(self) -> str:
        """`$5.00 in · $25.00 out per 1M`, or `free`."""
        if self.free:
            return "free"
        out = "–" if self.output is None else f"${self.output * 1_000_000:.2f}"
        return f"${self.input * 1_000_000:.2f} in · {out} out per 1M"


def _price(entry: object) -> Optional[ModelPrice]:
    if not isinstance(entry, dict):
        return None
    cost_in, cost_out = entry.get("input_cost_per_token"), entry.get("output_cost_per_token")
    if not isinstance(cost_in, (int, float)):
        return None
    return ModelPrice(float(cost_in), float(cost_out) if isinstance(cost_out, (int, float)) else None)


def prices_from(cost_map: dict) -> Dict[str, ModelPrice]:
    """Model id -> what calling that id costs.

    The proxy names each deployment's model in `base_model`, and calling the plain id
    reaches the free-tier deployment (campaigns are priced there), so that one wins and
    the cheapest of the rest is the fallback. Ids with no deployment entry fall back to
    the public list price under their own key.
    """
    found: Dict[str, list] = {}
    for entry in cost_map.values():
        if isinstance(entry, dict) and entry.get("base_model") and _price(entry):
            found.setdefault(entry["base_model"], []).append(entry)

    prices: Dict[str, ModelPrice] = {}
    for base, entries in found.items():
        free = [e for e in entries if e.get("tier") == "free"]
        pool = free or entries
        prices[base] = min((_price(e) for e in pool), key=lambda p: p.input)
    return prices


def prices_from_model_info(payload: dict) -> Dict[str, ModelPrice]:
    """Alias -> price, from the gateway's authenticated `/model/info`.

    That endpoint is keyed by the names the gateway publishes (the ones `/models` lists
    and a request carries), so unlike the public map it needs no id matching. An alias
    may have several deployments; as in `prices_from`, the free tier is the one a plain
    call reaches, and the cheapest of the rest is the fallback.
    """
    found: Dict[str, list] = {}
    for item in payload.get("data") or []:
        if not isinstance(item, dict):
            continue
        info = item.get("model_info") or {}
        if item.get("model_name") and _price(info):
            found.setdefault(item["model_name"], []).append(info)

    prices: Dict[str, ModelPrice] = {}
    for name, infos in found.items():
        pool = [i for i in infos if i.get("tier") == "free"] or infos
        prices[name] = min((_price(i) for i in pool), key=lambda p: p.input)
    return prices


def price_of(prices: Dict[str, ModelPrice], cost_map: dict, model_id: str) -> Optional[ModelPrice]:
    if model_id in prices:
        return prices[model_id]
    for prefix in _LIST_KEY_PREFIXES:
        entry = cost_map.get(prefix + model_id)
        if isinstance(entry, dict) and not entry.get("base_model"):
            return _price(entry)
    return None


def price_table(cost_map: dict, model_ids) -> Dict[str, ModelPrice]:
    """The price of each of `model_ids` the map knows."""
    prices = prices_from(cost_map)
    table = {}
    for model_id in model_ids:
        price = price_of(prices, cost_map, model_id)
        if price is not None:
            table[model_id] = price
    return table
