"""
Stub-moduler så custom-component-koden kan importeres uden
at have homeassistant installeret i test-miljøet.
"""
import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class _DataUpdateCoordinator:
    """Minimal stand-in for DataUpdateCoordinator."""

    def __class_getitem__(cls, item):
        return cls

    def __init__(self, hass, logger, *, name, update_interval):
        self.hass = hass
        self.data = None

    def async_set_updated_data(self, data):
        self.data = data

    def async_request_refresh(self):
        pass

    def async_update_listeners(self):
        pass


class _UpdateFailed(Exception):
    pass


class _Store:
    """Minimal stand-in for homeassistant.helpers.storage.Store."""

    def __init__(self, hass, version, key):
        pass

    async def async_load(self):
        return None

    async def async_save(self, data):
        pass


_update_coordinator_mod = MagicMock()
_update_coordinator_mod.DataUpdateCoordinator = _DataUpdateCoordinator
_update_coordinator_mod.UpdateFailed = _UpdateFailed

_storage_mod = MagicMock()
_storage_mod.Store = _Store

_cv_mod = MagicMock()
_cv_mod.string = str

_helpers_mod = MagicMock()
_helpers_mod.config_validation = _cv_mod

sys.modules.update({
    "homeassistant": MagicMock(),
    "homeassistant.components": MagicMock(),
    "homeassistant.components.http": MagicMock(),
    "homeassistant.config_entries": MagicMock(),
    "homeassistant.core": MagicMock(),
    "homeassistant.helpers": _helpers_mod,
    "homeassistant.helpers.aiohttp_client": MagicMock(),
    "homeassistant.helpers.config_validation": _cv_mod,
    "homeassistant.helpers.entity_registry": MagicMock(),
    "homeassistant.helpers.storage": _storage_mod,
    "homeassistant.helpers.update_coordinator": _update_coordinator_mod,
    "homeassistant.util": MagicMock(),
})
