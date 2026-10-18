# UX audit – 4.1.0 (2026-10-18)
Run with the VectorLab UX skills (`ux-audit` + domain skills), catalog defaults (no `.ux-profile.md`), WCAG 2.1 AA. Measured in a browser at 375px and 1280px.

**Page pattern:** 9 Analytics – *Operational* subtype ("watch live counts; act on alerts"), grouped by agent. Deviation: no date range, because the page shows live state only.

| Check | Before (4.0) | After (4.1) |
|---|---|---|
| Text under 12px | 10–11.5px in 8 places | none (SVG illustration text excepted) |
| Primary content size | 12px | 14px |
| Font weights | 400/600/700/800 | 400/600 |
| Body line-height | 1.4 | 1.5 |
| Hit targets | 17–26px tall | 44px hit area everywhere |
| God tools by keyboard | not reachable | buttons; arm then choose a task; Esc |
| Tooltips | `title=` only | real tooltip on hover + focus |
| Interrupting a running task | no warning | named confirm, Cancel focused |
| Reversible destructive action | no undo | Undo in the toast |
| Motion properties | left/top/width/height, clip-path, box-shadow | transform/opacity (power effects documented as exception) |
| Reduced motion | CSS only; JS particles still ran | particles/strikes skipped, fades ≤150ms |
| Horizontal overflow 375/1280 | none | none |

**Documented exceptions:** the powers' effects (petrify, crumble, lightning) run longer than 300ms and animate a crack stroke; they are one-shot feedback tied to the action and are skipped under reduced motion. Argus's idle wander/blink is a character loop, off under reduced motion.
