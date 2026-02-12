from homeassistant.const import Platform

DOMAIN = "foraeldreintra"
PLATFORMS = [Platform.SENSOR]

async def async_setup(hass, config):
    return True

async def async_setup_entry(hass, entry):
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True
