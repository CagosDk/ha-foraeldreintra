from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION


class HomeworkStatusStore:
    """Persistent storage for homework completion status."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(
            hass,
            STORAGE_VERSION,
            STORAGE_KEY,
        )
        self._data: dict[str, bool] = {}

    async def async_load(self) -> None:
        """Load persisted homework status."""
        stored = await self._store.async_load()
        if isinstance(stored, dict):
            completed = stored.get("completed", {})
            if isinstance(completed, dict):
                self._data = {
                    str(key): bool(value)
                    for key, value in completed.items()
                }
                return

        self._data = {}

    async def async_save(self) -> None:
        """Persist homework status."""
        await self._store.async_save(
            {
                "completed": self._data,
            }
        )

    def is_completed(self, homework_id: str) -> bool:
        """Return True if homework is marked as completed."""
        return self._data.get(homework_id, False)

    async def async_set_completed(self, homework_id: str, completed: bool) -> None:
        """Set completion state for a homework item."""
        self._data[homework_id] = completed
        await self.async_save()

    async def async_remove(self, homework_id: str) -> None:
        """Remove stored state for a homework item."""
        if homework_id in self._data:
            self._data.pop(homework_id)
            await self.async_save()

    def as_dict(self) -> dict[str, bool]:
        """Return a copy of current completion map."""
        return dict(self._data)
