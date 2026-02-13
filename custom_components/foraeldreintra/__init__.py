from homeassistant.helpers.discovery import async_load_platform

DOMAIN = "foraeldreintra"

async def async_setup(hass, config):
    conf = config.get(DOMAIN)

    if not conf:
        return False

    hass.data[DOMAIN] = {
        "username": conf.get("username"),
        "password": conf.get("password"),
        "school_url": conf.get("school_url"),
    }

    # Korrekt måde at loade platform
    hass.async_create_task(
        async_load_platform(hass, "sensor", DOMAIN, {}, config)
    )

    return True
