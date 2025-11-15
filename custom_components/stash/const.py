from homeassistant.const import CONF_URL as HA_CONF_URL

DOMAIN = "stash"

# Используем стандартный ключ url из HA
CONF_URL = HA_CONF_URL

# Интервал опроса Stash (в секундах)
DEFAULT_SCAN_INTERVAL = 300
