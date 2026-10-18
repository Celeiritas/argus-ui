# The scene: Olympus, weather, seasons and powers

Every page sits on a background scene: a sky, Mount Olympus, grass and a row of trees. The scene follows the real weather and season. The **Olympus** section (`<base>/olympus`) is a playground where nothing covers the scene and every power can be tried on it.

## Where the weather and date come from

| What | Source | Who calls it |
|---|---|---|
| Season | The date on the viewer's device: Dec–Feb winter, Mar–May spring, Jun–Aug summer, Sep–Nov fall (flipped for the southern hemisphere) | Nobody: it's worked out in the page |
| Day / night | Open-Meteo's `is_day` when weather is set up, otherwise the viewer's clock (night is 8 pm to 6 am) | — |
| Weather | [Open-Meteo](https://open-meteo.com) `current` forecast: free, no account or API key | **The Argus server only**, at most once every 20 minutes, cached in `~/.cache/argus-ui/sky.json` |

The browser never talks to an outside site for the scene. Open-Meteo only sees the server's IP address and the location rounded to two decimals. If the service is down, the page keeps the last reading (and says so in the tooltip). If there has never been a reading, the page shows the season with no weather.

Why Open-Meteo:

| Service | Key or account | Coverage | Notes |
|---|---|---|---|
| **Open-Meteo** (chosen) | None | Worldwide | WMO weather codes, `is_day`, °F or °C; free for non-commercial use |
| api.weather.gov (NWS) | None, but a User-Agent is required | US only | Two calls (point → forecast); no simple current-conditions code |
| OpenWeatherMap | API key | Worldwide | Free tier needs an account and a key to keep secret |

**Set the location:** `WEATHER=<lat>,<lon> ./install.sh`, which writes `~/.config/argus-ui/weather.json` as `{"lat": .., "lon": .., "units": "f"}` (`UNITS=c` for Celsius). The location is kept on your machine and never committed. The server's `ARGUS_WEATHER="lat,lon"` setting overrides the file.

**Weather codes → scene:** 0–1 clear · 2–3 cloudy · 45/48 fog · 51–67 and 80–82 rain (heavier codes make more rain) · 71–77 and 85–86 snow · 95–99 storm (lightning flashes over the summit). Rain streaks slant with the wind.

**Preview any look:** use the Olympus controls, or add URL options to any page, e.g. `?sky=storm&season=winter&night=1`.

## Powers in the scene

- **Zeus's bolt.** The medallion stays home and hands you a bolt.
  - Drop it on a task to run it, or on a tree to strike it.
  - Fling it, by letting go while moving fast, and it flies on with a little gravity until it hits a tree or the ground, leaving a scorch mark and rubble.
  - Flung bolts never touch task cards; only a deliberate drop runs a task.
- **Medusa** turns a tree to stone; drag her onto it again to bring it back.
- **Poseidon** (Olympus only for now) washes away debris (ash, charred sticks, scorch marks, rubble) with a wave. Charred trees in its path grow back.
- On pages other than Olympus, a struck tree cleans itself up after 30 seconds.
- With reduced motion turned on, the weather is a still picture and the powers skip their particles.

## Layers (back to front)

Keep this order whenever you add art or effects, so nothing is covered by mistake.

1. `html` background (night colour)
2. `#scene` (fixed, `z-index: -1`, no pointer events):
   1. sky gradient (by weather and night)
   2. stars
   3. Olympus: far range, massif, snow, temple glow, clouds, summit bolt
   4. grass
   5. trees
   6. debris
   7. weather canvas (rain and snow fall in front of the trees)
   8. fog
3. Page content: section bar, header (title, Argus, tools), agent tabs, `main`. Cards are opaque, so the scene shows only around them and at the end of each page (which has 220px of open space).
4. A tool being dragged, and the bolt in hand: `.floating` / `.shot` (z 50)
5. `#flash` (48) and `#fx` effects (49): lightning, sparks, flames, smoke, water
6. Toast (60)
7. Dialogs (the browser's top layer)

**Inside a medallion:** background → figure → rim → anything that belongs *outside* the rim (Medusa's sleeping Zs, effect particles). Draw those last and outside the rim's radius, with a dark outline so they read on the pale rim, and keep `overflow: visible` on the SVG.

**Hit-testing the scene:** the scene sits behind the page, so tools find trees and debris by their boxes, and only where nothing else (a card, a panel, a button) is on top.

**Class names:** scene states are `.struck` and `.statue` on `.tree`. Don't reuse `.stone`, which is the overlay on frozen task cards and is positioned absolutely.
