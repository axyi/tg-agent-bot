"""spec-v1.11.0 T4: the `/model` menu and the model override
(REQ-V1110-MOD-01..-06).

Builds on `tests/test_v1110_cbq.py`'s `make_cfg`/`update`/`callback`/`process`
helpers (callback-query plumbing) and `tests/test_observability.py`'s
`NamedLLM`/`run` (the agent path, for MOD-06's `llm_calls.model` check). See
`docs/spec/spec-v1.11.0.md` sec.8 and `docs/spec/task-briefs/v1110-T4.md`.
"""

from __future__ import annotations

import logging
from pathlib import Path

import httpx

import bot
import config
import storage
from llm import build_llm_client
from tests.fakes import FakeTelegram, mock_llm_transport
from tests.test_observability import NamedLLM, run
from tests.test_v1110_cbq import USER_ID, callback, make_cfg, process, update

REPO_ROOT = Path(__file__).resolve().parent.parent


def _minimal_env(**overrides):
    env = {
        "TELEGRAM_BOT_TOKEN": "123456789:sentinel-telegram-token-value",
        "ALLOWED_TG_IDS": str(USER_ID),
        "LLM_PROVIDER": "openrouter",
        "OPENROUTER_API_KEY": "sk-or-sentinel-api-key-value",
    }
    env.update(overrides)
    return env


# --------------------------------------------------------------------------
# T-V1110-MOD-01 -- step 1: the status block and the provider keyboard.
# --------------------------------------------------------------------------


def test_t_v1110_mod_01_model_step_one(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    fake = FakeTelegram()
    process(conn, cfg, update("/model"), tg=fake)
    assert len(fake.sent) == 1
    payload = fake.sent_payloads[0]
    body = payload["text"]
    assert body.startswith("<pre>") and body.endswith("</pre>")
    inner = body[len("<pre>") : -len("</pre>")]
    assert "lmstudio" in inner
    assert "none" in inner
    assert "lmstudio=0" in inner and "openrouter=0" in inner

    keyboard = payload["reply_markup"]["inline_keyboard"]
    assert len(keyboard) == 1
    assert [b["text"] for b in keyboard[0]] == ["lmstudio", "openrouter", "auto"]
    assert [b["callback_data"] for b in keyboard[0]] == [
        "mod:prov:lmstudio",
        "mod:prov:openrouter",
        "mod:auto:-",
    ]

    # LM Studio unconfigured -> its button (and status row) absent
    cfg2 = make_cfg(tmp_path, lmstudio_base_url="", lmstudio_model="", lmstudio_models=())
    fake2 = FakeTelegram()
    process(conn, cfg2, update("/model", update_id=2), tg=fake2)
    keyboard2 = fake2.sent_payloads[0]["reply_markup"]["inline_keyboard"][0]
    assert [b["text"] for b in keyboard2] == ["openrouter", "auto"]
    inner2 = fake2.sent_payloads[0]["text"][len("<pre>") : -len("</pre>")]
    assert "lmstudio model" not in inner2


# --------------------------------------------------------------------------
# T-V1110-MOD-02 -- step 2: model buttons; selection sets two keys; back.
# --------------------------------------------------------------------------


def test_t_v1110_mod_02_model_step_two_sets_two_keys(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    fake = FakeTelegram()
    process(conn, cfg, update("/model"), tg=fake)
    message_id = 100 + len(fake.sent)

    process(conn, cfg, callback("mod:prov:openrouter", message_id=message_id, update_id=2), tg=fake)
    edited = fake.edited_payloads[-1]
    inner = edited["text"][len("<pre>") : -len("</pre>")]
    assert inner.startswith("Models for openrouter:")
    for idx, model in enumerate(cfg.openrouter_models):
        assert f"{idx}. {bot.model_display(model, limit=64)}" in inner
    keyboard = edited["reply_markup"]["inline_keyboard"]
    assert len(keyboard) == len(cfg.openrouter_models) + 1
    assert keyboard[-1] == [{"text": "← back", "callback_data": "mod:back:-"}]

    plain_step2_text = bot._model_step2_body(cfg, "openrouter")
    digest = bot._catalogue_hash(cfg.openrouter_models)
    installed = []
    selection_data = f"mod:model:1:{digest}"
    process(
        conn,
        cfg,
        callback(selection_data, text=plain_step2_text, message_id=message_id, update_id=3),
        tg=fake,
        set_provider=installed.append,
    )
    assert storage.get_state(conn, "provider_override") == "openrouter"
    assert storage.get_state(conn, "model_override:openrouter") == cfg.openrouter_models[1]
    assert installed == ["openrouter"]
    final_edit = fake.edited_payloads[-1]
    assert final_edit["message_id"] == message_id
    expected_display = bot.model_display(cfg.openrouter_models[1], limit=64)
    final_inner = final_edit["text"][len("<pre>") : -len("</pre>")]
    assert final_inner == f"Provider: openrouter, model: {expected_display}"
    assert "reply_markup" not in final_edit

    # mod:back:- restores step 1's body and keyboard
    process(conn, cfg, callback("mod:back:-", message_id=message_id, update_id=4), tg=fake)
    back_edit = fake.edited_payloads[-1]
    assert back_edit["message_id"] == message_id
    back_inner = back_edit["text"][len("<pre>") : -len("</pre>")]
    assert "openrouter" in back_inner
    assert back_edit["reply_markup"]["inline_keyboard"][0][0]["text"] == "lmstudio"


# --------------------------------------------------------------------------
# T-V1110-MOD-03 -- auto clears both keys (button and text form).
# --------------------------------------------------------------------------


def test_t_v1110_mod_03_auto_clears_both(conn, tmp_path):
    cfg = make_cfg(tmp_path)

    storage.set_state(conn, "provider_override", "openrouter")
    storage.set_state(conn, "model_override:openrouter", "o-alt")
    storage.set_state(conn, "model_override:lmstudio", "m-default")
    installed = []
    fake = FakeTelegram()
    process(
        conn,
        cfg,
        callback("mod:auto:-", message_id=77, update_id=1),
        tg=fake,
        set_provider=installed.append,
    )
    assert storage.get_state(conn, "provider_override") is None
    assert storage.get_state(conn, "model_override:openrouter") is None
    assert storage.get_state(conn, "model_override:lmstudio") is None
    assert installed == [None]
    edited = fake.edited_payloads[-1]
    assert edited["message_id"] == 77
    assert edited["text"] == "<pre>Provider override cleared.</pre>"
    assert "reply_markup" not in edited

    # text form -- clears both, leaves an unrelated key untouched
    storage.set_state(conn, "provider_override", "openrouter")
    storage.set_state(conn, "model_override:openrouter", "o-alt")
    storage.set_state(conn, "model_override:lmstudio", "m-default")
    storage.set_state(conn, "some_other_key", "kept")
    installed2 = []
    tg2, _llm2, _runner2 = process(
        conn,
        cfg,
        update("/model auto", update_id=2),
        set_provider=installed2.append,
    )
    assert tg2.sent == [(USER_ID, "Provider override cleared.")]
    assert storage.get_state(conn, "provider_override") is None
    assert storage.get_state(conn, "model_override:openrouter") is None
    assert storage.get_state(conn, "model_override:lmstudio") is None
    assert storage.get_state(conn, "some_other_key") == "kept"
    assert installed2 == [None]


# --------------------------------------------------------------------------
# T-V1110-MOD-04 -- the text form, kept for scripts and tests.
# --------------------------------------------------------------------------


def test_t_v1110_mod_04_model_text_form(conn, tmp_path):
    cfg = make_cfg(tmp_path)

    tg, _llm, _runner = process(conn, cfg, update("/model lmstudio", update_id=1))
    assert tg.sent == [(USER_ID, "Provider switched to lmstudio.")]
    assert storage.get_state(conn, "model_override:lmstudio") is None

    tg2, _llm2, _runner2 = process(conn, cfg, update("/model openrouter o-alt", update_id=2))
    display = bot.model_display("o-alt", limit=64)
    assert tg2.sent == [(USER_ID, f"Provider switched to openrouter, model: {display}.")]
    assert storage.get_state(conn, "provider_override") == "openrouter"
    assert storage.get_state(conn, "model_override:openrouter") == "o-alt"

    tg3, _llm3, _runner3 = process(conn, cfg, update("/model openrouter nope", update_id=3))
    assert tg3.sent == [(USER_ID, "Unknown model for openrouter; see /model")]

    tg4, _llm4, _runner4 = process(conn, cfg, update("/model bogus", update_id=4))
    assert tg4.sent == [(USER_ID, bot.MODEL_USAGE_REPLY)]

    tg5, _llm5, _runner5 = process(conn, cfg, update("/model a b c", update_id=5))
    assert tg5.sent == [(USER_ID, bot.MODEL_USAGE_REPLY)]

    # three arguments is refused even when the first two would otherwise be
    # accepted (a slice-based dispatch could silently drop the third one).
    tg6, _llm6, _runner6 = process(conn, cfg, update("/model openrouter o-alt extra", update_id=6))
    assert tg6.sent == [(USER_ID, bot.MODEL_USAGE_REPLY)]

    assert bot.MODEL_USAGE_REPLY == "Usage: /model [lmstudio|openrouter|auto] [<model>]"


# --------------------------------------------------------------------------
# T-V1110-MOD-05 -- the catalogue is an env allowlist.
# --------------------------------------------------------------------------


def test_t_v1110_mod_05_catalogue_from_env():
    env = _minimal_env(OPENROUTER_MODELS=" b, a ,b,", OPENROUTER_MODEL="a")
    cfg = config.load_config(env, load_env_file=False)
    assert cfg.openrouter_models == ("a", "b")

    env2 = _minimal_env(OPENROUTER_MODEL="a")
    cfg2 = config.load_config(env2, load_env_file=False)
    assert cfg2.openrouter_models == ("a",)

    env3 = _minimal_env(OPENROUTER_MODEL="c", OPENROUTER_MODELS="a,b")
    cfg3 = config.load_config(env3, load_env_file=False)
    assert cfg3.openrouter_models == ("c", "a", "b")

    # an empty default (LLM_PROVIDER=lmstudio here, so OPENROUTER_MODEL is
    # legitimately never set) -- the catalogue is empty regardless of
    # OPENROUTER_MODELS, since there is nothing to fall back to.
    env4 = {
        "TELEGRAM_BOT_TOKEN": "123456789:sentinel-token-for-mod05b",
        "ALLOWED_TG_IDS": str(USER_ID),
        "LLM_PROVIDER": "lmstudio",
        "LMSTUDIO_BASE_URL": "http://localhost:1234/v1",
        "LMSTUDIO_MODEL": "local-model",
        "OPENROUTER_MODELS": "a,b",
    }
    cfg4 = config.load_config(env4, load_env_file=False)
    assert cfg4.openrouter_models == ()

    content = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    assert "LMSTUDIO_MODELS=" in content
    assert "OPENROUTER_MODELS=" in content
    for line in content.splitlines():
        if line.startswith(("LMSTUDIO_MODELS=", "OPENROUTER_MODELS=")):
            idx = content.index(line)
            preceding = content[:idx].splitlines()[-1]
            assert preceding.startswith("#"), "expected a one-line comment above " + line


# --------------------------------------------------------------------------
# T-V1110-MOD-06 -- the override reaches the client (negative).
# --------------------------------------------------------------------------


def test_t_v1110_mod_06_override_reaches_client(conn, tmp_path):
    cfg = make_cfg(tmp_path, openrouter_model="a", openrouter_models=("a", "b"))
    storage.set_state(conn, "model_override:openrouter", "b")

    def handler(_request):
        return httpx.Response(200, json={})

    with httpx.Client(transport=mock_llm_transport(handler)) as http:
        raw_model = bot.load_model_override(conn, "openrouter")
        assert raw_model == "b"
        client = build_llm_client(cfg, client=http, override="openrouter", model=raw_model)
        assert client.describe() == ("openrouter", "b")

        # a stale override -- reseeded to a value outside the catalogue --
        # is ignored, falling back to the configured default.
        storage.set_state(conn, "model_override:openrouter", "nope")
        resolved = bot._effective_model_override(conn, cfg, "openrouter")
        assert resolved is None
        client2 = build_llm_client(cfg, client=http, override="openrouter", model=resolved)
        assert client2.describe() == ("openrouter", cfg.openrouter_model)

    storage.set_state(conn, "model_override:openrouter", "b")
    _reply, _llm, _conv = run(conn, [], llm=NamedLLM("openrouter", "b"))
    row = conn.execute("SELECT provider, model FROM llm_calls ORDER BY id DESC LIMIT 1").fetchone()
    assert row["provider"] == "openrouter"
    assert row["model"] == "b"


# --------------------------------------------------------------------------
# T-V1110-MOD-07 -- the catalogue is bounded at 20 entries.
# --------------------------------------------------------------------------


def test_t_v1110_mod_07_catalogue_bounded_at_20(conn, tmp_path, caplog):
    entries = [f"m{i}" for i in range(25)]
    env = _minimal_env(OPENROUTER_MODEL=entries[0], OPENROUTER_MODELS=",".join(entries))
    with caplog.at_level(logging.WARNING):
        cfg = config.load_config(env, load_env_file=False)
    assert len(cfg.openrouter_models) == 20
    assert cfg.openrouter_models[0] == entries[0]

    messages = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    dropped_msgs = [m for m in messages if "dropped" in m]
    assert len(dropped_msgs) == 1
    assert "5" in dropped_msgs[0]
    assert not any(entries[i] in dropped_msgs[0] for i in range(20, 25))

    cfg_full = make_cfg(
        tmp_path, openrouter_model=entries[0], openrouter_models=cfg.openrouter_models
    )
    fake = FakeTelegram()
    process(conn, cfg_full, update("/model"), tg=fake)
    message_id = 100 + len(fake.sent)
    process(
        conn,
        cfg_full,
        callback("mod:prov:openrouter", message_id=message_id, update_id=2),
        tg=fake,
    )
    edited = fake.edited_payloads[-1]
    inner = edited["text"][len("<pre>") : -len("</pre>")]
    lines = inner.split("\n")
    model_lines = [line for line in lines if line and line[0].isdigit()]
    assert len(model_lines) == 20
    keyboard = edited["reply_markup"]["inline_keyboard"]
    assert len(keyboard) == 21  # 20 models + the back row
    assert bot.utf16_length(inner) <= 4096


# --------------------------------------------------------------------------
# T-V1110-MOD-08 -- a catalogue reordered between render and click is stale
# (negative).
# --------------------------------------------------------------------------


def test_t_v1110_mod_08_reordered_catalogue_is_stale(conn, tmp_path):
    cfg_v1 = make_cfg(tmp_path, openrouter_model="a", openrouter_models=("a", "b", "c"))
    fake = FakeTelegram()
    process(conn, cfg_v1, update("/model"), tg=fake)
    message_id = 100 + len(fake.sent)
    process(
        conn, cfg_v1, callback("mod:prov:openrouter", message_id=message_id, update_id=2), tg=fake
    )
    old_digest = bot._catalogue_hash(cfg_v1.openrouter_models)
    old_step2_text = bot._model_step2_body(cfg_v1, "openrouter")
    selection_data = f"mod:model:1:{old_digest}"

    cfg_v2 = make_cfg(tmp_path, openrouter_model="a", openrouter_models=("c", "b", "a"))
    installed = []
    process(
        conn,
        cfg_v2,
        callback(selection_data, text=old_step2_text, message_id=message_id, update_id=3),
        tg=fake,
        set_provider=installed.append,
    )
    assert fake.callback_answers[-1]["text"] == bot.CALLBACK_EXPIRED_REPLY
    assert installed == []
    assert storage.get_state(conn, "provider_override") is None
    assert not any("Provider:" in p["text"] for p in fake.edited_payloads)

    # the unchanged catalogue is accepted
    process(
        conn,
        cfg_v1,
        callback(selection_data, text=old_step2_text, message_id=message_id, update_id=4),
        tg=fake,
        set_provider=installed.append,
    )
    assert storage.get_state(conn, "provider_override") == "openrouter"
    assert installed == ["openrouter"]

    assert bot._catalogue_hash(["a\nb", "c"]) != bot._catalogue_hash(["a", "b\nc"])


# --------------------------------------------------------------------------
# T-V1110-MOD-09 -- model_display in rows and buttons; a sentinel secret
# and control characters never survive (negative).
# --------------------------------------------------------------------------


def test_t_v1110_mod_09_display_form_in_rows_and_buttons(conn, tmp_path):
    sentinel = "CANARY-" + "Q" * 20  # 27 raw chars, well above MIN_SECRET_LENGTH
    config.register_secret(sentinel)
    hostile = "vendor/x\ny\x00z\x07w"

    cfg = make_cfg(
        tmp_path,
        openrouter_model="o-default",
        openrouter_models=("o-default", sentinel, hostile),
    )
    fake = FakeTelegram()
    process(conn, cfg, update("/model"), tg=fake)
    message_id = 100 + len(fake.sent)
    process(conn, cfg, callback("mod:prov:openrouter", message_id=message_id, update_id=2), tg=fake)
    edited = fake.edited_payloads[-1]
    inner = edited["text"][len("<pre>") : -len("</pre>")]
    assert sentinel not in inner
    assert config.REDACTION in inner
    assert hostile not in inner

    lines = inner.split("\n")
    model_lines = [line for line in lines if line and line[0].isdigit()]
    assert len(model_lines) == 3
    for line in model_lines:
        assert "\x00" not in line and "\x07" not in line

    keyboard = edited["reply_markup"]["inline_keyboard"]
    model_buttons = [row[0] for row in keyboard[:-1]]
    assert len(model_buttons) == 3
    for button in model_buttons:
        assert sentinel not in button["text"]
        assert "\x00" not in button["text"] and "\x07" not in button["text"]
        assert "\n" not in button["text"]
    assert config.REDACTION in model_buttons[1]["text"]

    digest = bot._catalogue_hash(cfg.openrouter_models)
    plain_text = bot._model_step2_body(cfg, "openrouter")
    process(
        conn,
        cfg,
        callback(f"mod:model:2:{digest}", text=plain_text, message_id=message_id, update_id=3),
        tg=fake,
    )
    final = fake.edited_payloads[-1]
    assert hostile not in final["text"]
    assert "\x00" not in final["text"] and "\x07" not in final["text"]
    assert "reply_markup" not in final
    assert storage.get_state(conn, "model_override:openrouter") == hostile
    assert cfg.openrouter_models == ("o-default", sentinel, hostile)
