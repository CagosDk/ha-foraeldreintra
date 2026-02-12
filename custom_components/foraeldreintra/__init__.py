DOMAIN = "foraeldreintra"

async def async_setup(hass, config):
    conf = config.get(DOMAIN)

    hass.data[DOMAIN] = {
        "username": conf.get("username"),
        "password": conf.get("password"),
        "school_url": conf.get("school_url"),
    }

    hass.async_create_task(
        hass.helpers.discovery.async_load_platform(
            "sensor", DOMAIN, {}, config
        )
    )

    return True
