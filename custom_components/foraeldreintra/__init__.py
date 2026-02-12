from homeassistant.helpers.discovery import async_load_platform

DOMAIN = "foraeldreintra"

async def async_setup(hass, config):
    hass.async_create_task(
        async_load_platform(hass, "sensor", DOMAIN, {}, config)
    )
    return True
