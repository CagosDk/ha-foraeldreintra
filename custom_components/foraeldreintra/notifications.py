from __future__ import annotations

import re
from typing import Any

from homeassistant.core import HomeAssistant


class NotificationDeliveryError(Exception):
    """Configured Home Assistant notification target is invalid or unavailable."""


async def async_send_notification(
    hass: HomeAssistant,
    service: str,
    title: str,
    message: str,
    url: str = "",
    telegram_chat_ids: str = "",
) -> None:
    """Send one notification through a notify service or Telegram bot action."""
    service = service.strip()
    if service == "telegram_bot.send_message":
        chat_id_values = [
            value.strip()
            for value in re.split(r"[,;\n]+", telegram_chat_ids)
            if value.strip()
        ]
        if not chat_id_values:
            raise NotificationDeliveryError("Telegram chat ID is required")
        chat_ids: list[str | int] = [
            int(value) if re.fullmatch(r"-?\d+", value) else value
            for value in chat_id_values
        ]
        domain = "telegram_bot"
        service_name = "send_message"
        telegram_message = f"{title}\n\n{message}"
        if url:
            telegram_message += f"\n\n{url}"
        service_data: dict[str, Any] = {
            "message": telegram_message,
            "target": chat_ids,
        }
    else:
        if service.startswith("notify."):
            service = service.split(".", 1)[1]
        if not re.fullmatch(r"[a-z0-9_]+", service):
            raise NotificationDeliveryError("Enter a valid notify service")
        domain = "notify"
        service_name = service
        service_data = {
            "title": title,
            "message": message,
            "data": {"url": url, "clickAction": url} if url else {},
        }

    if not hass.services.has_service(domain, service_name):
        raise NotificationDeliveryError(
            f"Home Assistant service {domain}.{service_name} is unavailable"
        )

    try:
        await hass.services.async_call(
            domain,
            service_name,
            service_data,
            blocking=True,
        )
    except Exception as err:
        raise NotificationDeliveryError("Notification could not be sent") from err
