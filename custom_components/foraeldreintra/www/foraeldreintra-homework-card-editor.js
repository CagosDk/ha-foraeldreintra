const FORAELDREINTRA_HOMEWORK_CARD_EDITOR_VERSION = "1.0.0";

class ForaeldreintraHomeworkCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
    this._sectionState = {
      basic: true,
      visibility: true,
      status: true,
      texts: false,
      typography: false,
      layers: true,
    };
  }

  static get defaults() {
    return {
      entity: "",
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
      status_bar_width: "6",

      title_font_size: "",
      text_font_size: "",
      date_font_size: "",
      child_font_size: "",
      subject_title_font_size: "",
      button_font_size: "",
      badge_font_size: "",

      card_border_radius: "14",
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

  setConfig(config) {
    this._config = {
      ...ForaeldreintraHomeworkCardEditor.defaults,
      ...(config || {}),
    };
    this._render();
  }

  set hass(hass) {
    const hadStates = Boolean(this._hass?.states);
    const hasStates = Boolean(hass?.states);

    this._hass = hass;

    if (!this.shadowRoot?.hasChildNodes()) {
      this._render();
      return;
    }

    if (!hadStates && hasStates) {
      this._render();
    }
  }

  _emitConfig(rawConfig) {
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config: rawConfig },
        bubbles: true,
        composed: true,
      })
    );
  }

  _saveSectionState() {
    this.shadowRoot?.querySelectorAll("details[data-section]").forEach((el) => {
      this._sectionState[el.dataset.section] = el.open;
    });
  }

  _rerenderAfterUpdate() {
    this._saveSectionState();
    this._render();
  }

  _setConfigValue(key, value) {
    const rawConfig = { ...this._config };

    if (value === "" || value === null || value === undefined) {
      delete rawConfig[key];
    } else {
      rawConfig[key] = value;
    }

    this._config = {
      ...ForaeldreintraHomeworkCardEditor.defaults,
      ...rawConfig,
    };

    this._emitConfig(rawConfig);
  }

  _onTextCommit(ev) {
    const key = ev.target.dataset.key;
    this._setConfigValue(key, ev.target.value);
  }

  _onCheckboxInput(ev) {
    const key = ev.target.dataset.key;
    this._setConfigValue(key, ev.target.checked);
  }

  _onSelectInput(ev) {
    const key = ev.target.dataset.key;
    this._setConfigValue(key, ev.target.value);

    if (key === "status_indicator_style") {
      this._rerenderAfterUpdate();
    }
  }

  _fieldText(label, key, helper = "", placeholder = "") {
    const value = this._config?.[key] ?? "";
    return `
      <label class="field">
        <span class="label">${label}</span>
        <input
          class="input"
          type="text"
          data-key="${key}"
          value="${this._escape(String(value))}"
          placeholder="${this._escape(placeholder)}"
        />
        ${helper ? `<span class="helper">${helper}</span>` : ""}
      </label>
    `;
  }

  _fieldSelect(label, key, options = [], helper = "") {
    const value = String(this._config?.[key] ?? "");
    const optionHtml = options
      .map(
        (opt) => `
          <option value="${this._escape(opt.value)}" ${value === opt.value ? "selected" : ""}>
            ${this._escape(opt.label)}
          </option>
        `
      )
      .join("");

    return `
      <label class="field">
        <span class="label">${label}</span>
        <select class="input" data-key="${key}">
          ${optionHtml}
        </select>
        ${helper ? `<span class="helper">${helper}</span>` : ""}
      </label>
    `;
  }

  _fieldToggle(label, key, helper = "") {
    const checked = Boolean(this._config?.[key]);
    return `
      <label class="toggle">
        <span class="toggle-left">
          <span class="label">${label}</span>
          ${helper ? `<span class="helper">${helper}</span>` : ""}
        </span>
        <input type="checkbox" data-key="${key}" ${checked ? "checked" : ""} />
      </label>
    `;
  }

  _buildEntityOptions(selectedValue = "") {
    if (!this._hass?.states) {
      return "";
    }

    return Object.values(this._hass.states)
      .filter((stateObj) => String(stateObj.entity_id || "").startsWith("sensor."))
      .sort((a, b) => {
        const aName = a.attributes?.friendly_name || a.entity_id;
        const bName = b.attributes?.friendly_name || b.entity_id;
        return String(aName).localeCompare(String(bName), "da");
      })
      .map((stateObj) => {
        const entityId = stateObj.entity_id;
        const friendlyName = stateObj.attributes?.friendly_name || entityId;
        const label = `${friendlyName} (${entityId})`;
        const selected = entityId === selectedValue ? "selected" : "";
        return `<option value="${this._escape(entityId)}" ${selected}>${this._escape(label)}</option>`;
      })
      .join("");
  }

  _fieldEntity(label, helper = "") {
    const value = String(this._config?.entity ?? "");

    return `
      <label class="field field-full">
        <span class="label">${label}</span>
        <select class="input" data-key="entity">
          <option value="">Vælg sensor…</option>
          ${this._buildEntityOptions(value)}
        </select>
        ${helper ? `<span class="helper">${helper}</span>` : ""}
      </label>
    `;
  }

  _subTitle(text) {
    return `<div class="sub-title">${text}</div>`;
  }

  _section(key, title, description, content) {
    const isOpen = this._sectionState[key] !== false;
    return `
      <details class="section" data-section="${key}" ${isOpen ? "open" : ""}>
        <summary>
          <div class="section-head">
            <div class="section-title">${title}</div>
            ${description ? `<div class="section-description">${description}</div>` : ""}
          </div>
        </summary>
        <div class="section-body">
          ${content}
        </div>
      </details>
    `;
  }

  _escape(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  _render() {
    if (!this.shadowRoot) return;

    const indicatorStyle = String(this._config?.status_indicator_style || "dot");

    const basicSection = this._section(
      "basic",
      "Grundlæggende",
      "De vigtigste indstillinger for kortet.",
      `
        ${this._fieldEntity("Entity", "Vælg den sensor som kortet skal læse fra.")}

        <div class="grid two">
          ${this._fieldText("Titel", "title", 'Default: "Lektier"', "Lektier")}
          ${this._fieldSelect(
            "Periode",
            "display_period",
            [
              { value: "current_and_future", label: "I dag og frem" },
              { value: "future_only", label: "Kun fremtidige" },
              { value: "all", label: "Alle" },
            ],
            "Bestemmer om kortet viser lektier fra i dag og frem, kun fremtidige eller alle."
          )}
        </div>

        <div class="toggles two-cols">
          ${this._fieldToggle("Kompakt visning", "compact")}
          ${this._fieldToggle("Gruppér efter barn", "group_by_child")}
        </div>
      `
    );

    const visibilitySection = this._section(
      "visibility",
      "Synlighed",
      "Styr hvilke elementer der vises i kortet.",
      `
        ${this._subTitle("Status og handlinger")}
        <div class="toggles">
          ${this._fieldToggle("Vis status-badge", "show_status_badge")}
          ${this._fieldToggle("Vis Færdig/Fortryd-knap", "show_toggle_button")}
          ${this._fieldToggle("Vis filterknap", "show_filter_button")}
        </div>

        ${this._subTitle("Struktur")}
        <div class="toggles">
          ${this._fieldToggle("Vis datooverskrifter", "show_date_headers")}
          ${this._fieldToggle("Vis børneoverskrift", "show_child_header")}
          ${this._fieldToggle("Vis barn i meta", "show_child_in_meta")}
        </div>

        ${this._subTitle("Ekstra")}
        <div class="toggles">
          ${this._fieldToggle("Vis ugeplan-badge", "show_derived_badge")}
        </div>
      `
    );

    let statusTopRow = `
      <div class="grid status-top-row ${indicatorStyle === "bar" ? "two" : "one"}">
        ${this._fieldSelect(
          "Statusindikator",
          "status_indicator_style",
          [
            { value: "dot", label: "Prik" },
            { value: "bar", label: "Venstre farvebar" },
            { value: "none", label: "Ingen indikator" },
          ],
          'Default: "Prik"'
        )}
        ${
          indicatorStyle === "bar"
            ? this._fieldText("Bredde på farvebar", "status_bar_width", 'Default: "6"', "6")
            : ""
        }
      </div>
    `;

    let statusColorRow = "";
    if (indicatorStyle !== "none") {
      statusColorRow = `
        <div class="grid three fixed-three">
          ${this._fieldText("Farve: åben", "status_color_open", 'Default: "#ffb300"', "#ffb300")}
          ${this._fieldText("Farve: hastende", "status_color_urgent", 'Default: "#e53935"', "#e53935")}
          ${this._fieldText("Farve: færdig", "status_color_done", 'Default: "#43a047"', "#43a047")}
        </div>
      `;
    }

    const statusSection = this._section(
      "status",
      "Statusindikator",
      "Udseende og farver for status.",
      `
        ${statusTopRow}
        ${statusColorRow}
      `
    );

    const textsSection = this._section(
      "texts",
      "Tekster",
      "Labels og knaptekster.",
      `
        ${this._subTitle("Status")}
        <div class="grid status-text-row">
          ${this._fieldText("Tekst: åben status", "status_label_open", 'Default: "Mangler"', "Mangler")}
          ${this._fieldText("Tekst: hastende status", "status_label_urgent", 'Default: "Mangler"', "Mangler")}
          ${this._fieldText("Tekst: færdig status", "status_label_done", 'Default: "Færdig"', "Færdig")}
        </div>

        ${this._subTitle("Knapper")}
        <div class="grid two">
          ${this._fieldText("Tekst: færdig-knap", "button_label_done", 'Default: "Færdig"', "Færdig")}
          ${this._fieldText("Tekst: fortryd-knap", "button_label_undo", 'Default: "Fortryd"', "Fortryd")}
        </div>

        ${this._subTitle("Filter")}
        <div class="grid two">
          ${this._fieldText("Tekst: vis færdige", "filter_label_show_completed", 'Default: "Vis færdige"', "Vis færdige")}
          ${this._fieldText("Tekst: skjul færdige", "filter_label_hide_completed", 'Default: "Skjul færdige"', "Skjul færdige")}
        </div>

        ${this._subTitle("Badge")}
        <div class="grid two">
          ${this._fieldText("Tekst: ugeplan-badge", "derived_badge_label", 'Default: "Fra ugeplan"', "Fra ugeplan")}
        </div>
      `
    );

    const typographySection = this._section(
      "typography",
      "Typografi",
      "Tomt felt = standard. Størrelser angives som rene tal, og kortet tilføjer selv rem.",
      `
        <div class="grid two">
          ${this._fieldText("Titel størrelse", "title_font_size", "Tomt felt = HA-standard", "")}
          ${this._fieldText("Fagtitel størrelse", "subject_title_font_size", "Tomt felt = standard", "")}
        </div>

        <div class="grid two">
          ${this._fieldText("Brødtekst størrelse", "text_font_size", "Tomt felt = standard", "")}
          ${this._fieldText("Dato størrelse", "date_font_size", "Tomt felt = standard", "")}
        </div>

        <div class="grid two">
          ${this._fieldText("Barn størrelse", "child_font_size", "Tomt felt = standard", "")}
          ${this._fieldText("Knap størrelse", "button_font_size", "Tomt felt = standard", "")}
        </div>

        <div class="grid two">
          ${this._fieldText("Badge størrelse", "badge_font_size", "Tomt felt = standard", "")}
          <div class="field spacer-field"></div>
        </div>
      `
    );

    const cardLayersSection = this._section(
      "layers",
      "Kortlag",
      "Baggrunde, gennemsigtighed og radius.",
      `
        <div class="grid two">
          ${this._fieldText("Border radius", "card_border_radius", 'Default: "14"', "14")}
          <div class="field spacer-field"></div>
        </div>

        ${this._subTitle("Yderste kort")}
        <div class="grid two">
          ${this._fieldText(
            "Baggrundsfarve",
            "outer_card_background_color",
            "Default: var(--card-background-color)",
            "var(--card-background-color)"
          )}
          ${this._fieldText("Gennemsigtighed", "outer_card_background_opacity", 'Default: "0,35"', "0,35")}
        </div>

        ${this._subTitle("Gruppe-kort")}
        <div class="grid two">
          ${this._fieldText(
            "Baggrundsfarve",
            "group_card_background_color",
            "Default: var(--card-background-color)",
            "var(--card-background-color)"
          )}
          ${this._fieldText("Gennemsigtighed", "group_card_background_opacity", 'Default: "0,55"', "0,55")}
        </div>

        ${this._subTitle("Lektie-kort")}
        <div class="grid two">
          ${this._fieldText(
            "Baggrundsfarve",
            "item_card_background_color",
            "Default: var(--card-background-color)",
            "var(--card-background-color)"
          )}
          ${this._fieldText("Gennemsigtighed", "item_card_background_opacity", 'Default: "0,75"', "0,75")}
        </div>
      `
    );

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          box-sizing: border-box;
          color: var(--primary-text-color);
          font-family: var(--paper-font-body1_-_font-family, inherit);
        }

        * {
          box-sizing: border-box;
        }

        .wrapper {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .section {
          border: 1px solid var(--divider-color);
          border-radius: 14px;
          background: var(--card-background-color);
          overflow: hidden;
        }

        .section summary {
          list-style: none;
          cursor: pointer;
          padding: 14px 16px;
        }

        .section summary::-webkit-details-marker {
          display: none;
        }

        .section-head {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .section-title {
          font-size: 1rem;
          font-weight: 600;
          line-height: 1.3;
        }

        .section-description {
          font-size: 0.85rem;
          color: var(--secondary-text-color);
          line-height: 1.35;
        }

        .section-body {
          border-top: 1px solid var(--divider-color);
          padding: 14px 16px 16px;
          display: flex;
          flex-direction: column;
          gap: 14px;
        }

        .sub-title {
          font-size: 0.85rem;
          font-weight: 700;
          color: var(--secondary-text-color);
          margin-top: 2px;
          margin-bottom: -4px;
        }

        .grid {
          display: grid;
          gap: 12px;
        }

        .grid.one {
          grid-template-columns: 1fr;
        }

        .grid.two {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }

        .grid.three {
          grid-template-columns: repeat(3, minmax(0, 1fr));
        }

        .grid.fixed-three {
          grid-template-columns: repeat(3, minmax(0, 1fr));
        }

        .grid.status-top-row.two {
          grid-template-columns: minmax(0, 1fr) minmax(0, 220px);
        }

        .grid.status-top-row.one {
          grid-template-columns: 1fr;
        }

        .grid.status-text-row {
          grid-template-columns: repeat(3, minmax(0, 1fr));
        }

        .field {
          display: flex;
          flex-direction: column;
          gap: 6px;
          min-width: 0;
        }

        .field-full {
          grid-column: 1 / -1;
        }

        .label {
          font-size: 0.92rem;
          font-weight: 600;
          line-height: 1.3;
        }

        .helper {
          font-size: 0.78rem;
          line-height: 1.35;
          color: var(--secondary-text-color);
        }

        .input {
          width: 100%;
          padding: 10px 12px;
          border-radius: 10px;
          border: 1px solid var(--divider-color);
          background: var(--secondary-background-color);
          color: var(--primary-text-color);
          font: inherit;
          outline: none;
        }

        .input:focus {
          border-color: var(--primary-color);
        }

        .toggles {
          display: grid;
          grid-template-columns: 1fr;
          gap: 0;
        }

        .toggles.two-cols {
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 8px 14px;
        }

        .toggle {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          min-height: 44px;
          padding: 8px 0;
          border-bottom: 1px solid color-mix(in srgb, var(--divider-color) 60%, transparent);
        }

        .toggles.two-cols .toggle {
          border-bottom: none;
        }

        .toggle:last-child {
          border-bottom: none;
        }

        .toggle-left {
          display: flex;
          flex-direction: column;
          gap: 2px;
          min-width: 0;
        }

        input[type="checkbox"] {
          width: 18px;
          height: 18px;
          margin: 0;
          accent-color: var(--primary-color);
          flex: 0 0 auto;
        }

        .spacer-field {
          visibility: hidden;
        }

        @media (max-width: 900px) {
          .grid.two,
          .grid.three,
          .grid.fixed-three,
          .grid.status-top-row.two,
          .grid.status-text-row,
          .toggles.two-cols {
            grid-template-columns: 1fr;
          }
        }
      </style>

      <div class="wrapper">
        ${basicSection}
        ${visibilitySection}
        ${statusSection}
        ${textsSection}
        ${typographySection}
        ${cardLayersSection}
      </div>
    `;

    this.shadowRoot.querySelectorAll("details[data-section]").forEach((el) => {
      el.addEventListener("toggle", () => {
        this._sectionState[el.dataset.section] = el.open;
      });
    });

    this.shadowRoot.querySelectorAll('input[type="text"]').forEach((el) => {
      el.addEventListener("change", (ev) => this._onTextCommit(ev));
      el.addEventListener("blur", (ev) => this._onTextCommit(ev));
    });

    this.shadowRoot.querySelectorAll('input[type="checkbox"]').forEach((el) => {
      el.addEventListener("change", (ev) => this._onCheckboxInput(ev));
    });

    this.shadowRoot.querySelectorAll("select").forEach((el) => {
      el.addEventListener("change", (ev) => this._onSelectInput(ev));
    });
  }
}

customElements.define(
  "foraeldreintra-homework-card-editor",
  ForaeldreintraHomeworkCardEditor
);