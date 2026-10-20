#!/usr/bin/env python3
"""new-theme.py - make a starter theme with placeholder art in one step.

  python3 scripts/new-theme.py <name> [--title T] [--subtitle S] [--agent key:Name:What ...]

Writes themes/<name>/: theme.json, a lettered medallion per agent (icons/*.png), a plain Argus
for the header (the page draws his moving eyes on top), a simple freeze medallion (gods/medusa.svg)
and app icons. Then: bash scripts/build.sh <name>. Swap any PNG or the SVG for your own art later.
Needs Pillow (pip install pillow). Everything it makes is plain shapes and letters, free to use.
"""
import argparse, colorsys, json, os, sys
from PIL import Image, ImageDraw, ImageFont

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BG, RIM, INK = (28, 33, 39), (167, 182, 196), (242, 245, 247)
DEFAULT_AGENTS = ['argus:Argus:Watchman · monitoring', 'backup:Backup:Copies · snapshots',
                  'media:Media:Library · streaming', 'sync:Sync:Files between devices',
                  'mentor:Mentor:Learn · coaching']


def hue(i):
    """A muted colour per agent; the golden-ratio step keeps neighbours far apart on the colour wheel."""
    return tuple(int(c * 255) for c in colorsys.hls_to_rgb((.55 + i * .618) % 1, .62, .45))


def font(px):
    for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 'DejaVuSans-Bold.ttf', 'Arial Bold.ttf', 'arialbd.ttf'):
        try: return ImageFont.truetype(f, px)
        except OSError: pass
    return ImageFont.load_default()


def medallion(size, ring, draw_inside):
    """Draw at 4x and shrink, so edges are smooth."""
    S = size * 4; im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse([S*.04, S*.04, S*.96, S*.96], fill=BG, outline=ring, width=int(S*.045))
    d.ellipse([S*.11, S*.11, S*.89, S*.89], outline=RIM + (90,), width=int(S*.012))
    draw_inside(d, S)
    return im.resize((size, size), Image.LANCZOS)


def letter(i, name, size=256):
    def inside(d, S):
        d.text((S/2, S/2), name[:1].upper(), font=font(int(S*.42)), fill=hue(i), anchor='mm')
    return medallion(size, hue(i), inside)


def argus_head(size=234):
    """Plain figure under the page's drawn eyes (eye positions are fixed in web/index.html)."""
    def inside(d, S):
        k = S / 234
        d.polygon([(116*k, 30*k), (152*k, 100*k), (80*k, 100*k)], fill=INK)        # head behind the eyes
        d.line([(116*k, 100*k), (116*k, 160*k)], fill=INK, width=int(7*k))          # body
        d.line([(116*k, 160*k), (96*k, 200*k)], fill=INK, width=int(7*k))
        d.line([(116*k, 160*k), (136*k, 200*k)], fill=INK, width=int(7*k))
        d.line([(96*k, 125*k), (136*k, 125*k)], fill=INK, width=int(7*k))
    return medallion(size, (63, 111, 103), inside)


def mountain(size=256):
    def inside(d, S):
        d.polygon([(S*.22, S*.70), (S*.50, S*.28), (S*.78, S*.70)], fill=(110, 124, 138))
        d.polygon([(S*.43, S*.39), (S*.50, S*.28), (S*.57, S*.39), (S*.50, S*.36)], fill=INK)
    return medallion(size, (201, 163, 106), inside)


SAMPLE_DECK = {'id': 'argus-basics', 'name': 'Argus basics', 'blurb': 'A sample deck. Add your own JSON decks to this folder.', 'cards': [
    {'id': 'task', 'prompt': 'Which background jobs does Argus show?', 'answer': 'systemd --user services and timers whose names start with an agent key and a dash, such as backup-nightly.',
     'points': [{'idea': 'systemd user services', 'any': ['systemd', 'service', 'timer']}, {'idea': 'named after an agent key', 'any': ['key', 'prefix', 'name', 'starts']}]},
    {'id': 'freeze', 'prompt': 'What does freezing a task do?', 'answer': 'It stops the task and pauses its timer without deleting anything; thawing restores exactly what was on.',
     'points': [{'idea': 'stops it and pauses the timer', 'any': ['stop', 'pause', 'timer']}, {'idea': 'nothing is deleted; thaw restores it', 'any': ['delete', 'restore', 'thaw', 'undo']}]},
    {'id': 'serve', 'prompt': 'How do other devices reach Argus safely?', 'answer': 'Argus listens on 127.0.0.1 only, and tailscale serve publishes it over HTTPS to devices on your tailnet.',
     'points': [{'idea': 'only listens locally', 'any': ['127.0.0.1', 'localhost', 'local']}, {'idea': 'tailscale serve over https', 'any': ['tailscale', 'tailnet', 'https']}]}]}

FREEZE_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 234 234" class="medusa" overflow="visible" style="overflow:visible">
<style>
.medusa{--ring:#7FA7C9;--glow:#B9D6EE}
.medusa.awake{--ring:#A9CBEA}.medusa.freezing{--ring:#D8F0FF;--glow:#FFFFFF}.medusa.thawing{--ring:#9FE3B5;--glow:#C9F5D6}
.medusa .flake{fill:none;stroke:var(--glow);stroke-width:9;stroke-linecap:round}
</style>
<circle cx="117" cy="117" r="108" fill="#1C2127" stroke="var(--ring)" stroke-width="10"/>
<g class="flake" transform="translate(117 117)">
<path d="M0-62V62M-54-31 54 31M-54 31 54-31"/>
<path d="M-14-48 0-34 14-48M-14 48 0 34 14 48M-48-10-30-17-34-36M48 10 30 17 34 36M-48 10-30 17-34 36M48-10 30-17 34-36"/>
</g>
</svg>
'''


def main():
    a = argparse.ArgumentParser(description='Make a starter theme with placeholder art.')
    a.add_argument('name'); a.add_argument('--title', default='Argus'); a.add_argument('--subtitle', default='My server')
    a.add_argument('--agent', action='append', metavar='key:Name:What',
                   help='repeat per agent; tasks named <key>-… show under it. Default: argus, backup, media, sync, mentor')
    o = a.parse_args()
    T = os.path.join(R, 'themes', o.name)
    if os.path.exists(T): sys.exit(f'{T} already exists; pick another name')
    agents = []
    for s in o.agent or DEFAULT_AGENTS:
        key, name, what = (s.split(':', 2) + ['', ''])[:3]
        agents.append({'key': key.strip().lower(), 'name': name or key.title(), 'domain': what or name or key})
    if not any(x['key'] == 'argus' for x in agents): agents.insert(0, {'key': 'argus', 'name': 'Argus', 'domain': 'Watchman · monitoring'})
    for d in ('icons', 'gods', 'decks'): os.makedirs(os.path.join(T, d))
    json.dump({'name': o.name, 'title': o.title, 'subtitle': o.subtitle, 'never_freeze': ['argus-ui'], 'agents': agents},
              open(os.path.join(T, 'theme.json'), 'w'), indent=2, ensure_ascii=False)
    for i, x in enumerate(agents):
        if x['key'] != 'argus': letter(i, x['name']).save(os.path.join(T, 'icons', x['key'] + '.png'))
    if not any(x['key'] == 'mentor' for x in agents): letter(len(agents), 'Mentor').save(os.path.join(T, 'icons', 'mentor.png'))
    argus_head().save(os.path.join(T, 'icons', 'argus.png'))
    mountain().save(os.path.join(T, 'icons', 'olympus.png'))
    for px in (192, 512): argus_head(px).save(os.path.join(T, f'argus-{px}.png'))
    open(os.path.join(T, 'gods', 'medusa.svg'), 'w').write(FREEZE_SVG)
    json.dump(SAMPLE_DECK, open(os.path.join(T, 'decks', 'argus-basics.json'), 'w'), indent=1, ensure_ascii=False)
    open(os.path.join(T, 'ASSETS.md'), 'w').write(f'# {o.name} – assets\nMade by `scripts/new-theme.py`: plain shapes and letters, '
        'free to use under the code\'s MIT license. Replace any file with your own art.\n\nPractice decks go in `decks/` '
        '(see docs/mentor.md); sounds in `~/.config/argus-ui/sfx/` (see docs/sounds.md).\n')
    print(f'made {T}\nnext: bash scripts/build.sh {o.name}')


if __name__ == '__main__':
    main()
