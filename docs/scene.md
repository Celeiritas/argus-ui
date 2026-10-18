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

## The Olympus playground (`<base>/olympus`)

The twelve Olympians sit on an **Ω**, left foot to right foot: Dionysus, Hermes, Artemis, Apollo, Demeter, Hera, **Zeus at the top**, Poseidon, Hephaestus, Athena, Ares, Aphrodite. Twelve seats can't split evenly around a top seat, so the left side has six and the right five. Gods who aren't Olympians have their own spots below: **Chthonic** (Hades) and **Beyond Olympus** (Medusa). Seats show the god's *item*, not the god; seats without a power yet are dashed initials.

**Using an item:** drag it out of its seat and let go. It keeps the speed you gave it and falls, so a still release drops it straight down and a quick flick throws it. Pausing before you let go counts as a drop. Letting go over the dock puts it back. Without a mouse: click or press Enter on an item, then click the field (Enter again uses it in the middle of the field). Esc cancels.

| Item | Does |
|---|---|
| Zeus's bolt | strikes a tree (it burns and stands charred), burns a skeleton black until it crumbles to ash, scorches the ground |
| Medusa's snake | turns a tree or skeleton to stone, or back; on bare ground it slithers away |
| Poseidon's trident | wherever it lands, an opaque light-blue tsunami sweeps the screen and the playground comes back fresh |
| Hades' bident | raises a skeleton out of the ground (its bones rattle while it waits), or crumbles one it hits |
| Demeter's seeds | scatter and sprout flowers for the season: pastel blue or pink in spring, dandelions in summer, mushrooms in fall, poinsettias in winter |
| Apollo's bow | draws an arrow that flies and sticks where it lands: ground, tree (it sways with it) or skeleton |
| Hephaestus' hammer | digs a hole that deepens with every blow on the same spot, down to bedrock; smashes skeletons |

On the **Watch** page, Zeus's medallion also hands out bolts (drop one on a task to run it; flung bolts only hit trees and the ground, never tasks), and Medusa freezes and thaws tasks. A tree struck there tidies itself up after 30 seconds. With reduced motion turned on, the weather is a still picture, particles are skipped and the tsunami is a fade.

## Layers (back to front)

Keep this order whenever you add art or effects, so nothing is covered by mistake.

1. `html` background (night colour)
2. `#scene` (fixed, `z-index: -1`, no pointer events), in DOM order:
   1. sky gradient (by weather and night), stars
   2. `.skyflash`: the storm flash, a full-sky layer centred on the summit (never clipped to the mountain's box)
   3. Olympus (`.olympus` SVG: ranges that run far past the sides, massif, snow, temple glow, clouds, summit bolt). Script sets `meet` on wide screens and `slice` on narrow ones, so the full height, summit included, is always shown
   4. `.ground` (height `--gh`: turf, topsoil, clay, bedrock), with Hephaestus' `.hole`s inside it
   5. `.debris` (ash, sticks, scorch, rubble, bones), `.trees`, `.flora` (flowers), `.skels` (skeletons), `.stuck` (arrows and spears in the ground). All are anchored to the ground's surface
   6. weather canvas (rain and snow fall in front of everything above), then fog
3. Page content: section bar, header (title, Argus, tools), agent tabs, `main` (cards, Mentor, the Olympus dock). Cards are opaque, so the scene shows around them and at the end of each page
4. Things in hand or in flight: `.floating`, `.shot`, `.thrown`, `.seed` (z 50)
5. `#flash` (48) and `#fx` effects (49): lightning, sparks, flames, smoke, dirt, bone pieces
6. The tsunami (55), then the toast (60), then dialogs (the browser's top layer)

**Inside a medallion:** background → figure → rim → anything that belongs *outside* the rim (Medusa's sleeping Zs, effect particles). Draw those last and outside the rim's radius, with a dark outline so they read on the pale rim, and keep `overflow: visible` on the SVG.

**Hit-testing the scene:** the scene sits behind the page, so items find trees, skeletons and debris by their boxes, and only where nothing else (a card, a panel, the dock, a button) is on top. Thrown items test at their tip every frame and land when the tip reaches the ground's surface.

**Class names:** scene states are `.struck` and `.statue` (trees), `.up`, `.burning`, `.charred`, `.statue`, `.dying` (skeletons). Don't reuse `.stone`, which is the overlay on frozen task cards and is positioned absolutely.
