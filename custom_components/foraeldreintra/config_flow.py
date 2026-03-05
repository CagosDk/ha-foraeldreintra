class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self.entry = entry
        self._children: list[str] = []

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        # Hent børn – men lad aldrig flowet crashe hvis det fejler
        try:
            self._children = await self._fetch_children_names()
        except Exception:  # noqa: BLE001
            self._children = []

        existing = self.entry.options

        include_history_default = existing.get(OPT_INCLUDE_HISTORY, DEFAULT_INCLUDE_HISTORY)
        scan_mode_default = existing.get(OPT_SCAN_MODE, DEFAULT_SCAN_MODE)
        scan_interval_default = int(existing.get(OPT_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES))
        scan_times_default = existing.get(OPT_SCAN_TIMES, DEFAULT_SCAN_TIMES)

        # Default: alle børn valgt (hvis vi kender dem)
        selected_default = existing.get(OPT_SELECTED_CHILDREN)
        if (selected_default is None or selected_default == []) and self._children:
            selected_default = list(self._children)

        if user_input is not None:
            scan_mode = user_input.get(OPT_SCAN_MODE, DEFAULT_SCAN_MODE)

            if scan_mode == "interval":
                minutes = int(user_input.get(OPT_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES))
                if minutes < 1 or minutes > 1440:
                    errors[OPT_SCAN_INTERVAL_MINUTES] = "invalid_range"

            if scan_mode == "fixed_times":
                csv = (user_input.get(OPT_SCAN_TIMES) or "").strip()
                if not csv:
                    errors[OPT_SCAN_TIMES] = "required"
                elif not self._validate_times_csv(csv):
                    errors[OPT_SCAN_TIMES] = "invalid_time"

            if not errors:
                cleaned = dict(user_input)

                # Hvis brugeren ender med tom liste, så vælg alle (hvis vi kender dem)
                if not cleaned.get(OPT_SELECTED_CHILDREN) and self._children:
                    cleaned[OPT_SELECTED_CHILDREN] = list(self._children)

                # Polish: ryd irrelevante felter før vi gemmer
                if scan_mode == "interval":
                    cleaned[OPT_SCAN_TIMES] = ""
                    cleaned[OPT_SCAN_INTERVAL_MINUTES] = int(
                        cleaned.get(OPT_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES)
                    )
                else:
                    cleaned[OPT_SCAN_INTERVAL_MINUTES] = DEFAULT_SCAN_INTERVAL_MINUTES
                    cleaned[OPT_SCAN_TIMES] = (cleaned.get(OPT_SCAN_TIMES) or "").strip()

                return self.async_create_entry(title="", data=cleaned)

        # Byg schema
        schema_dict = {}

        # Børn: vis kun selector hvis vi faktisk har børn (ellers undgå crash)
        if self._children:
            children_selector = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=self._children,
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            )
            schema_dict[vol.Required(OPT_SELECTED_CHILDREN, default=selected_default)] = children_selector

        schema_dict[vol.Required(OPT_INCLUDE_HISTORY, default=include_history_default)] = bool

        scan_mode_selector = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    {"value": "interval", "label": "Interval"},
                    {"value": "fixed_times", "label": "Faste tidspunkter"},
                ],
                multiple=False,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )
        schema_dict[vol.Required(OPT_SCAN_MODE, default=scan_mode_default)] = scan_mode_selector

        schema_dict[vol.Optional(OPT_SCAN_INTERVAL_MINUTES, default=scan_interval_default)] = vol.Coerce(int)
        schema_dict[vol.Optional(OPT_SCAN_TIMES, default=scan_times_default)] = str

        schema = vol.Schema(schema_dict)

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
