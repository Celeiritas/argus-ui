# Changelog

## 4.1.0 – 2026-10-18
UX audit (VectorLab UX skills) and security review.
- **Type:** 16/14/12px scale (no text under 12px), task details at 14px, weights 400/600 only, body line-height 1.5
- **Targets:** every control has a 44px hit area; nav links and the log toggle are 44px tall
- **Keyboard:** Medusa and Zeus's bolt are real buttons. Press one, then Enter on a task (Esc cancels). Tooltips show on hover *and* focus. Argus's eyes follow keyboard focus too.
- **Confirm before interrupting:** freezing or restarting a task that is running right now asks first (named task, Cancel focused, Esc cancels). Freezing anything else offers **Undo**.
- **Copy:** verb-first buttons ("Show log", "Mute sounds"), plain-language results, errors say what happened and what to do next
- **Motion:** UI transitions use 150/200/300ms tokens and only transform/opacity; tools fly with transforms; reduced-motion skips particles and strikes (fade only); Argus stops wandering/blinking under reduced motion
- **Layout:** header is full width (only main content is capped); counts are plain text, not pills; sound toggle moved into the nav
- **Security:** CSRF and DNS-rebinding protection, `ARGUS_BIND`, `ARGUS_ALLOWED_HOSTS`, safe static paths, body size cap, `</script>` escaping, a lock around freeze/thaw, atomic frozen-list writes, and systemctl failures are reported instead of ignored

## 4.0.0 – 2026-10-18
First version in this repository. Same features as the author's "v4" home install, generalized:
- Agent list, titles and registry folder come from the theme (`theme.json`) instead of being hard-coded
- Build script (`scripts/build.sh <theme>`) and generic installer (`scripts/install.sh`, keeps the previous version)
- Large centered Argus with pointer-tracking, blinking, glaring eyes
- Compact task cards, persona pages at `<base>/<agent>`
- Medusa freeze/thaw with green stone effects (sounds optional, bring your own); Zeus's bolt run/restart with lightning effect and sound
- Works directly on a port or behind `tailscale serve --set-path /argus`; installable as a phone app

## Earlier (before this repo)
- v3 – persona groups with medallion icons, moving eyes, Medusa freeze/thaw (frost/fire), Tailscale path
- v2 – first web page (status cards, Run now)
