DOMAIN = "foraeldreintra"

CONF_SCHOOL_URL = "school_url"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

# Options
OPT_SELECTED_CHILDREN = "selected_children"          # list[str]
OPT_INCLUDE_HISTORY = "include_history"              # bool
OPT_DAYS_BACK = "days_back"                          # int
OPT_DAYS_FORWARD = "days_forward"                    # int
OPT_HIDE_EMPTY_CHILDREN = "hide_empty_children"      # bool
OPT_SORT_MODE = "sort_mode"                          # str
OPT_MAX_ITEMS = "max_items"                          # int
OPT_IGNORE_UNKNOWN_SUBJECT = "ignore_unknown_subject"  # bool

OPT_SCAN_MODE = "scan_mode"                          # "interval" | "fixed_times"
OPT_SCAN_INTERVAL_MINUTES = "scan_interval_minutes"  # int
OPT_SCAN_TIMES = "scan_times"                        # str (CSV: "06:30,12:00")

DEFAULT_SCAN_INTERVAL_MINUTES = 15

DEFAULT_INCLUDE_HISTORY = False
DEFAULT_DAYS_BACK = 7
DEFAULT_DAYS_FORWARD = 30
DEFAULT_HIDE_EMPTY_CHILDREN = False
DEFAULT_SORT_MODE = "date_then_child"  # "date_then_child" | "child_then_date"
DEFAULT_MAX_ITEMS = 50
DEFAULT_IGNORE_UNKNOWN_SUBJECT = False

DEFAULT_SCAN_MODE = "interval"
DEFAULT_SCAN_TIMES = ""

PLATFORMS = ["sensor"]
