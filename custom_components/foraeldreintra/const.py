

DOMAIN = "foraeldreintra"

CONF_SCHOOL_URL = "school_url"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

PLATFORMS = ["sensor"]

# Options
OPT_SELECTED_CHILDREN = "selected_children"

OPT_DISPLAY_PERIOD = "display_period"
DEFAULT_DISPLAY_PERIOD = "today_and_future"

# Lektier
OPT_SHOW_HOMEWORK_SENSORS = "show_homework_sensors"
DEFAULT_SHOW_HOMEWORK_SENSORS = True

OPT_ADD_HOMEWORK_MARKDOWN = "add_homework_markdown"
DEFAULT_ADD_HOMEWORK_MARKDOWN = False

# Ugeplan - sensorer
OPT_SHOW_WEEKPLAN_SENSORS = "show_weekplan_sensors"
DEFAULT_SHOW_WEEKPLAN_SENSORS = True

OPT_SHOW_WEEKPLAN_GENERAL_SENSORS = "show_weekplan_general_sensors"
DEFAULT_SHOW_WEEKPLAN_GENERAL_SENSORS = False

OPT_SHOW_WEEKPLAN_FOCUS_SENSORS = "show_weekplan_focus_sensors"
DEFAULT_SHOW_WEEKPLAN_FOCUS_SENSORS = False

OPT_SHOW_WEEKPLAN_SCHEDULE_SENSORS = "show_weekplan_schedule_sensors"
DEFAULT_SHOW_WEEKPLAN_SCHEDULE_SENSORS = False

# Ugeplan - indhold i samlet ugeplan
OPT_INCLUDE_WEEKPLAN_GENERAL = "include_weekplan_general"
DEFAULT_INCLUDE_WEEKPLAN_GENERAL = True

OPT_INCLUDE_WEEKPLAN_FOCUS = "include_weekplan_focus"
DEFAULT_INCLUDE_WEEKPLAN_FOCUS = True

OPT_INCLUDE_WEEKPLAN_SCHEDULE = "include_weekplan_schedule"
DEFAULT_INCLUDE_WEEKPLAN_SCHEDULE = True

# Markdown
OPT_ADD_WEEKPLAN_MARKDOWN = "add_weekplan_markdown"
DEFAULT_ADD_WEEKPLAN_MARKDOWN = True

# Tilpasning
OPT_SUBJECT_ALIASES = "subject_aliases"
DEFAULT_SUBJECT_ALIASES = ""

# Intern fast polling
DEFAULT_SCAN_INTERVAL_MINUTES = 60

# Afledte lektier fra ugeplan
OPT_WEEKPLAN_DERIVED_HOMEWORK_ENABLED = "weekplan_derived_homework_enabled"
DEFAULT_WEEKPLAN_DERIVED_HOMEWORK_ENABLED = False

OPT_WEEKPLAN_DERIVED_HOMEWORK_KEYWORDS = "weekplan_derived_homework_keywords"
DEFAULT_WEEKPLAN_DERIVED_HOMEWORK_KEYWORDS = ["diktatord", "øveord", "ord til diktat"]

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}_homework_status"

DATA_HOMEWORK_STATUS_STORE = "homework_status_store"
