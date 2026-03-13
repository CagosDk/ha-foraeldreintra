# ForældreIntra til Home Assistant

En dansk **custom integration** til Home Assistant, der henter **lektier** og **ugeplaner** fra skolens mobile ForældreIntra / SkoleIntra-side og gør dem tilgængelige som sensorer i Home Assistant.

Integrationens fokus er at gøre det nemt at vise skoledata på dashboards, i Markdown-kort og i automatiseringer.

> [!WARNING]
> Denne integration bruger **web scraping** mod skolens mobile ForældreIntra / SkoleIntra-side.
> Den er **ikke** baseret på et officielt eller understøttet API.
> Hvis skolen ændrer login, HTML-struktur eller sideopbygning, kan integrationen holde op med at virke, indtil den bliver opdateret. Den nuværende integration er sat op som `config_flow`-integration og er version `1.0.1` i `manifest.json`. citeturn430094view3turn430094view0

## Funktioner

- Henter **lektier** for de valgte børn
- Henter **ugeplaner** for de valgte børn
- Opretter sensorer til både lektier og ugeplaner
- Understøtter **samlede sensorer** og **separate sensorer pr. barn**
- Understøtter **Markdown-attributter** til nem visning i Home Assistant-kort
- Kan filtrere lektier efter visningsperiode
- Kan udlede ekstra lektier fra ugeplanen, fx **diktatord**
- Kan tilpasse fagforkortelser via egne oversættelser
- Sættes op direkte i Home Assistant via UI
- Kræver ingen YAML-konfiguration til selve integrationen

## Installation

### Installation via HACS

1. Åbn **HACS**
2. Gå til **Integrations**
3. Vælg menuen øverst til højre og klik **Custom repositories**
4. Tilføj repoet:
   `https://github.com/CagosDk/ha-foraeldreintra`
5. Vælg kategorien **Integration**
6. Installer **ForældreIntra**
7. Genstart Home Assistant

### Manuel installation

1. Download seneste release fra repoet
2. Kopiér mappen `custom_components/foraeldreintra` til:
   `config/custom_components/foraeldreintra`
3. Genstart Home Assistant

## Første opsætning

Når integrationen er installeret:

1. Gå til **Indstillinger** → **Enheder og tjenester**
2. Klik **Tilføj integration**
3. Søg efter **ForældreIntra**
4. Udfyld:
   - **Skolens URL**
   - **Brugernavn**
   - **Adgangskode**

I den danske oversættelse beskrives opsætningen som: *"Indtast dine oplysninger for at hente ugeplan og lektier"*, og felterne er `school_url`, `username` og `password`. citeturn430094view1

### Eksempel på skole-URL

```text
https://holbaekrealskolen.m.skoleintra.dk/
```

Det er vigtigt, at du bruger skolens **mobile** SkoleIntra / ForældreIntra-adresse.

## Konfiguration og valgmuligheder

Efter opsætning kan integrationen tilpasses under **Indstillinger** for integrationen.

Nedenfor er alle de muligheder, integrationen tilbyder i den nuværende løsning.

### Børn

Vælg hvilke børn der skal medtages i integrationen.

- Kun valgte børn opretter data i sensorerne
- Hvis ingen vælges manuelt, bruges som udgangspunkt alle fundne børn

### Visningsperiode

Styrer hvilke lektier der skal vises.

Mulige værdier:

- **Historik + i dag + frem**
  Viser alle lektier, også tidligere
- **Kun i dag + frem**
  Viser lektier fra i dag og fremad
- **Kun frem (fra i morgen)**
  Viser kun fremtidige lektier

Integrationens standardværdi for visningsperioden er `today_and_future`. citeturn430094view2

> [!TIP]
> Afledte lektier fra ugeplan følger også denne filtrering.
> Hvis en ugeplan-afledt lektie ligger på en dato i fortiden, vises den ikke ved **Kun frem (fra i morgen)**.

### Vis lektie-sensorer

Slår lektie-sensorerne til eller fra.

Når den er slået til, oprettes sensorer for:

- samlede lektier
- lektier pr. barn

Standard er slået til. `show_homework_sensors = True`. citeturn430094view2

### Tilføj markdown til lektier

Tilføjer en formatteret `markdown`-attribut på lektie-sensorerne.

Det gør det nemt at vise lektier direkte i et Markdown-kort i Home Assistant uden selv at bygge teksten.

Standard er slået fra. `add_homework_markdown = False`. citeturn430094view2

### Tilføj afledte lektier fra ugeplan

Når denne er slået til, forsøger integrationen at udlede ekstra lektier ud fra ugeplanen.

Det er især nyttigt i situationer hvor læreren ikke har lagt noget ind under de normale lektier, men i stedet har skrevet det i ugeplanen.

Eksempel:

- Ugeplanen indeholder teksten: `Diktatord i den uge: ...`
- En dag i ugeplanen indeholder fx: `Diktat`
- Integration kan så oprette et ekstra lektiepunkt ud fra ugeplanen

Afledte lektier markeres med kilde fra ugeplan.

### Nøgleord til afledte lektier fra ugeplan

Her angiver du hvilke ord eller formuleringer integrationen skal kigge efter i ugeplanen.

Eksempler:

```text
diktatord, øveord, ord til diktat
```

Brug komma-separerede værdier.

Denne mulighed er tænkt som en fleksibel måde at tilpasse integrationen til forskelle mellem lærere, skoler og formuleringer.

### Medtag Generelt i samlet ugeplan

Styrer om den generelle del af ugeplanen skal med i den samlede ugeplanssensor.

Typisk bruges dette til fælles beskeder som:

- information til forældre
- påmindelser
- generelle ugekommentarer

### Medtag Fokus i samlet ugeplan

Styrer om fokus-/fagområder skal med i den samlede ugeplanssensor.

Det er nyttigt, hvis lærerne bruger ugeplanen til at beskrive mål, fokusområder eller faglige emner for ugen.

### Medtag Skema i samlet ugeplan

Styrer om skemadelen skal med i den samlede ugeplanssensor.

Det er især relevant, hvis du vil kunne se dagens eller ugens fag, tider og eventuelle ekstra oplysninger direkte i ugeplanssensoren.

### Vis samlet ugeplan-sensor

Slår den samlede ugeplan-sensor til eller fra.

Når den er aktiv, får du en samlet ugeplanssensor pr. barn med de valgte indholdstyper, fx:

- generelt
- fokus
- skema

Standard er slået til. `show_weekplan_sensors = True`. citeturn430094view2

### Vis separat sensor for ugeplan generelt

Opretter en separat sensor kun til den generelle del af ugeplanen.

God hvis du vil vise fælles beskeder i ét kort og resten af ugeplanen et andet sted.

Standard er slået fra. `show_weekplan_general_sensors = False`. citeturn430094view2

### Vis separat sensor for ugeplan fokus

Opretter en separat sensor kun til fokus-/fagområder.

Standard er slået fra. `show_weekplan_focus_sensors = False`. citeturn430094view2

### Vis separat sensor for ugeplan skema

Opretter en separat sensor kun til skemadelen.

Standard er slået fra. `show_weekplan_schedule_sensors = False`. citeturn430094view2

### Tilføj markdown til ugeplan

Tilføjer en formatteret `markdown`-attribut til ugeplan-sensorerne.

Standard er slået til. `add_weekplan_markdown = True`. citeturn430094view2

### Fag-oversættelser

Giver mulighed for at oversætte eller omdøbe fagforkortelser og interne fagkoder.

Det er nyttigt når skolens data indeholder forkortelser, som du gerne vil have vist mere læsbart i Home Assistant.

Eksempel:

```text
Pæd=, MAS=, BOOS=Booster, SVØM=Svømning
```

Eksempler på brug:

- `BOOS=Booster` ændrer BOOS til Booster
- `SVØM=Svømning` ændrer SVØM til Svømning
- `Pæd=` skjuler eller tømmer værdien

> [!TIP]
> Denne funktion er især nyttig hvis skemaet indeholder interne forkortelser eller støtte-/pædagoglinjer, som du ikke ønsker vist på samme måde som almindelige fag.

## Hvilke sensorer oprettes?

Det afhænger af dine valgte indstillinger.

Typiske sensorer er:

### Lektier

- `sensor.foraeldreintra_lektier_alle`
- `sensor.foraeldreintra_lektier_<barn>`

Eksempel:

- `sensor.foraeldreintra_lektier_frederik`
- `sensor.foraeldreintra_lektier_olivia`

Typiske attributter:

- `items`
- `markdown`

### Ugeplan

- `sensor.foraeldreintra_ugeplan_<barn>`
- `sensor.foraeldreintra_ugeplan_generelt_<barn>`
- `sensor.foraeldreintra_ugeplan_fokus_<barn>`
- `sensor.foraeldreintra_ugeplan_skema_<barn>`

Typiske attributter:

- `barn`
- `title`
- `week`
- `url`
- `class_or_group`
- `items`
- `days`
- `markdown`

## Eksempler på brug i dashboards

### Vis lektier i et Markdown-kort

```yaml
type: markdown
content: >
  {{ state_attr('sensor.foraeldreintra_lektier_olivia', 'markdown') }}
```

### Vis ugeplan i et Markdown-kort

```yaml
type: markdown
content: >
  {{ state_attr('sensor.foraeldreintra_ugeplan_olivia', 'markdown') }}
```

### Vis kun hvis der er indhold

```yaml
type: conditional
conditions:
  - entity: sensor.foraeldreintra_lektier_olivia
    state_not: "0"
card:
  type: markdown
  content: >
    {{ state_attr('sensor.foraeldreintra_lektier_olivia', 'markdown') }}
```

## Eksempel på data

En ugeplanssensor kan fx indeholde:

- barnets navn
- uge-nummer
- generelle beskeder
- fagpunkter for ugen
- dagsopdelt skema
- dagsopdelt undervisningsplan

En lektiesensor kan fx indeholde:

- dato
- fag
- tekst
- links
- barn
- eventuel kilde fra ugeplan

## Begrænsninger

- Integrationens datakilde er skolens mobile webside, ikke et officielt API
- HTML-strukturen kan variere fra skole til skole
- Små ændringer på siden kan påvirke parsing af både lektier og ugeplaner
- Login-flow kan ændre sig uden varsel
- Ikke alle skoler viser nødvendigvis data helt ens
- Afledte lektier fra ugeplan afhænger af lærerens formuleringer og de nøgleord, du selv angiver

## Fejlsøgning

### Kan ikke logge ind

Kontrollér:

- at skolens URL er korrekt
- at du bruger den mobile SkoleIntra-adresse
- at brugernavn og adgangskode er korrekte
- at login stadig virker i en normal browser

### Ingen børn fundet

Mulige årsager:

- login lykkedes ikke helt
- siden med børn kunne ikke parses
- skolens side har ændret struktur
- kontoen har ikke adgang til børn i den aktuelle visning

### Lektier eller ugeplan opdateres ikke

Kontrollér:

- Home Assistant-loggen
- om skolens side er tilgængelig
- om integrationen kan genindlæses uden fejl

### Afledte lektier fra ugeplan vises ikke

Kontrollér:

- at funktionen er slået til
- at nøgleordene matcher teksten i ugeplanen
- at visningsperioden ikke filtrerer lektien væk
- at ugeplanen faktisk indeholder både relevant tekst og den dag/fag-kobling, du forventer

### Skema eller fag ser mærkelige ud

Prøv at bruge **Fag-oversættelser** til at rydde op i forkortelser eller skjule irrelevante fagkoder.

## Debug logging

Hvis du vil fejlfinde mere detaljeret, kan du aktivere debug-logning i Home Assistant:

```yaml
logger:
  default: warning
  logs:
    custom_components.foraeldreintra: debug
```

## Privatliv og sikkerhed

Integrationens login-oplysninger bruges til at logge ind på skolens side og hente data til Home Assistant.

Vær opmærksom på:

- data hentes fra en tredjepartsside
- integrationen er community-drevet
- layoutændringer på siden kan påvirke funktionaliteten
- visning i dashboards kan gøre skoledata synlige for andre i husstanden afhængigt af dit setup

## Kendte tekniske detaljer

Integrationen bruger Home Assistants `config_flow`, har domænet `foraeldreintra`, platformen `sensor` og afhænger af `beautifulsoup4==4.12.3`. I `const.py` er standards for blandt andet lektie-sensorer, ugeplan-sensorer og visningsperiode defineret centralt. citeturn430094view3turn430094view2

## Rapportering af fejl

Finder du en fejl, eller bruger din skole en lidt anden sideopbygning, så opret gerne en issue i repoet:

`https://github.com/CagosDk/ha-foraeldreintra/issues`

Det hjælper meget hvis du beskriver:

- hvilken skole du bruger
- hvad der ikke virker
- hvilke sensorer det drejer sig om
- om problemet gælder lektier, ugeplan eller begge dele
- gerne anonymiserede eksempler på data eller screenshots
