from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
):
    async_add_entities(
        [
            ForaeldreIntraSensor("Frederik"),
            ForaeldreIntraSensor("Olivia"),
        ],
        True,
    )


class ForaeldreIntraSensor(SensorEntity):
    def __init__(self, name):
        self._attr_name = f"ForældreIntra {name}"
        self._attr_unique_id = f"foraeldreintra_{name.lower()}"
        self._attr_native_value = "Starter..."
        self._attr_extra_state_attributes = {}

    async def async_update(self):
        self._attr_native_value = "Virker!"
