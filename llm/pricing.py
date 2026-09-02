"""Prices, the cost formula and the cost-basis precedence (REQ-V13-PRC-01…03).

The module is the *implementation* half of the one interface between a fetched
price and a stored row; the type half, `CostResolver`, lives next to `Usage` in
`llm/base.py`. `make_resolver` closes over everything a price decision needs and
performs no I/O, so the agent never fetches, reads `bot_state` or computes a
price of its own.

The OpenRouter `/models` field names below were verified against
https://openrouter.ai/docs/guides/overview/models (REQ-V13-PRE-05): every model
entry carries a `pricing` object whose `prompt`, `completion` and
`input_cache_read` are USD **per token**, written as strings. An absent or
unusable field yields `None` — never a guessed value. The TypeScript SDK spells
the same fields in camelCase; that is the SDK's own mapping, not the wire
format, and parsing it here would silently price nothing.
"""

import math
from collections.abc import Iterable
from dataclasses import dataclass

import httpx

from llm.base import CostResolver, Usage

MODELS_URL = "https://openrouter.ai/api/v1/models"
MODELS_TIMEOUT_S = 20.0
TOKENS_PER_MTOK = 1_000_000

# The `pricing` keys this module reads, per REQ-V13-PRE-05.
PROMPT_FIELD = "prompt"
COMPLETION_FIELD = "completion"
CACHE_READ_FIELD = "input_cache_read"

SOURCE_OPENROUTER_LIST = "openrouter-list"
SOURCE_MANUAL = "manual"

BASIS_PROVIDER = "provider"
BASIS_LIST = "openrouter-list"
BASIS_MANUAL = "manual"
REFERENCE_PREFIX = "reference:"
REFERENCE_STALE_PREFIX = "reference-stale:"
STALE_SUFFIX = "-stale"

OPENROUTER_PROVIDER = "openrouter"


class PricingError(Exception):
    """The price list could not be fetched or understood. Never fatal: the
    caller falls through to the lower-priority bases of REQ-V13-PRC-02."""


@dataclass(frozen=True)
class Price:
    """USD per million tokens — the unit every report and every env var uses."""

    input_usd_per_mtok: float
    output_usd_per_mtok: float
    cached_input_usd_per_mtok: float | None
    source: str
    fetched_at: str


def fetch_openrouter_prices(
    client: httpx.Client,
    model_ids: Iterable[str],
    *,
    now: str = "",
    timeout_s: float = MODELS_TIMEOUT_S,
) -> dict[str, Price]:
    """The prices of `model_ids` from `GET /api/v1/models`, keyed by model id.

    A model whose entry is missing, unparsable or negative is simply absent from
    the result: half a price is worse than none. An empty `model_ids` performs
    no request at all, so a bot with nothing to price never touches the network.
    """
    wanted = {model_id for model_id in model_ids if model_id}
    if not wanted:
        return {}
    try:
        response = client.get(MODELS_URL, timeout=timeout_s)
    except httpx.HTTPError as exc:
        raise PricingError(f"models request failed: {exc.__class__.__name__}") from None
    if response.status_code != 200:
        raise PricingError(f"models request returned http {response.status_code}")
    try:
        body = response.json()
    except ValueError:
        raise PricingError("the models response is not json") from None

    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, list):
        raise PricingError("the models response carries no 'data' list")

    prices: dict[str, Price] = {}
    for entry in data:
        if not isinstance(entry, dict) or entry.get("id") not in wanted:
            continue
        raw = entry.get("pricing")
        raw = raw if isinstance(raw, dict) else {}
        input_usd = _per_mtok(raw.get(PROMPT_FIELD))
        output_usd = _per_mtok(raw.get(COMPLETION_FIELD))
        if input_usd is None or output_usd is None:
            continue
        prices[str(entry["id"])] = Price(
            input_usd_per_mtok=input_usd,
            output_usd_per_mtok=output_usd,
            cached_input_usd_per_mtok=_per_mtok(raw.get(CACHE_READ_FIELD)),
            source=SOURCE_OPENROUTER_LIST,
            fetched_at=now,
        )
    return prices


def cost_usd(usage: Usage | None, price: Price | None) -> float | None:
    """`(prompt − cached) × in + cached × cached_in + completion × out`.

    Returns `None` — never 0.0, never an exception — when there is no price or
    the provider reported no `prompt_tokens`/`completion_tokens`: a failed call
    and a partially reporting provider both store `cost_usd = NULL`. A reported
    zero, on the other hand, is a real cost of zero.
    """
    if price is None or usage is None:
        return None
    prompt, completion = usage.prompt_tokens, usage.completion_tokens
    if prompt is None or completion is None:
        return None
    # A provider that reports more cached tokens than prompt tokens must not
    # turn the uncached remainder into a negative charge.
    cached = min(max(usage.cached_tokens or 0, 0), prompt)
    cached_rate = price.cached_input_usd_per_mtok
    if cached_rate is None:
        # No published cache price means no cache discount, not a free read.
        cached_rate = price.input_usd_per_mtok
    total = (
        (prompt - cached) * price.input_usd_per_mtok
        + cached * cached_rate
        + completion * price.output_usd_per_mtok
    )
    return total / TOKENS_PER_MTOK


def make_resolver(
    cfg,
    snapshot: dict[str, Price] | None,
    *,
    snapshot_basis: str | None = None,
    stale: dict | None = None,
) -> CostResolver:
    """The strict precedence of REQ-V13-PRC-02 as a pure closure.

    Per call, the first available basis wins: (1) the provider's own reported
    cost, (2) a price fetched in this process, (3) the manual env prices,
    (4) the price persisted by an earlier run, (5) nothing.

    The basis label of a fetched price is derived per call — an OpenRouter call
    priced from the list is `openrouter-list`, any other provider priced through
    `LLM_PRICE_REF_MODEL` is `reference:<model>` — unless the caller pins one in
    `snapshot_basis` (the benchmark, which records the same label in
    `meta.pricing`). A price taken from the persisted snapshot is labelled the
    same way and then marked stale: `openrouter-list-stale`,
    `reference-stale:<model>`. An OpenRouter call whose own model is not in the
    list never borrows the reference price; it falls through to the manual
    prices instead.
    """
    fresh = dict(snapshot or {})
    persisted = _state_prices(stale)
    manual = _manual_price(cfg)
    reference_model = str(getattr(cfg, "llm_price_ref_model", "") or "")

    def resolve(
        provider: str, model: str, usage: Usage | None
    ) -> tuple[float | None, str | None]:
        if usage is not None and usage.provider_cost_usd is not None:
            return float(usage.provider_cost_usd), BASIS_PROVIDER
        found = _lookup(fresh, snapshot_basis, provider, model, reference_model)
        if found is not None:
            return _priced(usage, found[0], found[1])
        if manual is not None:
            return _priced(usage, manual, BASIS_MANUAL)
        # The persisted `basis` documents how that snapshot was obtained; the
        # label of *this* call is derived from this call, then marked stale.
        found = _lookup(persisted, None, provider, model, reference_model)
        if found is not None:
            return _priced(usage, found[0], _stale_form(found[1]))
        return None, None

    return resolve


def snapshot_to_state(
    snapshot: dict[str, Price], *, basis: str = BASIS_LIST, fetched_at: str | None = None
) -> dict:
    """The JSON-able form of a fetched snapshot, for `bot_state.pricing_json`.

    `fetched_at` belongs to the fetch, not to any one price in it, so the caller
    that performed the fetch may state it; the prices' own stamp is the default.
    """
    if fetched_at is None:
        fetched_at = next((price.fetched_at for price in snapshot.values()), "")
    return {
        "fetched_at": fetched_at,
        "basis": basis,
        "prices": {
            model: {
                "input_usd_per_mtok": price.input_usd_per_mtok,
                "output_usd_per_mtok": price.output_usd_per_mtok,
                "cached_input_usd_per_mtok": price.cached_input_usd_per_mtok,
            }
            for model, price in snapshot.items()
        },
    }


def _lookup(
    prices: dict[str, Price],
    basis_override: str | None,
    provider: str,
    model: str,
    reference_model: str,
) -> tuple[Price, str] | None:
    if not prices:
        return None
    if provider == OPENROUTER_PROVIDER:
        price = prices.get(model)
        return None if price is None else (price, basis_override or BASIS_LIST)
    price = prices.get(reference_model) if reference_model else None
    if price is None:
        return None
    return price, basis_override or f"{REFERENCE_PREFIX}{reference_model}"


def _priced(
    usage: Usage | None, price: Price, basis: str
) -> tuple[float | None, str | None]:
    """A basis labels a cost; without a cost there is nothing to label."""
    cost = cost_usd(usage, price)
    return (None, None) if cost is None else (cost, basis)


def _stale_form(basis: str) -> str:
    if basis.startswith(REFERENCE_PREFIX):
        return REFERENCE_STALE_PREFIX + basis[len(REFERENCE_PREFIX):]
    return basis + STALE_SUFFIX


def _manual_price(cfg) -> Price | None:
    """Both env prices or neither (REQ-V13-PRE-04); `load_config` refuses a half
    pair, and so does this, for a `Config` built by hand."""
    input_usd = getattr(cfg, "llm_price_input_usd_per_mtok", None)
    output_usd = getattr(cfg, "llm_price_output_usd_per_mtok", None)
    if not _is_rate(input_usd) or not _is_rate(output_usd):
        return None
    return Price(
        input_usd_per_mtok=float(input_usd),
        output_usd_per_mtok=float(output_usd),
        cached_input_usd_per_mtok=None,
        source=SOURCE_MANUAL,
        fetched_at="",
    )


def _state_prices(state: dict | None) -> dict[str, Price]:
    """The persisted snapshot, read defensively: a row written by an older
    version, or by hand, must degrade to "no stale price", never to a crash."""
    if not isinstance(state, dict):
        return {}
    raw = state.get("prices")
    if not isinstance(raw, dict):
        return {}
    fetched_at = str(state.get("fetched_at") or "")
    basis = state.get("basis")
    basis = basis if isinstance(basis, str) and basis else BASIS_LIST
    prices: dict[str, Price] = {}
    for model, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        input_usd = _rate(entry.get("input_usd_per_mtok"))
        output_usd = _rate(entry.get("output_usd_per_mtok"))
        if input_usd is None or output_usd is None:
            continue
        prices[str(model)] = Price(
            input_usd_per_mtok=input_usd,
            output_usd_per_mtok=output_usd,
            cached_input_usd_per_mtok=_rate(entry.get("cached_input_usd_per_mtok")),
            source=basis,
            fetched_at=fetched_at,
        )
    return prices


def _per_mtok(raw: object) -> float | None:
    """A per-token rate, as a string or a number, in USD per million tokens."""
    if isinstance(raw, str):
        try:
            raw = float(raw)
        except ValueError:
            return None
    rate = _rate(raw)
    return None if rate is None else rate * TOKENS_PER_MTOK


def _rate(raw: object) -> float | None:
    # `bool` is an `int` subclass; `True` is not a price.
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    return float(raw) if _is_rate(raw) else None


def _is_rate(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )
