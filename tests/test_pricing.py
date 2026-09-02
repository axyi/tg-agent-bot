"""Pricing and cost — spec-v1.3 section 6.3 (REQ-V13-PRC-01…03), section 11.3.

Offline throughout: the OpenRouter `/models` payload always comes from an
`httpx.MockTransport`, never from the network — `conftest.py` fails any real
request. The field names parsed here (`pricing.prompt`, `pricing.completion`,
`pricing.input_cache_read`, USD **per token**, as strings) are the wire schema
of https://openrouter.ai/docs/guides/overview/models, verified per
REQ-V13-PRE-05; the TypeScript SDK spells the same fields in camelCase, which
is not what the HTTP endpoint returns.
"""

import json

import httpx
import pytest

import agent
import bot
import config
import storage
from llm import pricing
from llm.base import Usage
from llm.pricing import Price

NOW = "2026-09-02T10:00:00Z"
EARLIER = "2026-08-01T09:00:00Z"
USER_ID = 424242
TOKEN = "123456789:sentinel-telegram-token-for-pricing-tests"
BIG = "vendor/big-model"
REF = "vendor/reference-model"
OTHER = "vendor/other-model"

# 3 / 15 / 0.3 USD per million tokens, written the way the endpoint writes them.
PROMPT_PER_TOKEN = "0.000003"
COMPLETION_PER_TOKEN = "0.000015"
CACHE_READ_PER_TOKEN = "0.0000003"

USAGE = Usage(prompt_tokens=1000, completion_tokens=200, total_tokens=1200)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def model_entry(model_id, **overrides):
    prices = {
        "prompt": PROMPT_PER_TOKEN,
        "completion": COMPLETION_PER_TOKEN,
        "input_cache_read": CACHE_READ_PER_TOKEN,
    }
    prices.update(overrides)
    prices = {name: value for name, value in prices.items() if value is not None}
    return {"id": model_id, "name": model_id.upper(), "pricing": prices}


def models_client(payload, *, status=200, seen=None, raises=None):
    def handler(request):
        if seen is not None:
            seen.append(request)
        if raises is not None:
            raise raises
        if isinstance(payload, str):
            return httpx.Response(status, text=payload)
        return httpx.Response(status, json=payload)

    return httpx.Client(transport=httpx.MockTransport(handler))


def price(input_usd=3.0, output_usd=15.0, cached=0.3, *, fetched_at=NOW, source="openrouter-list"):
    return Price(
        input_usd_per_mtok=input_usd,
        output_usd_per_mtok=output_usd,
        cached_input_usd_per_mtok=cached,
        source=source,
        fetched_at=fetched_at,
    )


def snapshot(**overrides):
    prices = {BIG: price(), REF: price(2.0, 10.0, None)}
    prices.update(overrides)
    return prices


def stale_state(models=(BIG, REF), *, basis="openrouter-list", fetched_at=EARLIER):
    return {
        "fetched_at": fetched_at,
        "basis": basis,
        "prices": {
            model: {
                "input_usd_per_mtok": 1.0,
                "output_usd_per_mtok": 5.0,
                "cached_input_usd_per_mtok": None,
            }
            for model in models
        },
    }


def make_cfg(tmp_path, **overrides):
    fields = {
        "telegram_bot_token": TOKEN,
        "allowed_tg_ids": frozenset({USER_ID}),
        "llm_provider": "lmstudio",
        "lmstudio_base_url": "http://localhost:1234/v1",
        "lmstudio_model": "small",
        "openrouter_api_key": "",
        "openrouter_model": "",
        "llm_timeout_s": 120.0,
        "exec_workdir": tmp_path / "sandbox",
        "db_path": tmp_path / "test.db",
        "audit_log_path": tmp_path / "exec_audit.jsonl",
    }
    fields.update(overrides)
    return config.Config(**fields)


class RecordingTelegram:
    def __init__(self):
        self.sent = []

    def send_message(self, chat_id, text):
        self.sent.append((chat_id, text))

    def edit_message_text(self, chat_id, message_id, text):
        return None

    def delete_message(self, chat_id, message_id):
        return None


def base_env(**overrides):
    env = {
        "TELEGRAM_BOT_TOKEN": TOKEN,
        "ALLOWED_TG_IDS": str(USER_ID),
        "LMSTUDIO_MODEL": "small",
    }
    env.update(overrides)
    return {name: value for name, value in env.items() if value is not None}


# --------------------------------------------------------------------------
# REQ-V13-PRC-01 — the `/models` payload
# --------------------------------------------------------------------------

def test_prc01_fetch_converts_per_token_strings_to_per_million():
    seen = []
    client = models_client(
        {"data": [model_entry(OTHER), model_entry(BIG), model_entry(REF)]}, seen=seen
    )
    prices = pricing.fetch_openrouter_prices(client, [BIG, REF], now=NOW)

    assert seen[0].method == "GET"
    assert str(seen[0].url) == pricing.MODELS_URL
    # Only what was asked for: the third model is parsed by nobody.
    assert set(prices) == {BIG, REF}
    assert prices[BIG].input_usd_per_mtok == pytest.approx(3.0)
    assert prices[BIG].output_usd_per_mtok == pytest.approx(15.0)
    assert prices[BIG].cached_input_usd_per_mtok == pytest.approx(0.3)
    assert prices[BIG].fetched_at == NOW
    assert prices[BIG].source == pricing.SOURCE_OPENROUTER_LIST


def test_prc01_absent_cache_price_stays_none():
    """REQ-V13-PRE-05: an absent field is `None`, never a guessed value."""
    client = models_client({"data": [model_entry(BIG, input_cache_read=None)]})
    prices = pricing.fetch_openrouter_prices(client, [BIG], now=NOW)
    assert prices[BIG].cached_input_usd_per_mtok is None


@pytest.mark.parametrize("entry", [
    {"prompt": None},                     # the field is absent
    {"completion": None},
    {"prompt": "free"},                   # a string that is not a number
    {"completion": "-0.000015"},          # a negative rate
    {"prompt": ["0.000003"]},             # the wrong JSON type
])
def test_prc01_unusable_entries_are_skipped(entry):
    client = models_client({"data": [model_entry(BIG, **entry), model_entry(REF)]})
    prices = pricing.fetch_openrouter_prices(client, [BIG, REF], now=NOW)
    assert BIG not in prices
    assert REF in prices


def test_prc01_numeric_rates_are_accepted():
    client = models_client({"data": [model_entry(BIG, prompt=0.000003, completion=0.000015)]})
    prices = pricing.fetch_openrouter_prices(client, [BIG], now=NOW)
    assert prices[BIG].input_usd_per_mtok == pytest.approx(3.0)


def test_prc01_no_model_ids_makes_no_request():
    """A bot with neither an OpenRouter model nor a reference model prices
    nothing, so startup does not touch the network at all."""
    seen = []
    client = models_client({"data": [model_entry(BIG)]}, seen=seen)
    assert pricing.fetch_openrouter_prices(client, [], now=NOW) == {}
    assert seen == []


@pytest.mark.parametrize("kwargs", [
    {"payload": {"data": [], "error": "nope"}, "status": 500},
    {"payload": "not json at all"},
    {"payload": {"data": "not a list"}},
    {"payload": {"data": []}, "raises": httpx.ConnectError("refused")},
])
def test_prc01_fetch_failures_raise_pricing_error(kwargs):
    client = models_client(**kwargs)
    with pytest.raises(pricing.PricingError):
        pricing.fetch_openrouter_prices(client, [BIG], now=NOW)


# --------------------------------------------------------------------------
# REQ-V13-PRC-01 — the cost formula
# --------------------------------------------------------------------------

def test_prc01_cost_uses_the_cache_price_for_cached_tokens():
    usage = Usage(prompt_tokens=1000, completion_tokens=200, cached_tokens=400)
    # (1000 - 400) * 3 + 400 * 0.3 + 200 * 15, per million.
    expected = (600 * 3.0 + 400 * 0.3 + 200 * 15.0) / 1_000_000
    assert pricing.cost_usd(usage, price()) == pytest.approx(expected)


def test_prc01_cost_falls_back_to_the_input_price_without_a_cache_price():
    usage = Usage(prompt_tokens=1000, completion_tokens=200, cached_tokens=400)
    expected = (1000 * 3.0 + 200 * 15.0) / 1_000_000
    assert pricing.cost_usd(usage, price(cached=None)) == pytest.approx(expected)


def test_prc01_cost_counts_the_completion_tokens():
    """Dropping the output term is mutation `v13-cost-drops-output`."""
    cheap_output = pricing.cost_usd(USAGE, price(3.0, 0.0, None))
    dear_output = pricing.cost_usd(USAGE, price(3.0, 15.0, None))
    assert cheap_output == pytest.approx(1000 * 3.0 / 1_000_000)
    assert dear_output == pytest.approx((1000 * 3.0 + 200 * 15.0) / 1_000_000)
    assert dear_output > cheap_output


def test_prc01_cost_treats_a_missing_cached_count_as_zero():
    assert pricing.cost_usd(USAGE, price()) == pytest.approx(
        (1000 * 3.0 + 200 * 15.0) / 1_000_000
    )


@pytest.mark.parametrize("usage", [
    None,
    Usage(prompt_tokens=None, completion_tokens=200),
    Usage(prompt_tokens=1000, completion_tokens=None),
])
def test_prc01_cost_is_none_when_usage_is_incomplete(usage):
    """A failed call or a partial usage object stores NULL, never 0.0."""
    assert pricing.cost_usd(usage, price()) is None


def test_prc01_cost_is_none_without_a_price():
    assert pricing.cost_usd(USAGE, None) is None


def test_prc01_zero_tokens_cost_zero_not_none():
    """The other direction of mutation `v13-cost-none-as-zero`: a reported zero
    is a real cost of 0.0, and only a *missing* count is `None`."""
    zero = pricing.cost_usd(Usage(prompt_tokens=0, completion_tokens=0), price())
    assert zero == 0.0
    assert zero is not None


# --------------------------------------------------------------------------
# REQ-V13-PRC-02 — the basis precedence, one test per step
#
# Every test leaves the lower-priority sources in place, so a resolver that
# reordered the steps would answer differently.
# --------------------------------------------------------------------------

def full_resolver(tmp_path, **cfg_overrides):
    fields = {
        "openrouter_model": BIG,
        "llm_price_ref_model": REF,
        "llm_price_input_usd_per_mtok": 100.0,
        "llm_price_output_usd_per_mtok": 500.0,
    }
    fields.update(cfg_overrides)
    cfg = make_cfg(tmp_path, **fields)
    return pricing.make_resolver(
        cfg, snapshot(), snapshot_basis=None, stale=stale_state()
    )


def test_prc02_step1_provider_cost_wins(tmp_path):
    resolve = full_resolver(tmp_path)
    usage = Usage(prompt_tokens=1000, completion_tokens=200, provider_cost_usd=0.0042)
    assert resolve("openrouter", BIG, usage) == (0.0042, "provider")


def test_prc02_step2_fresh_list_wins_over_manual_and_stale(tmp_path):
    resolve = full_resolver(tmp_path)
    cost, basis = resolve("openrouter", BIG, USAGE)
    assert basis == "openrouter-list"
    assert cost == pytest.approx((1000 * 3.0 + 200 * 15.0) / 1_000_000)


def test_prc02_step2_reference_price_for_a_local_call(tmp_path):
    resolve = full_resolver(tmp_path)
    cost, basis = resolve("lmstudio", "small", USAGE)
    assert basis == f"reference:{REF}"
    assert cost == pytest.approx((1000 * 2.0 + 200 * 10.0) / 1_000_000)


def test_prc02_a_local_call_without_a_reference_model_skips_the_list(tmp_path):
    resolve = full_resolver(tmp_path, llm_price_ref_model="")
    cost, basis = resolve("lmstudio", "small", USAGE)
    assert basis == "manual"
    assert cost == pytest.approx((1000 * 100.0 + 200 * 500.0) / 1_000_000)


def test_prc02_an_unlisted_openrouter_model_never_borrows_the_reference_price(tmp_path):
    resolve = full_resolver(tmp_path)
    assert resolve("openrouter", OTHER, USAGE)[1] == "manual"


def test_prc02_step3_manual_wins_over_stale(tmp_path):
    cfg = make_cfg(
        tmp_path,
        openrouter_model=BIG,
        llm_price_input_usd_per_mtok=100.0,
        llm_price_output_usd_per_mtok=500.0,
    )
    resolve = pricing.make_resolver(cfg, None, snapshot_basis=None, stale=stale_state())
    cost, basis = resolve("openrouter", BIG, USAGE)
    assert basis == "manual"
    assert cost == pytest.approx((1000 * 100.0 + 200 * 500.0) / 1_000_000)


def test_prc02_manual_price_of_zero_is_a_price(tmp_path):
    cfg = make_cfg(
        tmp_path,
        llm_price_input_usd_per_mtok=0.0,
        llm_price_output_usd_per_mtok=0.0,
    )
    resolve = pricing.make_resolver(cfg, None, snapshot_basis=None, stale=stale_state())
    assert resolve("openrouter", BIG, USAGE) == (0.0, "manual")


def test_prc02_half_a_manual_pair_is_no_price(tmp_path):
    """`load_config` refuses the half pair; the resolver refuses it too rather
    than pricing an input at a made-up output rate."""
    cfg = make_cfg(tmp_path, openrouter_model=BIG, llm_price_input_usd_per_mtok=100.0)
    resolve = pricing.make_resolver(cfg, None, snapshot_basis=None, stale=None)
    assert resolve("openrouter", BIG, USAGE) == (None, None)


def test_prc02_step4_stale_list_is_labelled_stale(tmp_path):
    cfg = make_cfg(tmp_path, openrouter_model=BIG)
    resolve = pricing.make_resolver(cfg, None, snapshot_basis=None, stale=stale_state())
    cost, basis = resolve("openrouter", BIG, USAGE)
    assert basis == "openrouter-list-stale"
    assert cost == pytest.approx((1000 * 1.0 + 200 * 5.0) / 1_000_000)


def test_prc02_step4_stale_reference_keeps_the_model_in_the_label(tmp_path):
    cfg = make_cfg(tmp_path, llm_price_ref_model=REF)
    resolve = pricing.make_resolver(cfg, None, snapshot_basis=None, stale=stale_state())
    cost, basis = resolve("lmstudio", "small", USAGE)
    assert basis == f"reference-stale:{REF}"
    assert cost == pytest.approx((1000 * 1.0 + 200 * 5.0) / 1_000_000)


@pytest.mark.parametrize("stale", [
    None,
    {},
    {"prices": "not an object"},
    {"prices": {BIG: {"input_usd_per_mtok": "free", "output_usd_per_mtok": 5.0}}},
])
def test_prc02_step5_no_basis_at_all(tmp_path, stale):
    cfg = make_cfg(tmp_path, openrouter_model=BIG)
    resolve = pricing.make_resolver(cfg, None, snapshot_basis=None, stale=stale)
    assert resolve("openrouter", BIG, USAGE) == (None, None)


def test_prc02_a_priced_call_without_usage_stores_neither_cost_nor_basis(tmp_path):
    """A failed call reaches the resolver with `usage=None`; a basis without a
    cost would label a NULL."""
    resolve = full_resolver(tmp_path)
    assert resolve("openrouter", BIG, None) == (None, None)


def test_prc02_snapshot_basis_overrides_the_derived_label(tmp_path):
    cfg = make_cfg(tmp_path, openrouter_model=BIG, llm_price_ref_model=REF)
    resolve = pricing.make_resolver(
        cfg, snapshot(), snapshot_basis=f"reference:{REF}", stale=None
    )
    assert resolve("openrouter", BIG, USAGE)[1] == f"reference:{REF}"
    assert resolve("lmstudio", "small", USAGE)[1] == f"reference:{REF}"


def test_prc02_the_stale_label_follows_the_call_not_the_persisted_note(tmp_path):
    """`basis` in the persisted row records how that snapshot was fetched; the
    label of a call is what pricing *this* call from it amounts to."""
    cfg = make_cfg(tmp_path, openrouter_model=BIG, llm_price_ref_model=REF)
    resolve = pricing.make_resolver(
        cfg, None, snapshot_basis=None, stale=stale_state(basis=f"reference:{REF}")
    )
    assert resolve("openrouter", BIG, USAGE)[1] == "openrouter-list-stale"
    assert resolve("lmstudio", "small", USAGE)[1] == f"reference-stale:{REF}"


def test_prc02_the_resolver_is_a_pure_closure(tmp_path):
    """No I/O, no global state: the same call answers the same twice, and the
    snapshot it closes over is its own copy."""
    prices = snapshot()
    resolve = pricing.make_resolver(
        make_cfg(tmp_path, openrouter_model=BIG), prices, snapshot_basis=None, stale=None
    )
    first = resolve("openrouter", BIG, USAGE)
    prices.clear()
    assert resolve("openrouter", BIG, USAGE) == first


def test_prc02_snapshot_to_state_round_trips(tmp_path):
    state = pricing.snapshot_to_state(snapshot(), basis="openrouter-list")
    assert state["fetched_at"] == NOW
    assert state["basis"] == "openrouter-list"
    assert state["prices"][REF]["cached_input_usd_per_mtok"] is None
    # Whatever the persist wrote, the resolver must read back as a stale price.
    cfg = make_cfg(tmp_path, openrouter_model=BIG)
    resolve = pricing.make_resolver(cfg, None, snapshot_basis=None, stale=json.loads(
        json.dumps(state)
    ))
    cost, basis = resolve("openrouter", BIG, USAGE)
    assert basis == "openrouter-list-stale"
    assert cost == pytest.approx((1000 * 3.0 + 200 * 15.0) / 1_000_000)


# --------------------------------------------------------------------------
# REQ-V13-PRC-02 — the single `bot.py` wiring
# --------------------------------------------------------------------------

def test_prc02_startup_fetch_persists_the_snapshot(conn, tmp_path):
    cfg = make_cfg(tmp_path, openrouter_model=BIG, llm_price_ref_model=REF)
    client = models_client({"data": [model_entry(BIG), model_entry(REF)]})
    resolve = bot.build_cost_resolver(conn, cfg, client, now=NOW)

    assert resolve("openrouter", BIG, USAGE)[1] == "openrouter-list"
    state = json.loads(storage.get_state(conn, bot.PRICING_STATE_KEY))
    assert state["fetched_at"] == NOW
    assert state["basis"] == "openrouter-list"
    assert set(state["prices"]) == {BIG, REF}
    assert state["prices"][BIG]["input_usd_per_mtok"] == pytest.approx(3.0)


def test_prc02_a_failed_startup_fetch_falls_through_to_the_persisted_price(conn, tmp_path, caplog):
    storage.set_state(conn, bot.PRICING_STATE_KEY, json.dumps(stale_state()))
    cfg = make_cfg(tmp_path, openrouter_model=BIG)
    client = models_client({"data": []}, status=503)
    with caplog.at_level("WARNING", logger="bot"):
        resolve = bot.build_cost_resolver(conn, cfg, client, now=NOW)

    assert resolve("openrouter", BIG, USAGE)[1] == "openrouter-list-stale"
    assert any("price" in record.message.lower() for record in caplog.records)
    # The failed fetch left the persisted snapshot alone.
    assert json.loads(storage.get_state(conn, bot.PRICING_STATE_KEY))["fetched_at"] == EARLIER


def test_prc02_a_startup_without_any_priceable_model_makes_no_request(conn, tmp_path):
    seen = []
    client = models_client({"data": [model_entry(BIG)]}, seen=seen)
    resolve = bot.build_cost_resolver(conn, make_cfg(tmp_path), client, now=NOW)
    assert seen == []
    assert resolve("lmstudio", "small", USAGE) == (None, None)
    assert storage.get_state(conn, bot.PRICING_STATE_KEY) is None


def test_prc02_a_corrupt_persisted_snapshot_is_ignored(conn, tmp_path):
    storage.set_state(conn, bot.PRICING_STATE_KEY, "{not json")
    cfg = make_cfg(tmp_path, openrouter_model=BIG)
    client = models_client({"data": []}, status=500)
    resolve = bot.build_cost_resolver(conn, cfg, client, now=NOW)
    assert resolve("openrouter", BIG, USAGE) == (None, None)


def test_prc02_the_resolver_reaches_run_agent(conn, tmp_path, monkeypatch):
    seen = {}

    def fake_run_agent(**kwargs):
        seen.update(kwargs)
        return "ok"

    monkeypatch.setattr(agent, "run_agent", fake_run_agent)
    sentinel = pricing.make_resolver(make_cfg(tmp_path), None, snapshot_basis=None, stale=None)
    bot.process_update(
        {
            "update_id": 1,
            "message": {
                "message_id": 1, "date": 0,
                "chat": {"id": USER_ID, "type": "private"},
                "from": {"id": USER_ID, "is_bot": False},
                "text": "hello",
            },
        },
        conn=conn, tg=RecordingTelegram(), cfg=make_cfg(tmp_path), llm=object(),
        skills={}, runner=None, bot_username="ThisBot", resolve_cost=sentinel,
    )
    assert seen["resolve_cost"] is sentinel


@pytest.mark.parametrize("command", ["/new", "/summary"])
def test_prc02_the_resolver_reaches_the_summarizer(conn, tmp_path, monkeypatch, command):
    seen = {}

    def fake_summarize(conn_, conv_id, llm, cfg, *, resolve_cost=None):
        seen["resolve_cost"] = resolve_cost
        return None

    monkeypatch.setattr(agent, "summarize_conversation", fake_summarize)
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv, "one")
    storage.add_assistant_message(conn, conv, "two")
    sentinel = pricing.make_resolver(make_cfg(tmp_path), None, snapshot_basis=None, stale=None)
    bot.process_update(
        {
            "update_id": 1,
            "message": {
                "message_id": 1, "date": 0,
                "chat": {"id": USER_ID, "type": "private"},
                "from": {"id": USER_ID, "is_bot": False},
                "text": command,
            },
        },
        conn=conn, tg=RecordingTelegram(), cfg=make_cfg(tmp_path), llm=object(),
        skills={}, runner=None, bot_username="ThisBot", resolve_cost=sentinel,
    )
    assert seen["resolve_cost"] is sentinel


def test_prc02_poll_loop_hands_the_resolver_down(conn, tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(bot, "process_update", lambda update, **kwargs: seen.update(kwargs))
    monkeypatch.setattr(bot, "_shutdown", False)
    sentinel = pricing.make_resolver(make_cfg(tmp_path), None, snapshot_basis=None, stale=None)

    class OneBatch:
        def __init__(self):
            self.batches = [[{"update_id": 1}]]

        def get_updates(self, offset):
            if not self.batches:
                # `poll_loop` treats it as the shutdown signal it is.
                raise KeyboardInterrupt
            return self.batches.pop()

    bot.poll_loop(
        conn=conn, tg=OneBatch(), cfg=make_cfg(tmp_path), llm=object(), skills={},
        runner=None, bot_username="ThisBot", sleep=lambda _s: None,
        resolve_cost=sentinel,
    )
    assert seen["resolve_cost"] is sentinel


# --------------------------------------------------------------------------
# REQ-V13-PRC-03 — every basis form survives storage and `/stats`
# --------------------------------------------------------------------------

@pytest.mark.parametrize("basis", [
    "provider",
    "openrouter-list",
    "openrouter-list-stale",
    f"reference:{REF}",
    f"reference-stale:{REF}",
    "manual",
])
def test_prc03_every_basis_form_is_stored_and_rendered(conn, basis):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_llm_call(
        conn, conv_id=conv, turn_id=1, purpose="agent", round_no=1, attempt=1, ts=NOW,
        provider="openrouter", model=BIG, prompt_chars=100,
        prompt_chars_by_role={"system": 100, "tools": 0, "user": 0, "assistant": 0, "tool": 0},
        messages_n=2, tools_exposed=0, latency_ms=5, prompt_tokens=1000,
        completion_tokens=200, total_tokens=1200, cost_usd=0.0123, cost_basis=basis,
    )
    stored = conn.execute("SELECT cost_basis FROM llm_calls").fetchone()["cost_basis"]
    assert stored == basis
    # Reference prices are estimates and `/stats` says so, in the OBS-07 layout.
    line = [
        row for row in bot._render_stats(conn, USER_ID).splitlines()
        if row.startswith("Est. cost:")
    ][0]
    assert line == f"Est. cost: $0.0123 | $0.0123 (basis: {basis} | {basis})"


# --------------------------------------------------------------------------
# REQ-V13-PRE-04 — the three pricing variables
# --------------------------------------------------------------------------

def test_pre04_pricing_variables_default_to_empty():
    cfg = config.load_config(env=base_env(), load_env_file=False)
    assert cfg.llm_price_ref_model == ""
    assert cfg.llm_price_input_usd_per_mtok is None
    assert cfg.llm_price_output_usd_per_mtok is None


def test_pre04_manual_prices_are_parsed_as_floats():
    cfg = config.load_config(
        env=base_env(
            LLM_PRICE_REF_MODEL=f" {REF} ",
            LLM_PRICE_INPUT_USD_PER_MTOK="3",
            LLM_PRICE_OUTPUT_USD_PER_MTOK="15.5",
        ),
        load_env_file=False,
    )
    assert cfg.llm_price_ref_model == REF
    assert cfg.llm_price_input_usd_per_mtok == pytest.approx(3.0)
    assert cfg.llm_price_output_usd_per_mtok == pytest.approx(15.5)


def test_pre04_a_free_manual_price_is_accepted():
    cfg = config.load_config(
        env=base_env(
            LLM_PRICE_INPUT_USD_PER_MTOK="0",
            LLM_PRICE_OUTPUT_USD_PER_MTOK="0",
        ),
        load_env_file=False,
    )
    assert cfg.llm_price_input_usd_per_mtok == 0.0
    assert cfg.llm_price_output_usd_per_mtok == 0.0


@pytest.mark.parametrize("env,expected", [
    ({"LLM_PRICE_INPUT_USD_PER_MTOK": "3"}, "LLM_PRICE_OUTPUT_USD_PER_MTOK"),
    ({"LLM_PRICE_OUTPUT_USD_PER_MTOK": "15"}, "LLM_PRICE_INPUT_USD_PER_MTOK"),
])
def test_pre04_manual_prices_are_both_or_neither(env, expected):
    with pytest.raises(config.ConfigError) as exc:
        config.load_config(env=base_env(**env), load_env_file=False)
    assert expected in str(exc.value)


@pytest.mark.parametrize("value", ["-1", "abc", "inf", "nan"])
def test_pre04_manual_prices_reject_unusable_numbers(value):
    with pytest.raises(config.ConfigError) as exc:
        config.load_config(
            env=base_env(
                LLM_PRICE_INPUT_USD_PER_MTOK=value,
                LLM_PRICE_OUTPUT_USD_PER_MTOK="15",
            ),
            load_env_file=False,
        )
    assert "LLM_PRICE_INPUT_USD_PER_MTOK" in str(exc.value)
