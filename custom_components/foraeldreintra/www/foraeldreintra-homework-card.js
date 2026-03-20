const FORAELDREINTRA_HOMEWORK_CARD_VERSION = "1.0.0";

class ForaeldreIntraHomeworkCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._hass = null;
    this._hideCompleted = false;
  }

  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("Du skal angive entity");
    }

    const DEFAULT_DATA = {
      title: "Lektier",
      hide_completed: false,
      display_period: "current_and_future",
      child_filter: [],
      subject_filter: [],
      child_aliases: {},
      subject_aliases: {},
      show_derived_items: true,
    };

    const DEFAULT_GROUPING = {
      group_by_child: true,
      show_date_headers: true,
      show_child_header: true,
      show_child_in_meta: true,
      compact: false,
    };

    const DEFAULT_TEXTS = {
      status_label_open: "Mangler",
      status_label_urgent: "Mangler",
      status_label_done: "Færdig",
      button_label_done: "Færdig",
      button_label_undo: "Fortryd",
      filter_label_show_completed: "Vis færdige",
      filter_label_hide_completed: "Skjul færdige",
      derived_badge_label: "Fra ugeplan",
    };

    const DEFAULT_VISIBILITY = {
      show_status_badge: true,
      show_derived_badge: true,
      show_filter_button: true,
      show_toggle_button: true,
      status_indicator_style: "dot",
      status_bar_width: 6,
    };

    const DEFAULT_TYPOGRAPHY = {
      title_font_size: "",
      text_font_size: "",
      date_font_size: "",
      child_font_size: "",
      subject_title_font_size: "",
      button_font_size: "",
      badge_font_size: "",
    };

    const DEFAULT_LAYOUT = {
      card_border_radius: 14,
      card_background_opacity: 1,
      outer_card_background_color: "var(--card-background-color)",
      outer_card_background_opacity: "0,35",
      group_card_background_color: "var(--card-background-color)",
      group_card_background_opacity: "0,55",
      item_card_background_color: "var(--card-background-color)",
      item_card_background_opacity: "0,75",
    };

    const DEFAULT_COLORS = {
      status_color_open: "#ffb300",
      status_color_urgent: "#e53935",
      status_color_done: "#43a047",

      title_text_color: "var(--primary-text-color)",
      text_color: "var(--primary-text-color)",
      date_text_color: "var(--secondary-text-color)",
      child_text_color: "var(--primary-text-color)",
      meta_text_color: "var(--secondary-text-color)",

      toggle_button_background_color: "var(--primary-color)",
      toggle_button_text_color: "var(--text-primary-color)",
      toggle_button_secondary_background_color: "var(--secondary-background-color)",
      toggle_button_secondary_text_color: "var(--primary-text-color)",

      derived_badge_background_color: "rgba(66, 133, 244, 0.18)",
      derived_badge_text_color: "var(--primary-text-color)",
    };

    this._defaults = {
      ...DEFAULT_DATA,
      ...DEFAULT_GROUPING,
      ...DEFAULT_TEXTS,
      ...DEFAULT_VISIBILITY,
      ...DEFAULT_TYPOGRAPHY,
      ...DEFAULT_LAYOUT,
      ...DEFAULT_COLORS,
    };

    this._config = {
      ...this._defaults,
      ...config,
    };

    this._hideCompleted = this._loadHideCompletedPreference();
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    const items = this._getVisibleItems();
    return Math.max(3, items.length + 2);
  }

  _getHideCompletedStorageKey() {
    const entity = String(this._config?.entity || "unknown");
    return `foraeldreintra:hide_completed:${entity}`;
  }

  _loadHideCompletedPreference() {
    try {
      const saved = window.localStorage.getItem(this._getHideCompletedStorageKey());
      if (saved === "true") return true;
      if (saved === "false") return false;
    } catch (err) {
      // Ignorer localStorage-fejl
    }

    return Boolean(this._config?.hide_completed);
  }

  _saveHideCompletedPreference(value) {
    try {
      window.localStorage.setItem(
        this._getHideCompletedStorageKey(),
        value ? "true" : "false"
      );
    } catch (err) {
      // Ignorer localStorage-fejl
    }
  }

  _getEntityState() {
    if (!this._hass || !this._config?.entity) return null;
    return this._hass.states[this._config.entity] || null;
  }

  _getItems() {
    const stateObj = this._getEntityState();
    const items = stateObj?.attributes?.items;
    return Array.isArray(items) ? items : [];
  }

  _normalizeStringArray(value) {
    if (!Array.isArray(value)) return [];
    return value
      .map((item) => String(item ?? "").trim())
      .filter((item) => item.length > 0);
  }

  _normalizeMap(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return {};
    const out = {};
    for (const [key, val] of Object.entries(value)) {
      const k = String(key ?? "").trim();
      const v = String(val ?? "").trim();
      if (k) out[k] = v;
    }
    return out;
  }

  _displayCssValue(value, fallback) {
    const v = String(value ?? "").trim();
    return v || fallback;
  }

  _parseLocalizedNumber(value, fallback = null) {
    if (value === null || value === undefined || value === "") return fallback;
    if (typeof value === "number") return Number.isFinite(value) ? value : fallback;

    const normalized = String(value).trim().replace(/\s+/g, "").replace(",", ".");
    const num = Number(normalized);
    return Number.isFinite(num) ? num : fallback;
  }

  _getRemSize(value, fallback) {
    const num = this._parseLocalizedNumber(value, fallback);
    return `${num}rem`;
  }

  _clampOpacity(value, fallback = 1) {
    const num = this._parseLocalizedNumber(value, fallback);
    if (Number.isFinite(num)) return Math.min(1, Math.max(0, num));
    return fallback;
  }

  _clampPositiveNumber(value, fallback = 6) {
    const num = this._parseLocalizedNumber(value, fallback);
    if (Number.isFinite(num)) return Math.max(0, num);
    return fallback;
  }

  _colorWithOpacity(color, opacity, fallbackColor = "var(--card-background-color)") {
    const safeColor = this._displayCssValue(color, fallbackColor);
    const safeOpacity = this._clampOpacity(opacity, 1);

    return `color-mix(
      in srgb,
      ${safeColor} ${safeOpacity * 100}%,
      transparent
    )`;
  }

  _getStatusIndicatorStyle() {
    const value = String(this._config?.status_indicator_style || "dot").trim().toLowerCase();
    if (["dot", "bar", "none"].includes(value)) return value;
    return "dot";
  }

  _getStatusBarWidth() {
    return this._clampPositiveNumber(this._config?.status_bar_width, 6);
  }

  _getChildAliases() {
    return this._normalizeMap(this._config?.child_aliases);
  }

  _getSubjectAliases() {
    return this._normalizeMap(this._config?.subject_aliases);
  }

  _applyAlias(value, aliases) {
    const raw = String(value ?? "").trim();
    if (!raw) return "";

    const entries = Object.entries(aliases || {});
    const match = entries.find(([key]) => key.trim().toLowerCase() === raw.toLowerCase());
    return match ? match[1] : raw;
  }

  _displayChildName(value) {
    return this._applyAlias(value, this._getChildAliases());
  }

  _displaySubjectName(value) {
    return this._applyAlias(value, this._getSubjectAliases());
  }

  _matchesChildFilter(item) {
    const childFilter = this._normalizeStringArray(this._config?.child_filter);
    if (childFilter.length === 0) return true;

    const rawChild = String(item?.barn || "").trim();
    const displayChild = this._displayChildName(rawChild);

    const candidates = [rawChild, displayChild]
      .map((v) => v.trim().toLowerCase())
      .filter(Boolean);

    return childFilter.some((name) => candidates.includes(name.trim().toLowerCase()));
  }

  _matchesSubjectFilter(item) {
    const subjectFilter = this._normalizeStringArray(this._config?.subject_filter);
    if (subjectFilter.length === 0) return true;

    const rawSubject = String(item?.fag || "").trim();
    const displaySubject = this._displaySubjectName(rawSubject);

    const candidates = [rawSubject, displaySubject]
      .map((v) => v.trim().toLowerCase())
      .filter(Boolean);

    return subjectFilter.some((name) => candidates.includes(name.trim().toLowerCase()));
  }

  _matchesDerivedFilter(item) {
    const showDerivedItems = this._config?.show_derived_items !== false;
    return showDerivedItems ? true : !Boolean(item?.derived);
  }

  _getDayDifference(dateStr) {
    if (!dateStr) return null;

    try {
      const target = new Date(`${dateStr}T00:00:00`);
      if (Number.isNaN(target.getTime())) return null;

      const today = new Date();
      today.setHours(0, 0, 0, 0);

      const diffMs = target.getTime() - today.getTime();
      return Math.round(diffMs / 86400000);
    } catch {
      return null;
    }
  }

  _matchesDisplayPeriod(item) {
    const mode = String(this._config?.display_period || "current_and_future").trim().toLowerCase();
    const dayDiff = this._getDayDifference(item?.dato);

    if (dayDiff === null) return true;
    if (mode === "all") return true;
    if (mode === "future_only") return dayDiff >= 1;
    return dayDiff >= 0;
  }

  _getVisibleItems() {
    let items = this._getItems();

    items = items.filter((item) => this._matchesDisplayPeriod(item));
    items = items.filter((item) => this._matchesChildFilter(item));
    items = items.filter((item) => this._matchesSubjectFilter(item));
    items = items.filter((item) => this._matchesDerivedFilter(item));

    if (this._hideCompleted) {
      items = items.filter((item) => !item.completed);
    }

    return this._sortItems(items);
  }

  _sortItems(items) {
    return [...items].sort((a, b) => {
      const aCompleted = Boolean(a?.completed);
      const bCompleted = Boolean(b?.completed);

      if (aCompleted !== bCompleted) return aCompleted ? 1 : -1;

      const aDiff = this._getDayDifference(a?.dato);
      const bDiff = this._getDayDifference(b?.dato);

      if (aDiff !== bDiff) {
        return (aDiff ?? 9999) - (bDiff ?? 9999);
      }

      const aChild = this._displayChildName(a?.barn || "");
      const bChild = this._displayChildName(b?.barn || "");
      if (aChild !== bChild) {
        return String(aChild).localeCompare(String(bChild), "da");
      }

      const aTitle = this._displaySubjectName(a?.title || a?.fag || "");
      const bTitle = this._displaySubjectName(b?.title || b?.fag || "");
      return String(aTitle).localeCompare(String(bTitle), "da");
    });
  }

  _groupItemsByDate(items) {
    const grouped = new Map();

    for (const item of items) {
      const key = item?.dato || "Uden dato";
      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key).push(item);
    }

    return Array.from(grouped.entries()).sort((a, b) => String(a[0]).localeCompare(String(b[0])));
  }

  _groupItemsByChild(items) {
    const grouped = new Map();

    for (const item of items) {
      const rawChild = (item?.barn || "Ukendt").trim() || "Ukendt";
      const displayChild = this._displayChildName(rawChild);

      if (!grouped.has(displayChild)) grouped.set(displayChild, []);
      grouped.get(displayChild).push(item);
    }

    return Array.from(grouped.entries())
      .sort((a, b) => String(a[0]).localeCompare(String(b[0]), "da"))
      .map(([childName, childItems]) => [childName, this._sortItems(childItems)]);
  }

  _escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  _formatDate(dateStr) {
    if (!dateStr) return "Uden dato";

    try {
      const date = new Date(`${dateStr}T00:00:00`);
      if (Number.isNaN(date.getTime())) return dateStr;

      return new Intl.DateTimeFormat("da-DK", {
        weekday: "long",
        day: "numeric",
        month: "long",
      }).format(date);
    } catch {
      return dateStr;
    }
  }

  _getStatusInfo(item) {
    const showStatusBadge = this._config?.show_status_badge !== false;

    if (item?.completed) {
      return {
        key: "done",
        dotClass: "done",
        badgeClass: "done-badge",
        badgeText: showStatusBadge ? String(this._config?.status_label_done || "Færdig") : "",
        buttonClass: "secondary",
        buttonText: String(this._config?.button_label_undo || "Fortryd"),
      };
    }

    const dayDiff = this._getDayDifference(item?.dato);
    if (dayDiff !== null && dayDiff <= 1) {
      return {
        key: "urgent",
        dotClass: "urgent",
        badgeClass: "urgent-badge",
        badgeText: showStatusBadge ? String(this._config?.status_label_urgent || "Mangler") : "",
        buttonClass: "",
        buttonText: String(this._config?.button_label_done || "Færdig"),
      };
    }

    return {
      key: "open",
      dotClass: "open",
      badgeClass: "open-badge",
      badgeText: showStatusBadge ? String(this._config?.status_label_open || "Mangler") : "",
      buttonClass: "",
      buttonText: String(this._config?.button_label_done || "Færdig"),
    };
  }

  _normalizeDerivedText(text) {
    if (!text) return "";
    return String(text).replace(/^Diktat:\s*/i, "Diktatord: ");
  }

  _getTitleFontSize() {
    const value = String(this._config?.title_font_size ?? "").trim();
    return value ? this._getRemSize(value, 1.5) : "var(--ha-card-header-font-size, 24px)";
  }

  _getTextFontSize() {
    const value = String(this._config?.text_font_size ?? "").trim();
    return value ? this._getRemSize(value, 1) : "1rem";
  }

  _getDateFontSize() {
    const value = String(this._config?.date_font_size ?? "").trim();
    return value ? this._getRemSize(value, 0.95) : "0.95rem";
  }

  _getChildFontSize() {
    const value = String(this._config?.child_font_size ?? "").trim();
    return value ? this._getRemSize(value, 0.95) : "0.95rem";
  }

  _getSubjectTitleFontSize() {
    const value = String(this._config?.subject_title_font_size ?? "").trim();
    return value ? this._getRemSize(value, 1) : "1rem";
  }

  _getButtonFontSize() {
    const value = String(this._config?.button_font_size ?? "").trim();
    return value ? this._getRemSize(value, 0.9) : "0.9rem";
  }

  _getBadgeFontSize() {
    const value = String(this._config?.badge_font_size ?? "").trim();
    return value ? this._getRemSize(value, 0.75) : "0.75rem";
  }

  _getCardBorderRadius() {
    const value = this._parseLocalizedNumber(this._config?.card_border_radius, 14);
    if (Number.isFinite(value)) return Math.max(0, value);
    return 14;
  }

  _getLegacyCardBackgroundOpacity() {
    return this._clampOpacity(this._config?.card_background_opacity, 1);
  }

  _getOuterCardBackgroundColor() {
    return this._displayCssValue(this._config?.outer_card_background_color, "var(--card-background-color)");
  }

  _getOuterCardBackgroundOpacity() {
    const legacy = this._getLegacyCardBackgroundOpacity();
    return this._clampOpacity(this._config?.outer_card_background_opacity, legacy);
  }

  _getGroupCardBackgroundColor() {
    return this._displayCssValue(this._config?.group_card_background_color, "var(--card-background-color)");
  }

  _getGroupCardBackgroundOpacity() {
    const legacy = Math.min(1, Math.max(0, this._getLegacyCardBackgroundOpacity() * 0.92));
    return this._clampOpacity(this._config?.group_card_background_opacity, legacy);
  }

  _getItemCardBackgroundColor() {
    return this._displayCssValue(this._config?.item_card_background_color, "var(--card-background-color)");
  }

  _getItemCardBackgroundOpacity() {
    const legacy = this._getLegacyCardBackgroundOpacity();
    return this._clampOpacity(this._config?.item_card_background_opacity, legacy);
  }

  _getStatusColorOpen() {
    return String(this._config?.status_color_open || "#ffb300").trim();
  }

  _getStatusColorUrgent() {
    return String(this._config?.status_color_urgent || "#e53935").trim();
  }

  _getStatusColorDone() {
    return String(this._config?.status_color_done || "#43a047").trim();
  }

  _hexToRgba(hex, alpha = 0.18) {
    const value = String(hex || "").trim();

    const shortMatch = value.match(/^#([0-9a-fA-F]{3})$/);
    if (shortMatch) {
      const h = shortMatch[1];
      const r = parseInt(h[0] + h[0], 16);
      const g = parseInt(h[1] + h[1], 16);
      const b = parseInt(h[2] + h[2], 16);
      return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }

    const longMatch = value.match(/^#([0-9a-fA-F]{6})$/);
    if (longMatch) {
      const h = longMatch[1];
      const r = parseInt(h.slice(0, 2), 16);
      const g = parseInt(h.slice(2, 4), 16);
      const b = parseInt(h.slice(4, 6), 16);
      return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }

    return value;
  }

  async _toggleHomework(item) {
    if (!this._hass || !item?.homework_id) return;

    const service = item.completed ? "mark_homework_undone" : "mark_homework_done";

    try {
      await this._hass.callService("foraeldreintra", service, {
        homework_id: item.homework_id,
      });
    } catch (err) {
      console.error("Kunne ikke opdatere lektie-status", err);
    }
  }

  _toggleHideCompleted() {
    this._hideCompleted = !this._hideCompleted;
    this._saveHideCompletedPreference(this._hideCompleted);
    this._render();
  }

  _renderHomeworkRow(item, options = {}) {
    const { showChild = false, compact = false } = options;

    const rawSubject = (item.fag || "").trim();
    const displaySubject = this._displaySubjectName(rawSubject).trim();
    const titleRaw = (item.title || item.fag || "Lektie").trim();
    const isDerived = Boolean(item.derived);

    const displayTextRaw = isDerived
      ? this._normalizeDerivedText(item.tekst || "")
      : item.tekst || "";

    const text = this._escapeHtml(displayTextRaw);
    const title = this._escapeHtml(displaySubject || titleRaw);
    const subject = this._escapeHtml(displaySubject);
    const child = this._escapeHtml(this._displayChildName(item.barn || ""));
    const status = this._getStatusInfo(item);

    const showSubjectInMeta =
      !isDerived &&
      rawSubject &&
      titleRaw &&
      displaySubject &&
      displaySubject.toLowerCase() !== String(titleRaw).trim().toLowerCase();

    const indicatorStyle = this._getStatusIndicatorStyle();
    const showStatusDot = indicatorStyle === "dot";
    const showStatusBadge = this._config?.show_status_badge !== false;
    const showDerivedBadge = this._config?.show_derived_badge !== false;
    const showToggleButton = this._config?.show_toggle_button !== false;
    const showChildInMeta = this._config?.show_child_in_meta !== false;
    const derivedBadgeLabel = String(this._config?.derived_badge_label || "Fra ugeplan");

    return `
      <div class="item ${item.completed ? "completed" : ""} ${compact ? "compact" : ""} indicator-${indicatorStyle} indicator-${status.dotClass}">
        ${indicatorStyle === "bar" ? `<div class="status-bar ${status.dotClass}"></div>` : ""}

        <div class="item-top">
          <div class="title-wrap">
            <div class="title-row">
              ${showStatusDot ? `<span class="status-dot ${status.dotClass}"></span>` : ""}
              <span class="title">${title}</span>
              ${
                showStatusBadge && status.badgeText
                  ? `<span class="status-badge ${status.badgeClass}">${this._escapeHtml(status.badgeText)}</span>`
                  : ""
              }
            </div>

            ${
              (showChild && showChildInMeta && child) || showSubjectInMeta
                ? `
                  <div class="meta">
                    ${showChild && showChildInMeta && child ? `<span class="meta-child">${child}</span>` : ""}
                    ${showSubjectInMeta ? `<span class="meta-subject">${subject}</span>` : ""}
                  </div>
                `
                : ""
            }
          </div>

          ${
            showToggleButton
              ? `
                <button class="toggle-btn ${status.buttonClass}" data-homework-id="${this._escapeHtml(item.homework_id || "")}">
                  ${this._escapeHtml(status.buttonText)}
                </button>
              `
              : ""
          }
        </div>

        ${text ? `<div class="text">${text}</div>` : ""}
        ${
          isDerived && showDerivedBadge
            ? `<div class="source-note"><span class="derived-badge bottom">${this._escapeHtml(derivedBadgeLabel)}</span></div>`
            : ""
        }
      </div>
    `;
  }

  _renderChildGroup(childName, childItems, options = {}) {
    const childLabel = this._escapeHtml(childName);
    const compact = Boolean(options.compact);
    const showChildHeader = this._config?.show_child_header !== false;

    const rows = childItems
      .map((item) =>
        this._renderHomeworkRow(item, {
          showChild: false,
          compact,
        })
      )
      .join("");

    return `
      <div class="child-group ${compact ? "compact" : ""}">
        ${showChildHeader ? `<div class="child-header">${childLabel}</div>` : ""}
        <div class="child-items">
          ${rows}
        </div>
      </div>
    `;
  }

  _renderDateGroup(dateKey, dateItems) {
    const groupTitle = this._escapeHtml(this._formatDate(dateKey));
    const groupByChild = this._config?.group_by_child !== false;
    const compact = Boolean(this._config?.compact);
    const showDateHeaders = this._config?.show_date_headers !== false;

    let content = "";

    if (groupByChild) {
      const childGroups = this._groupItemsByChild(dateItems);
      content = childGroups
        .map(([childName, childItems]) =>
          this._renderChildGroup(childName, childItems, { compact })
        )
        .join("");
    } else {
      const sortedItems = this._sortItems(dateItems);
      content = sortedItems
        .map((item) =>
          this._renderHomeworkRow(item, {
            showChild: true,
            compact,
          })
        )
        .join("");
    }

    return `
      <div class="date-group ${compact ? "compact" : ""} ${showDateHeaders ? "" : "no-date-header"}">
        ${showDateHeaders ? `<div class="date-header">${groupTitle}</div>` : ""}
        <div class="date-items">
          ${content}
        </div>
      </div>
    `;
  }

  _render() {
    if (!this.shadowRoot || !this._config) {
      return;
    }

    const stateObj = this._getEntityState();
    const items = this._getVisibleItems();
    const showFilterButton = this._config?.show_filter_button !== false;

    if (!this._hass) {
      this.shadowRoot.innerHTML = `
        <ha-card>
          <div class="card-content">Indlæser...</div>
        </ha-card>
      `;
      return;
    }

    if (!stateObj) {
      this.shadowRoot.innerHTML = `
        <ha-card>
          <div class="card-header">${this._escapeHtml(this._config.title)}</div>
          <div class="card-content error">
            Entity ikke fundet: ${this._escapeHtml(this._config.entity)}
          </div>
        </ha-card>
        ${this._style()}
      `;
      return;
    }

    const grouped = this._groupItemsByDate(items);

    this.shadowRoot.innerHTML = `
      <ha-card class="${this._config?.compact ? "compact" : ""}">
        <div class="card-header-row ${this._config?.compact ? "compact" : ""}">
          <div class="card-header">${this._escapeHtml(this._config.title)}</div>
          ${
            showFilterButton
              ? `
                <button class="filter-btn ${this._config?.compact ? "compact" : ""}">
                  ${
                    this._hideCompleted
                      ? this._escapeHtml(this._config?.filter_label_show_completed || "Vis færdige")
                      : this._escapeHtml(this._config?.filter_label_hide_completed || "Skjul færdige")
                  }
                </button>
              `
              : ""
          }
        </div>

        <div class="card-content ${this._config?.compact ? "compact" : ""}">
          ${
            grouped.length > 0
              ? grouped.map(([dateKey, dateItems]) => this._renderDateGroup(dateKey, dateItems)).join("")
              : `<div class="empty">Ingen lektier at vise</div>`
          }
        </div>
      </ha-card>
      ${this._style()}
    `;

    const filterBtn = this.shadowRoot.querySelector(".filter-btn");
    if (filterBtn) {
      filterBtn.addEventListener("click", () => this._toggleHideCompleted());
    }

    this.shadowRoot.querySelectorAll(".toggle-btn").forEach((button) => {
      button.addEventListener("click", async (ev) => {
        const homeworkId = ev.currentTarget?.dataset?.homeworkId;
        const item = this._getItems().find((entry) => entry.homework_id === homeworkId);
        if (item) {
          await this._toggleHomework(item);
        }
      });
    });
  }

  _style() {
    const titleFontSize = this._getTitleFontSize();
    const textFontSize = this._getTextFontSize();
    const dateFontSize = this._getDateFontSize();
    const childFontSize = this._getChildFontSize();
    const subjectTitleFontSize = this._getSubjectTitleFontSize();
    const buttonFontSize = this._getButtonFontSize();
    const badgeFontSize = this._getBadgeFontSize();
    const radius = this._getCardBorderRadius();
    const statusBarWidth = this._getStatusBarWidth();

    const outerCardBg = this._colorWithOpacity(
      this._getOuterCardBackgroundColor(),
      this._getOuterCardBackgroundOpacity()
    );
    const groupCardBg = this._colorWithOpacity(
      this._getGroupCardBackgroundColor(),
      this._getGroupCardBackgroundOpacity()
    );
    const itemCardBg = this._colorWithOpacity(
      this._getItemCardBackgroundColor(),
      this._getItemCardBackgroundOpacity()
    );

    const statusColorOpen = this._getStatusColorOpen();
    const statusColorUrgent = this._getStatusColorUrgent();
    const statusColorDone = this._getStatusColorDone();

    const statusBgOpen = this._hexToRgba(statusColorOpen, 0.18);
    const statusBgUrgent = this._hexToRgba(statusColorUrgent, 0.18);
    const statusBgDone = this._hexToRgba(statusColorDone, 0.18);

    const titleTextColor = this._displayCssValue(this._config?.title_text_color, "var(--primary-text-color)");
    const textColor = this._displayCssValue(this._config?.text_color, "var(--primary-text-color)");
    const dateTextColor = this._displayCssValue(this._config?.date_text_color, "var(--secondary-text-color)");
    const childTextColor = this._displayCssValue(this._config?.child_text_color, "var(--primary-text-color)");
    const metaTextColor = this._displayCssValue(this._config?.meta_text_color, "var(--secondary-text-color)");

    const toggleButtonBg = this._displayCssValue(this._config?.toggle_button_background_color, "var(--primary-color)");
    const toggleButtonText = this._displayCssValue(this._config?.toggle_button_text_color, "var(--text-primary-color)");
    const toggleButtonSecondaryBg = this._displayCssValue(
      this._config?.toggle_button_secondary_background_color,
      "var(--secondary-background-color)"
    );
    const toggleButtonSecondaryText = this._displayCssValue(
      this._config?.toggle_button_secondary_text_color,
      "var(--primary-text-color)"
    );

    const derivedBadgeBg = this._displayCssValue(
      this._config?.derived_badge_background_color,
      "rgba(66, 133, 244, 0.18)"
    );
    const derivedBadgeText = this._displayCssValue(
      this._config?.derived_badge_text_color,
      "var(--primary-text-color)"
    );

    return `
      <style>
        :host {
          display: block;
          --fi-title-font-size: ${titleFontSize};
          --fi-text-font-size: ${textFontSize};
          --fi-date-font-size: ${dateFontSize};
          --fi-child-font-size: ${childFontSize};
          --fi-subject-title-font-size: ${subjectTitleFontSize};
          --fi-button-font-size: ${buttonFontSize};
          --fi-badge-font-size: ${badgeFontSize};
          --fi-radius: ${radius}px;
          --fi-radius-compact: ${Math.max(6, radius - 4)}px;
          --fi-status-bar-width: ${statusBarWidth}px;

          --fi-outer-card-bg: ${outerCardBg};
          --fi-group-card-bg: ${groupCardBg};
          --fi-item-card-bg: ${itemCardBg};

          --fi-status-color-open: ${statusColorOpen};
          --fi-status-color-urgent: ${statusColorUrgent};
          --fi-status-color-done: ${statusColorDone};

          --fi-status-bg-open: ${statusBgOpen};
          --fi-status-bg-urgent: ${statusBgUrgent};
          --fi-status-bg-done: ${statusBgDone};

          --fi-title-text-color: ${titleTextColor};
          --fi-text-color: ${textColor};
          --fi-date-text-color: ${dateTextColor};
          --fi-child-text-color: ${childTextColor};
          --fi-meta-text-color: ${metaTextColor};

          --fi-toggle-button-bg: ${toggleButtonBg};
          --fi-toggle-button-text: ${toggleButtonText};
          --fi-toggle-button-secondary-bg: ${toggleButtonSecondaryBg};
          --fi-toggle-button-secondary-text: ${toggleButtonSecondaryText};

          --fi-derived-badge-bg: ${derivedBadgeBg};
          --fi-derived-badge-text: ${derivedBadgeText};
        }

        :host([hidden]) {
          display: none;
        }

        * {
          box-sizing: border-box;
        }

        ha-card {
          overflow: hidden;
          border-radius: var(--fi-radius);
          background: var(--fi-outer-card-bg);
        }

        .card-header-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 12px;
          padding: 16px 16px 0 16px;
        }

        .card-header-row.compact {
          gap: 8px;
          padding: 12px 12px 0 12px;
        }

        .card-header {
          font-size: var(--fi-title-font-size);
          font-weight: var(--ha-card-header-font-weight, 400);
          line-height: var(--ha-card-header-line-height, 32px);
          letter-spacing: var(--ha-card-header-letter-spacing, -0.012em);
          font-family: var(--ha-card-header-font-family, inherit);
          min-width: 0;
          color: var(--fi-title-text-color);
        }

        .card-content {
          padding: 16px;
          padding-top: 12px;
        }

        .card-content.compact {
          padding: 12px;
          padding-top: 8px;
        }

        .filter-btn {
          border: 1px solid var(--divider-color);
          border-radius: calc(var(--fi-radius) - 4px);
          padding: 8px 12px;
          cursor: pointer;
          background: transparent;
          color: var(--primary-text-color);
          font: inherit;
          white-space: nowrap;
          font-size: var(--fi-button-font-size);
        }

        .filter-btn.compact {
          border-radius: calc(var(--fi-radius-compact) - 2px);
          padding: 6px 10px;
        }

        .date-group {
          margin-bottom: 18px;
        }

        .date-group.compact {
          margin-bottom: 10px;
        }

        .date-group:last-child {
          margin-bottom: 0;
        }

        .date-header {
          font-size: var(--fi-date-font-size);
          font-weight: 700;
          color: var(--fi-date-text-color);
          margin-bottom: 10px;
          text-transform: capitalize;
        }

        .date-group.compact .date-header {
          margin-bottom: 6px;
        }

        .date-items {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .date-group.compact .date-items {
          gap: 6px;
        }

        .child-group {
          border: 1px solid var(--divider-color);
          border-radius: var(--fi-radius);
          padding: 12px;
          background: var(--fi-group-card-bg);
        }

        .child-group.compact {
          padding: 8px;
          border-radius: var(--fi-radius-compact);
        }

        .child-header {
          font-size: var(--fi-child-font-size);
          font-weight: 700;
          margin-bottom: 10px;
          color: var(--fi-child-text-color);
        }

        .child-group.compact .child-header {
          margin-bottom: 6px;
        }

        .child-items {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .child-group.compact .child-items {
          gap: 6px;
        }

        .item {
          position: relative;
          border: 1px solid var(--divider-color);
          border-radius: var(--fi-radius);
          padding: 12px;
          background: var(--fi-item-card-bg);
          overflow: hidden;
        }

        .item.completed {
          opacity: 0.72;
        }

        .item.compact {
          padding: 8px;
          border-radius: var(--fi-radius-compact);
        }

        .item.indicator-bar {
          padding-left: calc(12px + var(--fi-status-bar-width) + 8px);
        }

        .item.compact.indicator-bar {
          padding-left: calc(8px + var(--fi-status-bar-width) + 6px);
        }

        .status-bar {
          position: absolute;
          left: 0;
          top: 0;
          bottom: 0;
          width: var(--fi-status-bar-width);
          border-top-left-radius: inherit;
          border-bottom-left-radius: inherit;
        }

        .status-bar.open {
          background: var(--fi-status-color-open);
        }

        .status-bar.urgent {
          background: var(--fi-status-color-urgent);
        }

        .status-bar.done {
          background: var(--fi-status-color-done);
        }

        .item-top {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 10px;
        }

        .title-wrap {
          min-width: 0;
          flex: 1;
        }

        .title-row {
          display: flex;
          align-items: center;
          gap: 8px;
          flex-wrap: wrap;
          min-width: 0;
        }

        .title {
          font-size: var(--fi-subject-title-font-size);
          font-weight: 700;
          color: var(--fi-text-color);
          min-width: 0;
          word-break: break-word;
        }

        .status-dot {
          width: 9px;
          height: 9px;
          border-radius: 50%;
          flex: 0 0 auto;
        }

        .status-dot.open {
          background: var(--fi-status-color-open);
        }

        .status-dot.urgent {
          background: var(--fi-status-color-urgent);
        }

        .status-dot.done {
          background: var(--fi-status-color-done);
        }

        .status-badge,
        .derived-badge {
          display: inline-flex;
          align-items: center;
          border-radius: 999px;
          padding: 4px 8px;
          font-size: var(--fi-badge-font-size);
          font-weight: 700;
          line-height: 1.2;
          white-space: nowrap;
        }

        .status-badge.open-badge {
          background: var(--fi-status-bg-open);
          color: var(--fi-status-color-open);
        }

        .status-badge.urgent-badge {
          background: var(--fi-status-bg-urgent);
          color: var(--fi-status-color-urgent);
        }

        .status-badge.done-badge {
          background: var(--fi-status-bg-done);
          color: var(--fi-status-color-done);
        }

        .derived-badge {
          background: var(--fi-derived-badge-bg);
          color: var(--fi-derived-badge-text);
        }

        .meta {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
          margin-top: 4px;
          color: var(--fi-meta-text-color);
          font-size: var(--fi-date-font-size);
          line-height: 1.35;
        }

        .text {
          margin-top: 10px;
          color: var(--fi-text-color);
          font-size: var(--fi-text-font-size);
          line-height: 1.5;
          white-space: pre-wrap;
        }

        .item.compact .text {
          margin-top: 8px;
        }

        .source-note {
          margin-top: 8px;
          display: flex;
          justify-content: flex-start;
        }

        .toggle-btn {
          border: none;
          border-radius: calc(var(--fi-radius) - 4px);
          padding: 8px 12px;
          cursor: pointer;
          font: inherit;
          font-size: var(--fi-button-font-size);
          white-space: nowrap;
          background: var(--fi-toggle-button-bg);
          color: var(--fi-toggle-button-text);
          flex: 0 0 auto;
        }

        .toggle-btn.secondary {
          background: var(--fi-toggle-button-secondary-bg);
          color: var(--fi-toggle-button-secondary-text);
        }

        .item.compact .toggle-btn {
          padding: 6px 10px;
          border-radius: calc(var(--fi-radius-compact) - 2px);
        }

        .empty,
        .error {
          color: var(--fi-meta-text-color);
          font-size: var(--fi-text-font-size);
          line-height: 1.5;
        }

        @media (max-width: 600px) {
          .card-header-row,
          .card-header-row.compact {
            align-items: flex-start;
            flex-direction: column;
          }

          .item-top {
            flex-direction: column;
          }

          .toggle-btn,
          .filter-btn {
            width: 100%;
          }
        }
      </style>
    `;
  }

  static getConfigElement() {
    return document.createElement("foraeldreintra-homework-card-editor");
  }

  static getStubConfig() {
    return {
      entity: "sensor.foraeldreintra_lektier_alle",
      title: "Lektier",

      display_period: "current_and_future",
      hide_completed: false,
      child_filter: [],
      subject_filter: [],
      child_aliases: {},
      subject_aliases: {},
      show_derived_items: true,

      group_by_child: true,
      show_date_headers: true,
      show_child_header: true,
      show_child_in_meta: true,
      compact: false,

      status_label_open: "Mangler",
      status_label_urgent: "Mangler",
      status_label_done: "Færdig",
      button_label_done: "Færdig",
      button_label_undo: "Fortryd",
      filter_label_show_completed: "Vis færdige",
      filter_label_hide_completed: "Skjul færdige",
      derived_badge_label: "Fra ugeplan",

      show_status_badge: true,
      show_derived_badge: true,
      show_filter_button: true,
      show_toggle_button: true,
      status_indicator_style: "dot",
      status_bar_width: 15,

      title_font_size: "",
      text_font_size: "",
      date_font_size: "",
      child_font_size: "",
      subject_title_font_size: "",
      button_font_size: "",
      badge_font_size: "",

      card_border_radius: 14,
      card_background_opacity: 1,

      outer_card_background_color: "var(--card-background-color)",
      outer_card_background_opacity: "0,35",
      group_card_background_color: "var(--card-background-color)",
      group_card_background_opacity: "0,55",
      item_card_background_color: "var(--card-background-color)",
      item_card_background_opacity: "0,75",

      status_color_open: "#ffb300",
      status_color_urgent: "#e53935",
      status_color_done: "#43a047",

      title_text_color: "var(--primary-text-color)",
      text_color: "var(--primary-text-color)",
      date_text_color: "var(--secondary-text-color)",
      child_text_color: "var(--primary-text-color)",
      meta_text_color: "var(--secondary-text-color)",

      toggle_button_background_color: "var(--primary-color)",
      toggle_button_text_color: "var(--text-primary-color)",
      toggle_button_secondary_background_color: "var(--secondary-background-color)",
      toggle_button_secondary_text_color: "var(--primary-text-color)",

      derived_badge_background_color: "rgba(66, 133, 244, 0.18)",
      derived_badge_text_color: "var(--primary-text-color)",
    };
  }
}

customElements.define("foraeldreintra-homework-card", ForaeldreIntraHomeworkCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "foraeldreintra-homework-card",
  name: "ForældreIntra Homework Card",
  description: `Viser lektier og giver mulighed for at markere dem som lavet. (v${FORAELDREINTRA_HOMEWORK_CARD_VERSION})`,
  preview: true,
});