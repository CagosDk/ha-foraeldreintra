from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

DOMAIN = "foraeldreintra"

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
):
    async_add_entities([ForældreIntraSensor("Frederik")])
    async_add_entities([ForældreIntraSensor("Olivia")])


class ForældreIntraSensor(SensorEntity):
    def __init__(self, name):
        self._attr_name = f"ForældreIntra {name}"
        self._attr_unique_id = f"foraeldreintra_{name.lower()}"
        self._attr_native_value = "Ingen data endnu"
        self._attr_extra_state_attributes = {}

    async def async_update(self):
        # Her kommer scraping senere
        self._attr_native_value = "Virker!"

