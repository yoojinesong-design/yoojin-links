"""Tests for bot.notify.Notifier: payload shapes per destination, flags, mode
tags, truncation and "never raises". requests.Session is always mocked."""
from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest
import requests

import bot.notify as notify_mod
from bot.config import NotifyConfig
from bot.notify import MAX_MESSAGE_CHARS, Notifier

DISCORD = "https://discord.com/api/webhooks/123/DISCORDSECRET"
SLACK = "https://hooks.slack.com/services/T0/B0/SLACKSECRET"
GENERIC = "https://example.org/hooks/GENERICSECRET"
TOKEN = "123456:TELEGRAMSECRET"
CHAT = "987654"
_SESSION_CLASS = requests.Session   # captured before any test patches requests.Session


def make_session(status: int = 200, text: str = "ok") -> MagicMock:
    session = MagicMock(spec=_SESSION_CLASS)
    session.post.return_value = MagicMock(status_code=status, text=text)
    return session


def make(mode: str = "paper", session: MagicMock | None = None, **cfg) -> tuple[Notifier, MagicMock]:
    session = session or make_session()
    return Notifier(NotifyConfig(**cfg), mode=mode, session=session), session


def posted(session: MagicMock) -> list[tuple[str, dict, float]]:
    return [(c.args[0], c.kwargs["json"], c.kwargs["timeout"]) for c in session.post.call_args_list]


# ---------------------------------------------------------------------------
# enabled
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("cfg, expected", [
    ({}, False),
    ({"webhook_url": DISCORD}, True),
    ({"webhook_url": ""}, False),
    ({"telegram_bot_token": TOKEN}, False),
    ({"telegram_chat_id": CHAT}, False),
    ({"telegram_bot_token": TOKEN, "telegram_chat_id": CHAT}, True),
    ({"webhook_url": SLACK, "telegram_bot_token": TOKEN, "telegram_chat_id": CHAT}, True),
])
def test_enabled_requires_a_complete_destination(cfg, expected):
    assert make(**cfg)[0].enabled is expected


def test_disabled_notifier_only_logs(caplog):
    notifier, session = make()
    with caplog.at_level(logging.INFO, logger="bot.notify"):
        notifier.send("hello")
    session.post.assert_not_called()
    assert "[PAPER] hello" in caplog.text


def test_telegram_needs_both_token_and_chat_id_to_post():
    notifier, session = make(telegram_bot_token=TOKEN)
    notifier.send("x")
    session.post.assert_not_called()


# ---------------------------------------------------------------------------
# payload shapes
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("url", [
    DISCORD,
    "https://discordapp.com/api/webhooks/1/abc",
    "https://ptb.discord.com/api/webhooks/1/abc",
    "https://canary.discord.com/api/webhooks/1/abc",
    "https://DISCORD.COM/api/webhooks/1/abc",
])
def test_discord_webhook_gets_content(url):
    notifier, session = make(webhook_url=url)
    notifier.send("bought 1 SPY")
    assert posted(session) == [(url, {"content": "[PAPER] bought 1 SPY"}, 10)]


def test_slack_webhook_gets_text():
    notifier, session = make(webhook_url=SLACK)
    notifier.send("sold BTC/KRW")
    assert posted(session) == [(SLACK, {"text": "[PAPER] sold BTC/KRW"}, 10)]


@pytest.mark.parametrize("url", [
    GENERIC,
    "https://notdiscord.com/api/webhooks/1/abc",          # look-alike domains are not Discord
    "https://discord.com.evil.example/api/webhooks/1/abc",
    "https://slack.com/api/chat.postMessage",
])
def test_other_webhooks_get_text_and_content(url):
    notifier, session = make(webhook_url=url)
    notifier.send("hi")
    assert posted(session) == [(url, {"text": "[PAPER] hi", "content": "[PAPER] hi"}, 10)]


def test_telegram_posts_send_message_with_chat_id():
    notifier, session = make(telegram_bot_token=TOKEN, telegram_chat_id=CHAT)
    notifier.send("filled")
    assert posted(session) == [(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                                {"chat_id": CHAT, "text": "[PAPER] filled"}, 10)]


def test_webhook_and_telegram_both_receive_the_message():
    notifier, session = make(webhook_url=DISCORD, telegram_bot_token=TOKEN, telegram_chat_id=CHAT)
    notifier.send("both")
    urls = [url for url, _, _ in posted(session)]
    assert urls == [DISCORD, f"https://api.telegram.org/bot{TOKEN}/sendMessage"]


# ---------------------------------------------------------------------------
# formatting
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("mode, tag", [("paper", "[PAPER]"), ("live", "[LIVE]")])
def test_messages_are_prefixed_with_the_mode(mode, tag):
    notifier, session = make(mode=mode, webhook_url=SLACK)
    notifier.send("msg")
    assert posted(session)[0][1]["text"] == f"{tag} msg"


def test_default_mode_is_paper():
    session = make_session()
    Notifier(NotifyConfig(webhook_url=SLACK), session=session).send("m")
    assert posted(session)[0][1]["text"].startswith("[PAPER] ")


def test_error_level_is_marked_in_the_message():
    notifier, session = make(mode="live", webhook_url=SLACK)
    notifier.send("broker down", level="error")
    assert posted(session)[0][1]["text"] == "[LIVE] ERROR: broker down"


@pytest.mark.parametrize("length", [MAX_MESSAGE_CHARS * 3, 5000])
def test_long_messages_are_truncated_to_1900_chars(length):
    notifier, session = make(webhook_url=GENERIC, telegram_bot_token=TOKEN, telegram_chat_id=CHAT)
    notifier.send("x" * length)
    for _, payload, _ in posted(session):
        for value in payload.values():
            if value != CHAT:
                assert len(value) == MAX_MESSAGE_CHARS and value.startswith("[PAPER] x")


def test_message_at_the_limit_is_not_truncated():
    notifier, session = make(webhook_url=SLACK)
    text = "y" * (MAX_MESSAGE_CHARS - len("[PAPER] "))
    notifier.send(text)
    assert posted(session)[0][1]["text"] == "[PAPER] " + text


def test_non_string_text_is_converted():
    notifier, session = make(webhook_url=SLACK)
    notifier.send(12.5)  # type: ignore[arg-type]
    assert posted(session)[0][1]["text"] == "[PAPER] 12.5"


# ---------------------------------------------------------------------------
# trade / error flags and logging
# ---------------------------------------------------------------------------
def test_trade_posts_when_on_trade_enabled():
    notifier, session = make(webhook_url=SLACK)
    notifier.trade("BUY 1 SPY")
    assert posted(session)[0][1] == {"text": "[PAPER] BUY 1 SPY"}


def test_trade_is_logged_but_not_pushed_when_on_trade_is_off(caplog):
    notifier, session = make(webhook_url=SLACK, on_trade=False)
    with caplog.at_level(logging.INFO, logger="bot.notify"):
        notifier.trade("BUY 1 SPY")
    session.post.assert_not_called()
    assert "BUY 1 SPY" in caplog.text


def test_error_posts_when_on_error_enabled(caplog):
    notifier, session = make(webhook_url=SLACK)
    with caplog.at_level(logging.INFO, logger="bot.notify"):
        notifier.error("rejected")
    assert posted(session)[0][1] == {"text": "[PAPER] ERROR: rejected"}
    assert any(r.levelno == logging.ERROR and "rejected" in r.getMessage() for r in caplog.records)


def test_error_is_logged_but_not_pushed_when_on_error_is_off(caplog):
    notifier, session = make(webhook_url=SLACK, on_error=False)
    with caplog.at_level(logging.INFO, logger="bot.notify"):
        notifier.error("rejected")
    session.post.assert_not_called()
    assert "rejected" in caplog.text


def test_on_trade_off_does_not_silence_errors_and_vice_versa():
    notifier, session = make(webhook_url=SLACK, on_trade=False, on_error=True)
    notifier.error("e")
    notifier.trade("t")
    assert [p["text"] for _, p, _ in posted(session)] == ["[PAPER] ERROR: e"]


@pytest.mark.parametrize("level, expected", [("info", logging.INFO), ("warning", logging.WARNING),
                                             ("error", logging.ERROR), ("bogus", logging.INFO)])
def test_send_logs_at_the_requested_level(caplog, level, expected):
    notifier, _ = make()
    with caplog.at_level(logging.DEBUG, logger="bot.notify"):
        notifier.send("lvl", level=level)
    assert [r.levelno for r in caplog.records if "lvl" in r.getMessage()] == [expected]


# ---------------------------------------------------------------------------
# never raises
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("exc", [
    requests.ConnectionError("connection refused"),
    requests.Timeout("timed out"),
    requests.RequestException("boom"),
    RuntimeError("unexpected"),
    ValueError("bad"),
])
def test_transport_errors_are_swallowed_and_logged(caplog, exc):
    session = make_session()
    session.post.side_effect = exc
    notifier, _ = make(session=session, webhook_url=SLACK, telegram_bot_token=TOKEN, telegram_chat_id=CHAT)
    with caplog.at_level(logging.WARNING, logger="bot.notify"):
        notifier.send("x")
        notifier.trade("x")
        notifier.error("x")
    # every destination was still attempted, for every call
    assert session.post.call_count == 6
    assert any(r.levelno == logging.WARNING and type(exc).__name__ in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize("status", [199, 300, 400, 401, 404, 429, 500, 503])
def test_non_2xx_responses_are_logged_as_warnings(caplog, status):
    notifier, _ = make(session=make_session(status=status, text="nope"), webhook_url=SLACK)
    with caplog.at_level(logging.WARNING, logger="bot.notify"):
        notifier.send("x")
    assert any(r.levelno == logging.WARNING and f"HTTP {status}" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize("status", [200, 201, 204, 299])
def test_2xx_responses_do_not_warn(caplog, status):
    notifier, _ = make(session=make_session(status=status), webhook_url=SLACK)
    with caplog.at_level(logging.WARNING, logger="bot.notify"):
        notifier.send("x")
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_first_destination_failure_does_not_block_the_second():
    session = make_session()
    ok = MagicMock(status_code=200, text="ok")
    session.post.side_effect = [requests.ConnectionError("down"), ok]
    notifier, _ = make(session=session, webhook_url=DISCORD, telegram_bot_token=TOKEN, telegram_chat_id=CHAT)
    notifier.send("x")
    assert session.post.call_count == 2


def test_broken_response_object_is_swallowed():
    session = make_session()
    session.post.return_value = object()   # no status_code at all
    notifier, _ = make(session=session, webhook_url=SLACK)
    notifier.send("x")


def test_text_whose_str_raises_is_swallowed(caplog):
    class Evil:
        def __str__(self) -> str:
            raise RuntimeError("no str for you")

    notifier, session = make(webhook_url=SLACK)
    with caplog.at_level(logging.WARNING, logger="bot.notify"):
        notifier.send(Evil())  # type: ignore[arg-type]
        notifier.trade(Evil())  # type: ignore[arg-type]
        notifier.error(Evil())  # type: ignore[arg-type]
    session.post.assert_not_called()
    assert "could not send notification" in caplog.text


def test_exception_whose_str_raises_is_swallowed():
    class NastyError(Exception):
        def __str__(self) -> str:
            raise RuntimeError("nested")

    session = make_session()
    session.post.side_effect = NastyError()
    notifier, _ = make(session=session, webhook_url=SLACK)
    notifier.send("x")


def test_secrets_are_redacted_from_failure_logs(caplog):
    session = make_session()
    session.post.side_effect = requests.ConnectionError(
        f"Max retries exceeded with url: /bot{TOKEN}/sendMessage and /api/webhooks/123/DISCORDSECRET")
    notifier, _ = make(session=session, webhook_url=DISCORD, telegram_bot_token=TOKEN, telegram_chat_id=CHAT)
    with caplog.at_level(logging.WARNING, logger="bot.notify"):
        notifier.send("x")
    assert caplog.records
    assert "TELEGRAMSECRET" not in caplog.text and "DISCORDSECRET" not in caplog.text


def test_secrets_are_redacted_from_error_response_bodies(caplog):
    notifier, _ = make(session=make_session(status=401, text=f"bad token {TOKEN}"),
                       telegram_bot_token=TOKEN, telegram_chat_id=CHAT)
    with caplog.at_level(logging.WARNING, logger="bot.notify"):
        notifier.send("x")
    assert "HTTP 401" in caplog.text and "TELEGRAMSECRET" not in caplog.text


def test_default_session_is_created_lazily(monkeypatch):
    created = []

    def fake_session():
        session = make_session()
        created.append(session)
        return session

    monkeypatch.setattr(notify_mod.requests, "Session", fake_session)
    notifier = Notifier(NotifyConfig(webhook_url=SLACK))
    notifier.send("no network needed to build me")   # enabled -> session created once
    notifier.send("again")
    assert len(created) == 1 and created[0].post.call_count == 2

    Notifier(NotifyConfig()).send("disabled")   # disabled -> no session at all
    assert len(created) == 1
