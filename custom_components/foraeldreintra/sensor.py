from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .scraper import hent_lektier

DOMAIN = "foraeldreintra"

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
):
    username = hass.data[DOMAIN]["username"]
    password = hass.data[DOMAIN]["password"]
    school_url = hass.data[DOMAIN]["school_url"]

    data = hent_lektier(username, password, school_url)

    entities = []
    for barn, tekst in data.items():
        entities.append(ForældreIntraSensor(barn, tekst))

    async_add_entities(entities)


class ForældreIntraSensor(SensorEntity):
    def __init__(self, name, value):
        self._attr_name = f"ForældreIntra {name}"
        self._attr_unique_id = f"foraeldreintra_{name.lower()}"
        self._attr_native_value = value
