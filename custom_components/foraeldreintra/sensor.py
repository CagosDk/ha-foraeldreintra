from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.entity_platform import AddEntitiesCallback

DOMAIN = "foraeldreintra"

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info=None,
):
    async_add_entities([
        ForaeldreIntraSensor("Frederik"),
        ForaeldreIntraSensor("Olivia")
    ])


class ForaeldreIntraSensor(SensorEntity):
    def __init__(self, name):
        self._name = f"ForældreIntra {name}"
        self._unique_id = f"foraeldreintra_{name.lower()}"
        self._state = "Ingen data endnu"

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def state(self):
        return self._state

    async def async_update(self):
        self._state = "Virker!"
