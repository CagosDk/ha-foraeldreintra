# ForældreIntra for Home Assistant

Custom Home Assistant integration for fetching homework and weekly plans from ForældreIntra / SkoleIntra through the school's mobile site.

> [!WARNING]
> This integration uses an unofficial web-scraping approach against the school's mobile site.
> It is **not** based on a public or supported API.
> If the school changes login flow, page structure, or HTML markup, the integration may stop working until updated.

## Features

- Fetches homework for all available children on the account
- Fetches weekly plans per child
- Creates Home Assistant sensors for homework and weekly plans
- Supports filtering by selected children
- Supports filtering homework by period
- Optional Markdown attributes for easy display in Markdown cards
- Configurable refresh behavior:
  - update by interval
  - or update at fixed times during the day
- UI-based setup through Home Assistant config flow
- No YAML configuration required

## Installation

### Option 1 — HACS (recommended)

1. Open **HACS**
2. Go to **Integrations**
3. Open the menu in the top-right corner and choose **Custom repositories**
4. Add this repository URL:
   `https://github.com/CagosDk/ha-foraeldreintra`
5. Select **Integration** as category
6. Click **Add**
7. Find **ForældreIntra** in HACS and install it
8. Restart Home Assistant

### Option 2 — Manual installation

1. Download the latest release from this repository
2. Copy the folder:

   `custom_components/foraeldreintra`

   into your Home Assistant config directory:

   `config/custom_components/foraeldreintra`

3. Restart Home Assistant

## Configuration

After installation:

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for **ForældreIntra**
4. Enter:
   - **School URL**  
     Example: `https://holbaekrealskolen.m.skoleintra.dk/`
   - **Username**
   - **Password**

The integration will validate your login and discover the available children linked to the account.

## Options

After setup, open the integration options to customize behavior.

Available options include:

- **Selected children**  
  Choose which children should be included

- **Display period for homework**  
  Choose whether to show:
  - all homework
  - today and future
  - future only

- **Markdown attribute**  
  Add formatted Markdown output to sensor attributes for easier dashboard display

- **Show aggregate sensor**  
  Enable or disable the sensor that combines homework across children

- **Auto-remove unselected children**  
  Control behavior when children are deselected


## Entities

The integration creates sensor entities depending on your setup and selected options.

Typical entities include:

### Homework sensors

- **ForældreIntra lektier (alle)**
  - State: number of homework items
  - Attributes may include:
    - `items`
    - `markdown`

- **ForældreIntra lektier (<child name>)**
  - State: number of homework items for that child
  - Attributes may include:
    - `items`
    - `markdown`

### Weekly plan sensors

- **ForældreIntra ugeplan (<child name>)**
  - State: current week identifier or week label
  - Attributes may include:
    - `barn`
    - `title`
    - `week`
    - `url`
    - `class_or_group`
    - `items`
    - `days`
    - `markdown`

## Example usage in Home Assistant

### Show homework in a Markdown card

type: markdown
content: >
  {{ state_attr('sensor.foraeldreintra_lektier_CHILDNAME', 'markdown') }}

### Show weekly plan in a Markdown card
type: markdown
content: >
  {{ state_attr('sensor.foraeldreintra_ugeplan_CHILDNAME', 'markdown') }}

## Notes and limitations

- This integration depends on the school's specific ForældreIntra / SkoleIntra mobile site
- Different schools may render pages slightly differently
- If the school changes HTML structure, parsing may fail
- If login behavior changes, authentication may stop working
- This integration has only been tested against the environments available to the maintainer and contributors

## Troubleshooting

### The integration cannot log in
Check the following:
- The School URL is correct and points to the school's mobile site
- Username and password are correct
- The site still works in a normal browser session
- The school has not changed login or introduced extra verification

### No children are found
Possible causes:
- Login succeeded partially, but the child list could not be parsed
- The page structure changed
- The account has no accessible children in the selected view

### Sensors stop updating
Check:
- Home Assistant logs
- Whether the selected refresh mode is configured correctly
- Whether the school's site is temporarily unavailable

### Weekly plan or homework formatting looks wrong
This usually means the school's HTML layout has changed and parsing rules may need adjustment.

## Logs

To inspect problems, open:

Settings → System → Logs

If needed, enable debug logging for the integration.

Example configuration.yaml:
logger:
  default: warning
  logs:
    custom_components.foraeldreintra: debug

## Reporting issues
If you find a bug or your school uses a slightly different page structure, please open an issue here:
https://github.com/CagosDk/ha-foraeldreintra/issues
