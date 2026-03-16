class ForaeldreIntraHomeworkCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._hass = null;
  }

  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("Du skal angive entity");
    }

    this._config = {
      title: "Lektier",
      show_completed: true,
      ...config,
    };

    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    const items = this._getItems();
    return Math.max(3, Math.ceil(items.length / 2) + 1);
  }

  _getEntityState() {
    if (!this._hass || !this._config?.entity) {
      return null;
    }
    return this._hass.states[this._config.entity] || null;
  }

  _getItems() {
    const stateObj = this._getEntityState();
    const items = stateObj?.attributes?.items;
    if (!Array.isArray(items)) {
      return [];
    }

    if (this._config?.show_completed === false) {
      return items.filter((item) => !item.completed);
    }

    return items;
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
    if (!dateStr) return "";
    try {
      const date = new Date(dateStr);
      if (Number.isNaN(date.getTime())) return dateStr;

      return new Intl.DateTimeFormat("da-DK", {
        weekday: "short",
        day: "numeric",
        month: "short",
      }).format(date);
    } catch {
      return dateStr;
    }
  }

  async _toggleHomework(item) {
    if (!this._hass || !item?.homework_id) {
      return;
    }

    const service = item.completed
      ? "mark_homework_undone"
      : "mark_homework_done";

    try {
      await this._hass.callService("foraeldreintra", service, {
        homework_id: item.homework_id,
      });
    } catch (err) {
      // Enkel fejlvisning i console i v1
      console.error("Kunne ikke opdatere lektie-status", err);
    }
  }

  _render() {
    if (!this.shadowRoot || !this._config) {
      return;
    }

    const stateObj = this._getEntityState();
    const items = this._getItems();

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

    const rowsHtml =
      items.length === 0
        ? `<div class="empty">Ingen lektier at vise</div>`
        : items
            .map((item) => {
              const dateText = this._formatDate(item.dato);
              const subject = this._escapeHtml(item.fag || "");
              const text = this._escapeHtml(item.tekst || "");
              const source = this._escapeHtml(item.source || "");
              const completed = Boolean(item.completed);
              const title = this._escapeHtml(item.title || item.fag || "Lektie");

              return `
                <div class="item ${completed ? "completed" : ""}" data-homework-id="${this._escapeHtml(item.homework_id || "")}">
                  <div class="item-top">
                    <div class="title-wrap">
                      <div class="title-row">
                        <span class="status-dot ${completed ? "done" : "open"}"></span>
                        <span class="title">${title}</span>
                      </div>
                      <div class="meta">
                        ${dateText ? `<span>${this._escapeHtml(dateText)}</span>` : ""}
                        ${subject ? `<span>${subject}</span>` : ""}
                        ${source ? `<span>Kilde: ${source}</span>` : ""}
                      </div>
                    </div>
                    <button class="toggle-btn" data-homework-id="${this._escapeHtml(item.homework_id || "")}">
                      ${completed ? "Markér som ikke løst" : "Markér som løst"}
                    </button>
                  </div>
                  ${text ? `<div class="text">${text}</div>` : ""}
                </div>
              `;
            })
            .join("");

    this.shadowRoot.innerHTML = `
      <ha-card>
        <div class="card-header">${this._escapeHtml(this._config.title)}</div>
        <div class="card-content">
          ${rowsHtml}
        </div>
      </ha-card>
      ${this._style()}
    `;

    this.shadowRoot.querySelectorAll(".toggle-btn").forEach((button) => {
      button.addEventListener("click", async (ev) => {
        const homeworkId = ev.currentTarget?.dataset?.homeworkId;
        const item = items.find((entry) => entry.homework_id === homeworkId);
        if (item) {
          await this._toggleHomework(item);
        }
      });
    });
  }

  _style() {
    return `
      <style>
        :host {
          display: block;
        }

        ha-card {
          overflow: hidden;
        }

        .card-header {
          font-size: 1.2rem;
          font-weight: 600;
          padding: 16px 16px 0 16px;
        }

        .card-content {
          padding: 16px;
        }

        .item {
          border: 1px solid var(--divider-color);
          border-radius: 12px;
          padding: 12px;
          margin-bottom: 12px;
          background: var(--card-background-color);
        }

        .item.completed {
          opacity: 0.8;
        }

        .item:last-child {
          margin-bottom: 0;
        }

        .item-top {
          display: flex;
          gap: 12px;
          justify-content: space-between;
          align-items: flex-start;
        }

        .title-wrap {
          flex: 1;
          min-width: 0;
        }

        .title-row {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 6px;
        }

        .status-dot {
          width: 10px;
          height: 10px;
          border-radius: 50%;
          display: inline-block;
          flex: 0 0 10px;
        }

        .status-dot.open {
          background: var(--warning-color);
        }

        .status-dot.done {
          background: var(--success-color);
        }

        .title {
          font-weight: 600;
          line-height: 1.3;
        }

        .meta {
          display: flex;
          flex-wrap: wrap;
          gap: 8px 12px;
          color: var(--secondary-text-color);
          font-size: 0.9rem;
        }

        .text {
          margin-top: 10px;
          white-space: pre-wrap;
          line-height: 1.45;
        }

        .toggle-btn {
          border: none;
          border-radius: 10px;
          padding: 10px 12px;
          cursor: pointer;
          background: var(--primary-color);
          color: var(--text-primary-color);
          font: inherit;
          white-space: nowrap;
        }

        .empty {
          color: var(--secondary-text-color);
        }

        .error {
          color: var(--error-color);
        }

        @media (max-width: 640px) {
          .item-top {
            flex-direction: column;
          }

          .toggle-btn {
            width: 100%;
          }
        }
      </style>
    `;
  }

  static getStubConfig() {
    return {
      entity: "sensor.foraeldreintra_lektier_alle",
      title: "Lektier",
    };
  }
}

customElements.define(
  "foraeldreintra-homework-card",
  ForaeldreIntraHomeworkCard
);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "foraeldreintra-homework-card",
  name: "ForældreIntra Homework Card",
  description: "Viser lektier og giver mulighed for at markere dem som løst.",
});
