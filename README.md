# ForældreIntra (Home Assistant)

En Home Assistant custom integration der henter ugeplan/lekti(er) fra ForældreIntra/SkoleIntra-løsningen via skolens mobilsite.

> Bemærk: Dette er ikke en officiel API. Skolen kan ændre login/HTML, hvilket kan gøre integrationen ustabil.

## Installation (HACS)

1. HACS → **Integrations**
2. Menu (⋮) → **Custom repositories**
3. Tilføj repo: `CagosDk/ha-foraeldreintra`
4. Category: **Integration**
5. Installer
6. Genstart Home Assistant

## Opsætning

1. Home Assistant → **Indstillinger** → **Enheder & tjenester**
2. **Tilføj integration**
3. Søg efter **ForældreIntra**
4. Udfyld:
   - School URL (fx `https://holbaekrealskolen.m.skoleintra.dk/`)
   - Brugernavn
   - Adgangskode

## Sensorer

- `sensor.foraeldreintra_lektier_alle`  
  - state: antal lektier
  - attributes: `items` (liste med alle lektier)

- `sensor.foraeldreintra_lektier_pr_barn`
  - state: samlet antal
  - attributes: `børn` (dict med barn -> liste)

## Fejlfinding

- Tjek **Indstillinger → System → Logfiler**
- Hvis login fejler: bekræft URL og at skolens mobilsite virker i browseren.
