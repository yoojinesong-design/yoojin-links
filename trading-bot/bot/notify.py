"""Trade and error notifications to Discord, Slack, a generic webhook and/or Telegram.

Notifications are best-effort: a failed or slow notification must never stop
the bot from managing its positions, so :meth:`Notifier.send` never raises.
"""
from __future__ import annotations

import logging
from urllib.parse import urlparse

import requests

from .config import NotifyConfig

logger = logging.getLogger(__name__)

MAX_MESSAGE_CHARS = 1900   # Discord's hard limit is 2000; leave room for formatting
TIMEOUT_SECONDS = 10
TELEGRAM_API = "https://api.telegram.org"

_LEVELS = {"debug": logging.DEBUG, "info": logging.INFO, "warning": logging.WARNING,
           "error": logging.ERROR, "critical": logging.CRITICAL}


class Notifier:
    def __init__(self, config: NotifyConfig, mode: str = "paper",
                 session: requests.Session | None = None) -> None:
        self.config = config
        self.mode = mode
        self._session = session

    @property
    def enabled(self) -> bool:
        """True when at least one destination is fully configured."""
        return bool(self.config.webhook_url) or self._telegram_ready

    @property
    def _telegram_ready(self) -> bool:
        return bool(self.config.telegram_bot_token and self.config.telegram_chat_id)

    def send(self, text: str, level: str = "info") -> None:
        """Log ``text`` and push it to every configured destination. Never raises."""
        self._emit(text, level, remote=True)

    def trade(self, text: str) -> None:
        """A fill / order notification (pushed only when ``on_trade`` is on; always logged)."""
        self._emit(text, "info", remote=self.config.on_trade)

    def error(self, text: str) -> None:
        """An error notification (pushed only when ``on_error`` is on; always logged)."""
        self._emit(text, "error", remote=self.config.on_error)

    # ---- internals -----------------------------------------------------------
    def _emit(self, text: object, level: str, remote: bool) -> None:
        try:
            message = self._format(text, level)
            logger.log(_LEVELS.get(str(level).lower(), logging.INFO), "notify: %s", message)
            if not remote:
                return
            url = self.config.webhook_url
            if url:
                self._post(url, _webhook_payload(url, message), "webhook")
            token, chat_id = self.config.telegram_bot_token, self.config.telegram_chat_id
            if token and chat_id:
                self._post(f"{TELEGRAM_API}/bot{token}/sendMessage",
                           {"chat_id": chat_id, "text": message}, "telegram")
        except Exception as exc:  # noqa: BLE001 - notifications must never break trading
            try:
                logger.warning("notify: could not send notification: %s: %s",
                               type(exc).__name__, self._redact(str(exc)))
            except Exception:  # noqa: BLE001 - even a broken exception message must not escape
                pass

    def _format(self, text: object, level: str) -> str:
        tag = f"[{str(self.mode or 'paper').upper()}]"
        marker = {"warning": " WARNING:", "error": " ERROR:", "critical": " CRITICAL:"}.get(str(level).lower(), "")
        message = f"{tag}{marker} {text}"
        if len(message) > MAX_MESSAGE_CHARS:
            message = message[:MAX_MESSAGE_CHARS - 1] + "…"
        return message

    def _post(self, url: str, payload: dict[str, str], destination: str) -> None:
        try:
            if self._session is None:
                self._session = requests.Session()
            response = self._session.post(url, json=payload, timeout=TIMEOUT_SECONDS)
            status = int(response.status_code)
            if not 200 <= status < 300:
                body = str(getattr(response, "text", ""))[:200]
                logger.warning("notify: %s returned HTTP %s: %s", destination, status, self._redact(body))
        except Exception as exc:  # noqa: BLE001 - connection errors, timeouts, bad responses
            logger.warning("notify: %s failed: %s: %s", destination, type(exc).__name__, self._redact(str(exc)))

    def _redact(self, text: str) -> str:
        """Hide secrets that exception messages may echo: the bot token and the
        webhook URL (requests often prints only the URL's path, which is the secret part)."""
        secrets = [self.config.telegram_bot_token, self.config.webhook_url]
        if self.config.webhook_url:
            secrets.append(urlparse(self.config.webhook_url).path)
        for secret in secrets:
            if secret and len(secret) > 1:
                text = text.replace(secret, "***")
        return text


def _webhook_payload(url: str, text: str) -> dict[str, str]:
    """Discord wants ``content``, Slack wants ``text``; unknown services get both."""
    host = (urlparse(url).hostname or "").lower()
    if _host_is(host, "discord.com") or _host_is(host, "discordapp.com"):
        return {"content": text}
    if host == "hooks.slack.com":
        return {"text": text}
    return {"text": text, "content": text}


def _host_is(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


__all__ = ["Notifier"]
