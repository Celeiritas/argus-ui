# Mealie: tonight's meal on Today (4.53.0)

The **Mealie** section (`<base>/mealie`) shows this week's meal plan from the owner's Mealie, and its tile on Today says
tonight's meal: *Tonight: Lentil soup*. LeafyGrove only reads the plan; meals are planned in Mealie. It is a bundled server
plugin (`plugins/mealie/`, docs/leafy-plugin.md) with no agent's name, so it keeps Mealie's own name (docs/home.md, "Sections
or Open"). Mealie's own site keeps its chip in Today's Open row (`media.json`, docs/home.md); the section is the part
LeafyGrove reads.

## What Today says
One line from `GET api/mealie/status` (status v2, docs/home.md). It never asks for you (`needs` is always `false`): a meal is
news, not a task.

| Mealie's plan for today | Today's line |
|---|---|
| one dinner, or several | *Tonight: Lentil soup* (several joined with " · ") |
| no dinner, one other meal | *No dinner planned · Lunch: Salad* |
| no dinner, several other meals | *No dinner planned · 2 other meals today* |
| nothing | *No meal planned today* |

When the plan can't be read, the line says why, and the section says what to do:

| State | Line |
|---|---|
| no token file | *Not set up yet: make an API token in Mealie* (nothing is asked) |
| the file is empty | *Not set up yet: the token file is empty* |
| its first line is not one word | *The token file does not hold a token* |
| `mealie.json` broken or its address not `http(s)://` | *mealie.json could not be read* |
| Mealie answers 401 or 403 | *Mealie refused the token: make a new one* |
| nothing listens, or the connection fails | *Mealie is not answering* |
| no answer within 3 seconds | *Mealie took too long to answer* |
| not JSON, not the expected shape, over 1 MB, or a redirect | *Mealie answered something unexpected* |

"Today" is the server's own date. LeafyGrove and Mealie run on the same machine, so they agree on it; Mealie's own
`/api/households/mealplans/today` is not used, so a container set to another time zone can't move the day.

## The section
Today first (always, with *No meal planned* when empty), then each of the next six days that has a meal. Each meal is its
kind (*Breakfast*, *Lunch*, *Dinner*, *Side*, *Snack*, *Drink*, *Dessert*, in that order) and its name: the recipe's name,
or the entry's title (a note such as *Leftovers*). When `media.json` has a `mealie` address and Mealie said its group, a
recipe's name links to its page in Mealie (`<address>/g/<group>/r/<recipe>`), and an **Open Mealie** button shows. **Check
again** asks Mealie again (at most once every 5 seconds); the page also re-reads every 15 seconds. Week entries (a meal
planned for a whole week, not a day) are not shown: Mealie leaves them out unless asked.

## Setting it up (on the server)
1. In Mealie, make an API token: open your profile (or go to `<mealie address>/user/profile/api-tokens`), choose **API
   Tokens**, then **Create an API Token**, give it a **Token Name** (for example *LeafyGrove*) and press **Generate**. Copy
   it: Mealie says "This token will not be viewable again." If the **API Tokens** card is missing, turn on **Show advanced
   features** in your user settings first.
2. Save it on the server as `~/.config/argus-ui/mealie-token.txt` (or point `ARGUS_MEALIE_TOKEN` elsewhere): the token alone
   on the first line. Only you should be able to read it: `chmod 600`. Never commit it.
3. Only if Mealie is not at `http://127.0.0.1:9925` (its default port, on the same machine):
   `~/.config/argus-ui/mealie.json` (or `ARGUS_MEALIE`) with `{"url": "http://127.0.0.1:<port>"}`.
4. For recipe links, the `mealie` key in `~/.config/argus-ui/media.json` (docs/home.md), the address your browser uses.

No restart is needed for the token: the file is read on every request, and a new token is used at once. A new LeafyGrove
version (a new `plugin.py`) needs the usual restart. Make a token for LeafyGrove alone: deleting it in Mealie then breaks
nothing else.

## The token stays on the server
- It is read from the file on every request and sent only to Mealie, in the `Authorization: Bearer` header.
- Never into an answer, the page, a log line or an error: the plugin prints nothing, keeps no text from a failed request, and
  answers a bug with *Mealie answered something unexpected* instead of a traceback (the server would log one).
- Redirects are not followed, so the header can't reach another address; the system's proxy settings are not used.
- Only the owner can call `api/mealie/...` (no `roles` in the manifest, docs/people.md).

## Mealie's API (verified at v3.30.0)
The version the owner runs. Checked against the source at the tag, not the demo site (which runs a nightly build):
- `GET /api/households/mealplans?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&perPage=100&page=1`
  ([controller_mealplan.py](https://github.com/mealie-recipes/mealie/blob/v3.30.0/mealie/routes/households/controller_mealplan.py),
  `get_all`): a page `{page, perPage, total, totalPages, items}`; week entries are left out unless `include_week_entries=true`.
- Each item ([new_meal.py](https://github.com/mealie-recipes/mealie/blob/v3.30.0/mealie/schema/meal_plan/new_meal.py),
  `ReadPlanEntry`, camelCase keys): `date`, `entryType` (breakfast, lunch, dinner, side, snack, drink, dessert), `title`,
  `text`, `recipe` (`name`, `slug`, …) or `null`.
- `GET /api/users/self` → `groupSlug`; a recipe's page is `/g/<groupSlug>/r/<slug>` (the frontend's routes,
  [spa/__init__.py](https://github.com/mealie-recipes/mealie/blob/v3.30.0/mealie/routes/spa/__init__.py)).
- Auth: a Bearer token, long-lived API tokens included
  ([dependencies.py](https://github.com/mealie-recipes/mealie/blob/v3.30.0/mealie/core/dependencies/dependencies.py)).
  Tokens are made on `/user/profile/api-tokens` ([Mealie's API docs](https://mealie.io/documentation/getting-started/api-usage/));
  the words in step 1 are from the v3.30.0 English text.

Not verified against a running Mealie with a token (none existed when this was written): the answer's exact shape on the
owner's Mealie, and the click path in Mealie's menus to the profile page (the address in step 1 works either way).

## Tests
- `python3 tests/mealie_test.py -v` (no browser, any OS; `tests/run.sh mealie` runs it as "mealie model") against
  `tests/fixtures/fake_mealie.py`, a stand-in Mealie: where the files are, every line above, the week and its links, each
  failure (a closed port for *not answering*, a 0.4 s limit for *too long*), a redirect not followed, the cache (one ask a
  minute, failures 30 s, a new token at once, Check again), the token in no answer and no output, and the bundled plugin on a
  real server (the token not in its log).
- `bash tests/run.sh mealie` (browser): Today's tile without a token and with one, the section's week, Check again by keyboard
  with focus kept, the token on no page, 375 px. `run.sh` starts the fake on `MEALIE_PORT` and points the server at it.
