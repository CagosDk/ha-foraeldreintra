DOMAIN = "foraeldreintra"

CONF_SCHOOL_URL = "school_url"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

PLATFORMS = ["sensor"]

# Options
OPT_SELECTED_CHILDREN = "selected_children"  # list[str]

# Ny: visningsperiode (erstatter include_history)
OPT_DISPLAY_PERIOD = "display_period"  # "all" | "today_and_future" | "future_only"
DEFAULT_DISPLAY_PERIOD = "today_and_future"

# Ny: tilføj markdown attribute
OPT_ADD_MARKDOWN = "add_markdown"
DEFAULT_ADD_MARKDOWN = False

# (Behold) opdatering
OPT_SCAN_MODE = "scan_mode"  # "interval" | "fixed_times"
OPT_SCAN_INTERVAL_MINUTES = "scan_interval_minutes"  # int
OPT_SCAN_TIMES = "scan_times"  # CSV "06:30,12:00"

DEFAULT_SCAN_MODE = "interval"
DEFAULT_SCAN_INTERVAL_MINUTES = 15
DEFAULT_SCAN_TIMES = ""
