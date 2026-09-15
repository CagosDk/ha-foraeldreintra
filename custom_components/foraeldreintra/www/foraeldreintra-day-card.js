// Dagsvisning af integrationens ugeplanssensor (days-attributten).
const dayModes = { both: "Skema og fokus", schedule: "Kun skema", focus: "Kun fokus" };
const escapeDayText = (value) => String(value ?? "").replace(/[&<>"']/g,
  (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);

function dayDate(day, plan) {
  if (/^\d{4}-\d{2}-\d{2}$/.test(day.date || "")) return day.date;
  const match = String(day.formatted_date || "").match(/^(\d{1,2})\.\s*([a-zæøå]+)\.?(?:\s+(\d{4}))?$/i);
  if (!match) return null;
  const months = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"];
  const month = months.indexOf(match[2].toLowerCase().slice(0, 3)) + 1;
  // The URL retains the ISO week/year even when the sensor's week is abbreviated.
  const week = String(plan.url || "").match(/(?:\/|^)(\d{1,2})-(\d{4})(?:$|\D)/);
  let year = Number(match[3] || week?.[2] || String(plan.week || "").match(/\b(20\d{2})\b/)?.[1]);
  if (!year || !month) return null;
  if (!match[3] && week) {
    if (Number(week[1]) === 1 && month === 12) year -= 1;
    if (Number(week[1]) >= 52 && month === 1) year += 1;
  }
  const date = new Date(Date.UTC(year, month - 1, Number(match[1])));
  if (date.getUTCMonth() !== month - 1 || date.getUTCDate() !== Number(match[1])) return null;
  return date.toISOString().slice(0, 10);
}

class ForaeldreintraDayCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  setConfig(config) {
    if (!config?.entity) throw new Error("Du skal vælge en ugeplanssensor (entity)");
    if (config.mode !== undefined && !Object.hasOwn(dayModes, config.mode)) {
      throw new Error("mode skal være both, schedule eller focus");
    }
    this._config = { title: "I dag", mode: "both", ...config };
    this._render();
  }

  set hass(hass) { this._hass = hass; this._render(); }
  connectedCallback() {
    this._render();
    clearInterval(this._timer);
    this._timer = setInterval(() => this._render(), 30000);
  }
  disconnectedCallback() { clearInterval(this._timer); }
  getCardSize() { return 4; }
  static getConfigElement() { return document.createElement("foraeldreintra-day-card-editor"); }
  static getStubConfig(hass) {
    return { entity: Object.keys(hass?.states || {}).find((id) => Array.isArray(hass.states[id].attributes?.days)) || "", mode: "both" };
  }

  _render() {
    if (!this._config || !this._hass) return;
    const state = this._hass.states[this._config.entity];
    const plan = state?.attributes || {};
    const now = new Date();
    const timeZone = this._hass.config?.time_zone || "Europe/Copenhagen";
    const parts = new Intl.DateTimeFormat("en-GB", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(now);
    const part = (name) => parts.find((p) => p.type === name).value;
    const today = `${part("year")}-${part("month")}-${part("day")}`;
    const days = Array.isArray(plan.days) ? plan.days : [];
    const day = days.find((item) => item && dayDate(item, plan) === today);
    let content;
    if (!state || ["unavailable", "unknown"].includes(state.state)) {
      content = "<p>Ugeplanssensoren er ikke tilgængelig.</p>";
    } else if (!Array.isArray(plan.days)) {
      content = "<p>Vælg en ugeplanssensor med attributten days.</p>";
    } else if (!day) {
      content = "<p>Ingen ugeplan for i dag.</p>";
    } else {
      const schedule = Array.isArray(day.schedule) ? day.schedule.filter(Boolean) : [];
      const focus = Array.isArray(day.lesson_plans) ? day.lesson_plans.filter(Boolean) : [];
      content = this._config.mode !== "focus" ? `<section><h3>Dagens skema</h3>${schedule.length
        ? schedule.map((row) => `<div class="lesson"><span>${escapeDayText(row.time)}</span><div><strong>${escapeDayText(row.subject_full || row.subject_short || row.title)}</strong>${row.title && row.title !== (row.subject_full || row.subject_short) ? `<div class="text">${escapeDayText(row.title)}</div>` : ""}</div></div>`).join("")
        : "<p>Intet skema for i dag.</p>"}</section>` : "";
      if (this._config.mode !== "schedule") content += `<section><h3>Dagens fokus / ugeplan</h3>${focus.length
        ? focus.map((row) => `<article><strong>${escapeDayText(row.subject || "Generelt")}</strong><div class="text">${escapeDayText(row.content_text)}</div></article>`).join("")
        : "<p>Intet fokus for i dag.</p>"}</section>`;
    }
    this.shadowRoot.innerHTML = `<style>
      ha-card { padding: 20px; color: var(--primary-text-color); }
      h2 { font-size: 24px; font-weight: 400; margin: 0 0 8px; }
      h3 { font-size: 16px; margin: 20px 0 12px; }
      .meta, p { color: var(--secondary-text-color); }
      .lesson { display: grid; grid-template-columns: minmax(75px, auto) 1fr; gap: 12px; }
      .lesson, article { padding: 10px 0; border-bottom: 1px solid var(--divider-color); }
      .text { white-space: pre-wrap; overflow-wrap: anywhere; margin-top: 4px; }
    </style><ha-card><h2>${escapeDayText(this._config.title)}</h2><div class="meta">${escapeDayText(plan.barn)} · ${escapeDayText(new Intl.DateTimeFormat("da-DK", { timeZone, dateStyle: "full" }).format(now))}</div>${content}</ha-card>`;
  }
}

class ForaeldreintraDayCardEditor extends HTMLElement {
  constructor() { super(); this.attachShadow({ mode: "open" }); }
  setConfig(config) { this._config = { mode: "both", ...config }; this._render(); }
  set hass(hass) { this._hass = hass; this._render(); }
  _render() {
    if (!this._config) return;
    this.shadowRoot.innerHTML = `<style>label { display: block; margin: 12px 0; } input, select { display: block; width: 100%; box-sizing: border-box; padding: 8px; }</style>
      <label>Ugeplanssensor<input data-key="entity" list="entities" value="${escapeDayText(this._config.entity)}"></label>
      <datalist id="entities">${Object.entries(this._hass?.states || {}).filter(([, state]) => Array.isArray(state.attributes?.days)).map(([id]) => `<option value="${escapeDayText(id)}"></option>`).join("")}</datalist>
      <label>Titel<input data-key="title" value="${escapeDayText(this._config.title ?? "I dag")}"></label>
      <label>Indhold<select data-key="mode">${Object.entries(dayModes).map(([value, label]) => `<option value="${value}" ${this._config.mode === value ? "selected" : ""}>${label}</option>`).join("")}</select></label>`;
    this.shadowRoot.querySelectorAll("[data-key]").forEach((input) => input.addEventListener("change", () => {
      this._config = { ...this._config, [input.dataset.key]: input.value };
      this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config }, bubbles: true, composed: true }));
    }));
  }
}

if (!customElements.get("foraeldreintra-day-card")) customElements.define("foraeldreintra-day-card", ForaeldreintraDayCard);
if (!customElements.get("foraeldreintra-day-card-editor")) customElements.define("foraeldreintra-day-card-editor", ForaeldreintraDayCardEditor);
window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "foraeldreintra-day-card")) window.customCards.push({
  type: "foraeldreintra-day-card", name: "ForældreIntra – I dag", description: "Dagens skema, fokus eller begge fra ugeplanen", preview: true,
});
