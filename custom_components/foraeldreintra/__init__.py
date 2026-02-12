DOMAIN = "foraeldreintra"

async def async_setup(hass, config):
    hass.data.setdefault(DOMAIN, {})
    return True
