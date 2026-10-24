# Shared effects and hold to confirm

Every section gives the same kind of feedback for the same kind of event, so the pieces live in two shared files that load right after `core.js`:

- `web/js/fx.js`: the effects (`fx.*`, plus the older `particle`, `ROCK` and `boltFx` that Watch's powers and Olympus use)
- `web/js/hold.js`: `holdConfirm()`

Server plugins get both through their page's `api` (`api.fx`, `api.holdConfirm`; docs/leafy-plugin.md), so a plugin never copies them.

## The rules they keep
- **Motion confirms something real.** An effect marks an event that happened (an idea you got, a parcel that moved, a task that changed), never decoration. The state it confirms is always shown another way too: a word, an icon, a tick.
- **Reduced motion is handled inside.** With `prefers-reduced-motion`, `burst`, `motes`, `pieces` and `bolt` draw nothing and finish at once; `glint` becomes a short fading outline. A plugin can't forget it.
- **They draw in the `#fx` layer** (z 49, above the page, under the toast; docs/scene.md) and clean up after themselves.

## `fx`
A *target* is an element or a point `[x, y]` on the screen. Each call returns a promise that settles when the effect has played.

| Call | What it shows | Use it for |
|---|---|---|
| `fx.burst(target, {colors, n, spread, size, shape, fall, ms})` | pieces fly out from a point and fade. `shape`: `dot`, `leaf`, `rock`, `spark` | a small "yes": a key idea you got (Mentor's olive leaves), a delivery that arrived |
| `fx.motes(from, to, {color, n, ms, lift})` | a ribbon of glowing motes swirls along a lifted curve (after SoulSeed's heal swirl) | something moved from one place to another: a parcel to its shelf, a snapshot into its jar |
| `fx.glint(element, {color})` | one sheen sweeps across the element | "this changed since you last looked" |
| `fx.pieces(element, {colors, cols, rows, ms})` | the element's area breaks into chunks that fall away; the element stays | something was taken down or rolled back |
| `fx.bolt(target)` | Zeus's bolt from the top of the screen, with a flash and sparks | Zeus acting: a deploy approved, a task run |

```js
// in a server plugin's page.js
api.fx.burst(row.querySelector('.tick'), {colors: ['#8EC9E8', '#E6ECF1'], n: 10, spread: 40});
await api.fx.motes(parcel, shelf, {color: '#8EC9E8'});
```

## `holdConfirm(button, onDone, {ms = 3000})`
For anything that changes what runs: approve a deploy, roll back, release a held delivery. It returns `{cancel}`.

- **Press and hold** for 3 seconds: a ring fills and the label counts down ("Hold… 3", "2", "1"). At the end the label says "Working…" while `onDone()` runs, then comes back.
- **Let go early, or slide off the button:** nothing is sent, and a toast says so.
- **Keyboard:** hold Space or Enter. A short press sends nothing.
- **Screen readers and switches** send a single click that can't be held. Such a click (one with no press behind it) arms the button ("Click again to …") and a second click within 5 seconds confirms. That keeps a deliberate second step without shutting anyone out.
- **Reduced motion:** no ring; the countdown words still show.
- **Argus watches** the button while it is held, eyes wide, then nods when `onDone()` finishes, or winces if it returns `false` or throws. Return `false` when the server said no, so the character agrees with the toast.
- The button keeps its label (verb-first, like "Approve argus-ui 4.18.0") and gets an `aria-label` that adds "hold 3 seconds to confirm". Touch can't scroll, select text or open a menu on it.

```js
api.holdConfirm(el.querySelector('#approve'), async () => {
  const r = await api.post('approve', {id});
  api.toast(r.ok ? 'Approved. Zeus deploys it now.' : "Couldn't approve it. Nothing was changed.");
  return r.ok;                       // false: Argus winces instead of nodding
});
```

## Argus reacts: `api.argus.react(kind)`, `api.argus.watch(el)`
The characters answer what you do, using only the art that is already there (they move; nothing is redrawn).
- `react('nod')`: it worked. Argus dips twice; on a side page the section's own medallion (`#hero`) nods with him.
- `react('wince')`: it didn't. A blink and a small shake, Argus and the medallion.
- `react('wide')` / `react('rest')`: eyes wide while something is about to happen, back to normal after.
- `watch(el)` keeps his eyes on `el` ahead of the pointer; `watch(null)` lets go.
- Where they are used: holds (above), Medusa and Zeus on Watch (nod when the task froze, thawed or ran; wince when it failed), Mentor (nods when you got every key idea; nothing for a miss, because a wrong answer is part of learning).
- `react('content')`: a slow, contented blink (400 ms). Home uses it when Needs you empties.
- Reduced motion: the eyes still follow and widen; nothing nods or shakes, and there is no slow blink.
- Use them for results of the user's own actions, not for background events: Argus already glares at failed tasks on his own.

Tested in `tests/fx.test.js`, through `tests/plugin-fixtures/demo-server`.

## At rest
After a minute with no input (pointer, key, wheel, touch or focus) and nothing wrong, Argus dozes: his eyes half-close and drift
slowly, and his blinks slow down. Any input wakes him with a blink. He never dozes while a task has failed or an alert is up (he
glares instead), while a button is held, or while something is being carried on Olympus. Reduced motion: he does not doze.
`look.doze(ms)` sets the wait (tests shorten it).

Mentor keeps a streak of cards answered with every key idea (`localStorage` `mentor-streak`; a miss ends it; cards without a key-idea
list leave it as it is). Every third one sends a ribbon of motes (`fx.motes`) from the result up to Mentor's medallion, and the
result line says how many in a row.
