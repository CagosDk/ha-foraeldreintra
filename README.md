# ForældreIntra — Home Assistant integration + Lovelace-kort 📚🏫

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)

En dansk Home Assistant-løsning til at hente og vise data fra **ForældreIntra / SkoleIntra** direkte i Home Assistant.

Projektet består af to dele:

- **Integrationen** henter og eksponerer data som Home Assistant-entiteter
- **Lovelace-kortene** viser lektier eller dagens skema og fokus med visuelle editorer

Løsningen er lavet til danske brugere og danske skoledata.

---

## Hvad projektet indeholder

### Integration
Integrationen opretter sensorer i Home Assistant med data fra ForældreIntra, så du kan bruge dem i dashboards, templates, automations og egne kort.

### Lovelace-kort
Det medfølgende custom card gør det nemt at vise lektier direkte i dit dashboard med fokus på læsbarhed og fleksibilitet.

---

## Funktioner ✨

- Viser lektier fra en ForældreIntra-sensor i Home Assistant
- Gruppering efter barn
- Dato-overskrifter
- Mulighed for at skjule/vises færdige lektier
- Markér lektier som færdige / fortryd direkte fra kortet
- Understøttelse af afledte lektier fra ugeplan
- Statusvisning som prik, venstre farvebar eller ingen indikator
- Statusbadge med tekster som fx **Mangler** / **Færdig**
- Mulighed for at vise/skjule:
  - statusbadge
  - filterknap
  - toggle-knap
  - badge for ugeplan
  - børneoverskrift
  - barn i meta
  - dato-overskrifter
- Compact-visning
- Tilpasning af:
  - titel
  - fontstørrelser
  - border radius
  - baggrundslag og gennemsigtighed
  - statusfarver
- Custom editor i Lovelace UI
- Separat dagskort med dagens skema, dagens fokus fra ugeplanen eller begge

---

## Hurtigt overblik

### Det du får i praksis
- Sensorer fra integrationen
- Et custom Lovelace-kort til visning af lektier
- En visuel editor til kortet
- Mulighed for at tilpasse kortets udseende uden at skrive alt i YAML

---

## Installation

### HACS (anbefalet)

1. Åbn **HACS**
2. Gå til **Integrations**
3. Tryk på **⋯ → Custom repositories**
4. Tilføj dette repository som **Integration**
5. Installer integrationen
6. Genstart Home Assistant
7. Gå til **Indstillinger → Enheder og tjenester**
8. Tilføj integrationen **ForældreIntra**

> Bemærk: Selve integrationen installeres via HACS som integration.

---

## Lovelace resource (kortets JavaScript)

Afhængigt af dit HACS-setup bliver resource-filerne måske tilføjet automatisk.

Hvis kortet ikke dukker op i Lovelace-editoren:

1. Gå til **Indstillinger → Betjeningspaneler → Ressourcer**
2. Tilføj JavaScript-filerne
```text
/foraeldreintra-static/foraeldreintra-homework-card.js?v=1
/foraeldreintra-static/foraeldreintra-homework-card-editor.js?v=1
```
4. Vælg typen **JavaScript Module**
5. Genindlæs dashboardet

Typisk vil stien være noget i stil med:


> Tip: Hvis du oplever cache-problemer efter opdateringer, kan du tilføje versionsparameter til resource-URL'en, fx `?v=1.0.0`.

---

## Hurtig start

### Simpel opsætning

```yaml
type: custom:foraeldreintra-homework-card
entity: sensor.foraeldreintra_lektier_alle
title: Lektier
```

### Eksempel med flere indstillinger

```yaml
type: custom:foraeldreintra-homework-card
entity: sensor.foraeldreintra_lektier_alle
title: Lektier
display_period: current_and_future
group_by_child: true
compact: false
show_status_badge: true
show_filter_button: true
show_toggle_button: true
show_derived_badge: true
show_date_headers: true
show_child_header: true
show_child_in_meta: true
status_indicator_style: dot
status_bar_width: 15
status_color_open: "#ffb300"
status_color_urgent: "#e53935"
status_color_done: "#43a047"
status_label_open: Mangler
status_label_urgent: Mangler
status_label_done: Færdig
button_label_done: Færdig
button_label_undo: Fortryd
filter_label_show_completed: Vis færdige
filter_label_hide_completed: Skjul færdige
derived_badge_label: Fra ugeplan
subject_title_font_size: "1,0"
text_font_size: "1,0"
date_font_size: "0,95"
child_font_size: "0,95"
button_font_size: "0,9"
badge_font_size: "0,75"
card_border_radius: 14
outer_card_background_color: var(--card-background-color)
outer_card_background_opacity: "0,35"
group_card_background_color: var(--card-background-color)
group_card_background_opacity: "0,55"
item_card_background_color: var(--card-background-color)
item_card_background_opacity: "0,75"
hide_completed: false
child_filter: []
subject_filter: []
child_aliases: {}
subject_aliases: {}
show_derived_items: true
```

---

## Dagsvisning: skema og fokus

Kortet **ForældreIntra – I dag** viser ét barns data for dagens dato fra ugeplanssensorens `days`-attribut. Du kan vælge **kun skema**, **kun fokus** eller **begge** i den visuelle editor eller i YAML.

### Installation af dagskortet

Tilføj denne ekstra resource som **JavaScript Module** under **Indstillinger → Betjeningspaneler → Ressourcer**, og genindlæs dashboardet:

```text
/foraeldreintra-static/foraeldreintra-day-card.js?v=1
```

Editoren er inkluderet i samme fil. Lektiekortets eksisterende resources bruges fortsat til lektiekortet.

### Skema og fokus sammen

```yaml
type: custom:foraeldreintra-day-card
entity: sensor.foraeldreintra_ugeplan_anna
title: Annas dag
mode: both
```

### Kun dagens skema

```yaml
type: custom:foraeldreintra-day-card
entity: sensor.foraeldreintra_ugeplan_anna
title: Dagens skema
mode: schedule
```

### Kun dagens fokus / ugeplan

```yaml
type: custom:foraeldreintra-day-card
entity: sensor.foraeldreintra_ugeplan_anna
title: Dagens fokus
mode: focus
```

Erstat eksempel-entiteten med dit barns faktiske ugeplanssensor fra **Udviklerværktøjer → Tilstande**. Opret et kort pr. barn. Den samlede ugeplanssensor skal have både skema og fokus inkluderet i integrationens indstillinger for at vise begge dele. Du kan også bruge en særskilt skemasensor med `mode: schedule` eller en særskilt fokussensor med `mode: focus`.

| Indstilling | Standard | Betydning |
| --- | --- | --- |
| `entity` | Påkrævet | Ugeplanssensor med `days` |
| `title` | `I dag` | Kortets overskrift |
| `mode` | `both` | `schedule`, `focus` eller `both` |

Skemaet viser tid, fag og eventuel titel i kildens rækkefølge. Fokus viser dagens `lesson_plans` med fag og tekst; ugeplanens generelle tekster gældende for hele ugen vises ikke som dagens fokus. Linjeskift bevares, og indhold vises som tekst.

**Dato og tomme data:** Dagens dato følger Home Assistants indstillede tidszone (ellers Europe/Copenhagen). Kortet opdateres ved nye sensordata og kontrollerer datoen hvert 30. sekund, mens det er åbent. Det viser kun en matchende dato, også ved årsskifte. En gammel ugeplan, en weekend uden indhold eller en dag uden match giver beskeden *Ingen ugeplan for i dag*. Mangler kun skema eller fokus, får den pågældende sektion sin egen tomme besked. Kortet henter ikke en anden ugeplan; det viser de data, integrationen allerede har hentet.

Datoen læses fra `days[].date` i ISO-format, hvis den findes, ellers fra `formatted_date` (fx `15. sep.`) og uge/år i sensorens `url` (fx en sti med `38-2026`). En dato med et eksplicit år understøttes også. Uden et kendt år vises datoen ikke, så gamle data ikke bliver forvekslet med dagens.

### Test

Kør frontend-testene uden ekstra pakker med Node.js 22 eller nyere:

```sh
node --test tests/test_day_card.cjs
```

Testene dækker indholdsvalg, dato/tidszone, midnat, årsskifte, tomme data, tekst-escaping og editorens konfigurationsændringer. De køres også i GitHub Actions.

---

## Sådan virker det

Integrationen opretter sensorer i Home Assistant med en liste af lektier i attributter.  
Kortet læser disse data fra `hass.states` og viser dem i dashboardet.

Kortet kan blandt andet bruge disse oplysninger fra sensoren:

- barn
- fag
- tekst
- dato
- status for færdig / ikke færdig
- markering af afledte lektier fra ugeplan

---

## Kortets vigtigste muligheder

### Visning
- `group_by_child` — gruppér efter barn
- `compact` — kompakt visning
- `display_period` — styr hvilke datoer der vises
- `show_date_headers` — vis dato-overskrifter
- `show_child_header` — vis overskrift for barn
- `show_child_in_meta` — vis barn i meta-linjen

### Elementer
- `show_status_badge` — vis statusbadge
- `show_filter_button` — vis knap til vis/skjul færdige
- `show_toggle_button` — vis knap til færdig/fortryd
- `show_derived_badge` — vis badge for ugeplan
- `show_derived_items` — vis eller skjul afledte lektier

### Status
- `status_indicator_style: dot`
- `status_indicator_style: bar`
- `status_indicator_style: none`

### Filtrering
- `child_filter`
- `subject_filter`

### Alias
- `child_aliases`
- `subject_aliases`

Det gør det muligt at omdøbe børn eller fag i visningen uden at ændre de rå data.

---

## Custom editor

Kortet har en visuel editor i Lovelace, hvor du kan ændre de vigtigste indstillinger uden at redigere YAML manuelt.

Editoren gør det muligt at justere blandt andet:

- entity
- titel
- periode
- compact
- gruppering
- statusvisning
- tekster
- typografi
- baggrundslag
- gennemsigtighed
- border radius

---

## Vis/skjul færdige

Kortet kan huske dit valg for **vis/skjul færdige** pr. entity i browseren, så præferencen ikke nulstilles hele tiden ved almindelig brug.

---

## Fejlsøgning

### Kortet viser ingen data
- Kontrollér at integrationen er installeret korrekt
- Kontrollér at sensoren findes
- Kontrollér at sensoren faktisk har data i attributten `items`
- Genstart Home Assistant efter installation eller opdatering

### Kortet dukker ikke op i editoren
- Kontrollér at resource-filerne er tilføjet under **Dashboards → Ressourcer**
- Kontrollér at typen er **JavaScript Module**
- Genindlæs dashboardet
- Prøv hård refresh i browseren

### Ændringer i JavaScript slår ikke igennem
Det skyldes ofte cache.

Prøv:
- hård refresh
- opdater resource-URL med fx `?v=1.0.0`
- kontrollér at Home Assistant loader de rigtige filer

### Entity selector eller editor opfører sig mærkeligt
- Kontrollér at editor-filen er den nyeste version
- Kontrollér at resource-stien peger på den rigtige fil
- Tjek at der ikke findes gamle dubletter af samme resource

---

## Status lige nu

Denne release fokuserer på lektiekortet og stabilitet omkring:

- custom editor
- vis/skjul færdige
- compact visning
- HA-lignende titel
- statusindikatorer
- styling og læsbarhed

Dagsvisningen findes som et separat kort: `custom:foraeldreintra-day-card`. Det viser dagens skema og fokus fra ugeplanen; en samlet visning af hele ugen er endnu ikke implementeret.

---

## Målgruppe

Denne integration er lavet til danske brugere med adgang til ForældreIntra / SkoleIntra og er derfor primært dokumenteret på dansk.

---

## Bidrag og feedback

Issues, forslag og forbedringer er meget velkomne.

Hvis du finder fejl eller har idéer til nye funktioner, så opret gerne en issue i repository'et.

---

## Licens

Tilføj den licens, du ønsker at bruge for projektet, fx MIT, hvis det er det du vælger.
