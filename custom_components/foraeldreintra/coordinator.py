from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ForaldreIntraClient, ForaldreIntraAuthError, ForaldreIntraError
from .notifications import async_send_notification, NotificationDeliveryError
from .const import (
    CONF_PASSWORD,
    CONF_SCHOOL_URL,
    CONF_USERNAME,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    OPT_SELECTED_CHILDREN,
    OPT_NOTIFY_NEW_MESSAGES,
    OPT_MESSAGE_NOTIFY_SERVICE,
    OPT_TELEGRAM_TARGET,
)

_LOGGER = logging.getLogger(__name__)


class ForaldreIntraCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.session = async_get_clientsession(hass)
        self.client = ForaldreIntraClient(
            session=self.session,
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            school_url=entry.data[CONF_SCHOOL_URL],
        )
        self._last_good_data: dict[str, Any] | None = None
        self._message_notification_store = Store(
            hass,
            1,
            f"{DOMAIN}_message_notifications_{entry.entry_id}",
        )
        self._message_notification_state: dict[str, Any] | None = None

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL_MINUTES),
        )

    async def async_update_options(self, new_entry: ConfigEntry) -> None:
        self.entry = new_entry
        self.async_set_updated_data(self.data)
        self.async_request_refresh()

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self._fetch_children_homework_and_weekplans_with_retry()

            if self._is_valid_result(data):
                if isinstance(data.get("messages"), list):
                    await self._async_notify_new_messages(
                        data["messages"],
                        data.get("message_child_ids", []),
                    )
                self._last_good_data = data
                return data

            _LOGGER.warning(
                "ForældreIntra returnerede tomt eller ugyldigt datasæt. "
                "Beholder sidste gyldige data."
            )

            if self._last_good_data is not None:
                return self._last_good_data

            raise UpdateFailed("Tomt datasæt modtaget og ingen tidligere data at falde tilbage på.")

        except (ForaldreIntraAuthError, ForaldreIntraError) as err:
            if self._last_good_data is not None:
                _LOGGER.warning(
                    "Fejl ved opdatering af ForældreIntra (%s). "
                    "Beholder sidste gyldige data.",
                    err,
                )
                return self._last_good_data
            raise UpdateFailed(str(err)) from err

        except Exception as err:
            if self._last_good_data is not None:
                _LOGGER.exception(
                    "Ukendt fejl ved opdatering af ForældreIntra. "
                    "Beholder sidste gyldige data."
                )
                return self._last_good_data
            raise UpdateFailed(f"Ukendt fejl: {err}") from err

    async def _fetch_children_homework_and_weekplans_with_retry(self) -> dict[str, Any]:
        # Første forsøg
        data = await self._fetch_children_and_homework()

        if self._is_valid_result(data):
            return data

        _LOGGER.warning(
            "ForældreIntra gav tomt/mistænkeligt resultat. Forsøger ny login og henter igen."
        )

        # Tvungen ny login + nyt forsøg
        await self.client.login()
        data_retry = await self._fetch_children_and_homework()

        return data_retry

    async def _fetch_children_and_homework(self) -> dict[str, Any]:
        children = await self.client.get_children()

        if not children:
            _LOGGER.debug("Ingen børn fundet i første forsøg. Logger ind igen.")
            await self.client.login()
            children = await self.client.get_children()

        items = await self.client.get_homework_for_children(children) if children else []
        weeklyplans = await self.client.get_weekplans_for_children(children) if children else {}

        selected_names = set(self.entry.options.get(OPT_SELECTED_CHILDREN, []))
        message_children = [
            child
            for child in children
            if not selected_names or child.name in selected_names
        ]
        messages: list[dict[str, Any]] | None = None
        try:
            messages = await self.client.get_messages_for_children(message_children)
        except Exception:
            # Message polling must not interrupt homework and weekly-plan updates.
            _LOGGER.warning("Beskedpolling fejlede; de øvrige data opdateres videre.")

        return {
            "children": [{"id": c.id, "name": c.name} for c in children],
            "items": items,
            "weeklyplans": weeklyplans,
            "messages": messages,
            "message_child_ids": [child.id for child in message_children],
        }

    async def _async_notify_new_messages(
        self,
        messages: list[dict[str, Any]],
        child_ids: list[str],
    ) -> None:
        """Notify once for newly observed unread messages and persist their IDs."""
        if self._message_notification_state is None:
            stored = await self._message_notification_store.async_load()
            self._message_notification_state = stored if isinstance(stored, dict) else {}

        state = self._message_notification_state
        initialized = set(str(value) for value in state.get("initialized_children", []))
        stored_seen = state.get("seen_by_child", {})
        if not isinstance(stored_seen, dict):
            stored_seen = {}

        current_by_child: dict[str, list[dict[str, Any]]] = {}
        for message in messages:
            child_id = str(message.get("child_id") or "")
            if child_id:
                current_by_child.setdefault(child_id, []).append(message)

        notify_enabled = bool(self.entry.options.get(OPT_NOTIFY_NEW_MESSAGES, False))
        service = str(
            self.entry.options.get(OPT_MESSAGE_NOTIFY_SERVICE, "") or ""
        ).strip()
        telegram_chat_ids = str(
            self.entry.options.get(OPT_TELEGRAM_TARGET, "") or ""
        ).strip()

        seen_by_child: dict[str, list[str]] = {
            str(child_id): [
                str(message_id)
                for message_id in message_ids
                if message_id is not None
            ][-1000:]
            for child_id, message_ids in stored_seen.items()
            if isinstance(message_ids, list)
        }

        for child_value in child_ids:
            child_id = str(child_value)
            seen = set(seen_by_child.get(child_id, []))
            child_messages = current_by_child.get(child_id, [])

            # First successful poll establishes a baseline and avoids old-message bursts.
            if child_id not in initialized:
                seen.update(str(message.get("id")) for message in child_messages)
                initialized.add(child_id)
                seen_by_child[child_id] = list(seen)[-1000:]
                continue

            for message in child_messages:
                message_id = str(message.get("id") or "")
                if not message_id or message_id in seen:
                    continue

                if not bool(message.get("unread")) or not notify_enabled or not service:
                    seen.add(message_id)
                    continue

                sender = str(message.get("sender") or "").strip()
                body = str(message.get("message") or "").strip()
                if len(body) > 1000:
                    body = body[:997] + "..."
                title = (
                    f"ForældreIntra · {message.get('child', '')} · "
                    f"{message.get('subject', 'Ny besked')}"
                )
                notification = (
                    f"{sender}: {body}"
                    if sender and body
                    else (body or sender or "Du har modtaget en ny besked.")
                )

                try:
                    await async_send_notification(
                        self.hass,
                        service,
                        title,
                        notification,
                        str(message.get("url") or ""),
                        telegram_chat_ids,
                    )
                except NotificationDeliveryError:
                    _LOGGER.warning(
                        "ForældreIntra notification could not be sent via %s",
                        service,
                    )
                    continue

                seen.add(message_id)

            seen_by_child[child_id] = list(seen)[-1000:]

        self._message_notification_state = {
            "initialized_children": sorted(initialized),
            "seen_by_child": seen_by_child,
        }
        await self._message_notification_store.async_save(
            self._message_notification_state
        )

    def _is_valid_result(self, data: dict[str, Any] | None) -> bool:
        if not data or not isinstance(data, dict):
            return False

        children = data.get("children") or []
        weeklyplans = data.get("weeklyplans") or {}
        items = data.get("items") or []

        # Hvis vi slet ikke har børn, er resultatet ikke brugbart
        if not children:
            return False

        # Hvis der er børn men både ugeplaner og lektier er helt tomme,
        # er det ofte tegn på udløbet session / fejlsvar snarere end reel "ingen data".
        if not weeklyplans and not items and data.get("messages") is None:
            return False

        return True

    async def async_shutdown(self) -> None:
        return None
