const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function setup(mode = 'both', date = '2026-09-15T10:00:00Z') {
  const registry = new Map();
  let tick;
  let cleared = false;
  class Clock extends Date { constructor(...args) { super(...(args.length ? args : [date])); } }
  const context = vm.createContext({
    Date: Clock, Intl, window: {},
    HTMLElement: class {
      attachShadow() { this.shadowRoot = { innerHTML: '', querySelectorAll: () => [] }; }
      dispatchEvent(event) { this.event = event; }
    },
    CustomEvent: class { constructor(type, options) { this.type = type; Object.assign(this, options); } },
    customElements: { get: (key) => registry.get(key), define: (key, value) => registry.set(key, value) },
    setInterval: (callback) => { tick = callback; return 1; },
    clearInterval: () => { cleared = true; },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../custom_components/foraeldreintra/www/foraeldreintra-day-card.js'), 'utf8'), context);
  const card = new (registry.get('foraeldreintra-day-card'))();
  const plan = {
    barn: 'Anna', url: '/weeklyplans/38-2026',
    days: [{ formatted_date: '15. sep.', schedule: [{ time: '08:00–08:45', subject_full: 'Dansk' }],
      lesson_plans: [{ subject: 'Læsning', content_text: 'Læs side 7\nHusk bog' }] },
      { formatted_date: '16. sep.', schedule: [{ subject_full: 'I morgen' }] }],
  };
  const hass = { config: { time_zone: 'Europe/Copenhagen' }, states: { 'sensor.plan': { state: '38', attributes: plan } } };
  card.setConfig({ entity: 'sensor.plan', mode });
  card.hass = hass;
  return { card, plan, hass, context, registry, setDate: (value) => { date = value; }, tick: () => tick(), cleared: () => cleared };
}

for (const mode of ['both', 'schedule', 'focus']) test(`renders today's selected content: ${mode}`, () => {
  const { card } = setup(mode);
  assert.equal(card.shadowRoot.innerHTML.includes('08:00–08:45'), mode !== 'focus');
  assert.equal(card.shadowRoot.innerHTML.includes('Læs side 7\nHusk bog'), mode !== 'schedule');
  assert.ok(!card.shadowRoot.innerHTML.includes('I morgen'));
});

test('matches dates in the Home Assistant timezone and updates after midnight', () => {
  const env = setup('both', '2026-09-14T22:05:00Z');
  assert.match(env.card.shadowRoot.innerHTML, /Læs side 7/);
  env.card.connectedCallback();
  env.setDate('2026-09-15T22:05:00Z');
  env.tick();
  assert.match(env.card.shadowRoot.innerHTML, /I morgen/);
  assert.doesNotMatch(env.card.shadowRoot.innerHTML, /Læs side 7/);
  env.card.disconnectedCallback();
  assert.ok(env.cleared());
});

test('stale plans and dates without a known year do not become today', () => {
  const { card, plan, hass } = setup();
  for (const url of ['/weeklyplans/38-2025', '']) {
    plan.url = url;
    card.hass = hass;
    assert.match(card.shadowRoot.innerHTML, /Ingen ugeplan for i dag/);
  }
});

test('handles ISO week year boundaries and invalid dates', () => {
  const { context } = setup();
  for (const [formatted, url, expected] of [
    ['30. dec.', '/1-2026', '2025-12-30'],
    ['1. jan.', '/53-2026', '2027-01-01'],
    ['31. feb.', '/9-2026', null],
    ['15. september 2026', '', '2026-09-15'],
  ]) {
    context.input = { formatted_date: formatted };
    context.plan = { url };
    assert.equal(vm.runInContext('dayDate(input, plan)', context), expected);
  }
});

test('shows unavailable, incorrect sensor, empty day and empty sections', () => {
  const { card, hass, plan } = setup();
  plan.days[0].schedule = [];
  plan.days[0].lesson_plans = [];
  card.hass = hass;
  assert.match(card.shadowRoot.innerHTML, /Intet skema for i dag/);
  assert.match(card.shadowRoot.innerHTML, /Intet fokus for i dag/);
  plan.days = [];
  card.hass = hass;
  assert.match(card.shadowRoot.innerHTML, /Ingen ugeplan for i dag/);
  delete plan.days;
  card.hass = hass;
  assert.match(card.shadowRoot.innerHTML, /Vælg en ugeplanssensor/);
  hass.states['sensor.plan'].state = 'unavailable';
  card.hass = hass;
  assert.match(card.shadowRoot.innerHTML, /ikke tilgængelig/);
  delete hass.states['sensor.plan'];
  card.hass = hass;
  assert.match(card.shadowRoot.innerHTML, /ikke tilgængelig/);
});

test('escapes school content and validates mode', () => {
  const { card, plan, hass } = setup();
  plan.days[0].lesson_plans[0].content_text = '<img src=x onerror="alert(1)">';
  card.hass = hass;
  assert.doesNotMatch(card.shadowRoot.innerHTML, /<img/);
  assert.match(card.shadowRoot.innerHTML, /&lt;img/);
  assert.throws(() => card.setConfig({ entity: 'sensor.plan', mode: 'invalid' }), /mode skal/);
  assert.throws(() => card.setConfig({}), /ugeplanssensor/);
});

test('editor emits selected mode while preserving other settings', () => {
  const { registry } = setup();
  const editor = new (registry.get('foraeldreintra-day-card-editor'))();
  editor.setConfig({ type: 'custom:foraeldreintra-day-card', entity: 'sensor.plan', title: 'Anna' });
  let change;
  const input = { dataset: { key: 'mode' }, value: 'focus', addEventListener: (_, callback) => { change = callback; } };
  editor.shadowRoot.querySelectorAll = () => [input];
  editor._render();
  change();
  assert.equal(editor.event.type, 'config-changed');
  assert.equal(editor.event.detail.config.mode, 'focus');
  assert.equal(editor.event.detail.config.title, 'Anna');
  assert.equal(editor.event.detail.config.entity, 'sensor.plan');
});
