DOMAIN = "foraeldreintra"

CONF_SCHOOL_URL = "school_url"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

PLATFORMS = ["sensor"]

# Options
OPT_SELECTED_CHILDREN = "selected_children"        # list[str]
OPT_INCLUDE_HISTORY = "include_history"            # bool

OPT_SCAN_MODE = "scan_mode"                        # "interval" | "fixed_times"
OPT_SCAN_INTERVAL_MINUTES = "scan_interval_minutes"  # int
OPT_SCAN_TIMES = "scan_times"                      # CSV "06:30,12:00"

DEFAULT_INCLUDE_HISTORY = True

DEFAULT_SCAN_MODE = "interval"
DEFAULT_SCAN_INTERVAL_MINUTES = 15
DEFAULT_SCAN_TIMES = ""
