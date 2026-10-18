#!/usr/bin/env python3
"""Draft medallions for new gods, matched to leafy_realm_service_figures_v2.png:
Powder Snow rim, thin ring in the god's hue, hue->Night radial background, white stick figure (stroke 7), simple face."""
import sys, os
OUT = sys.argv[1] if len(sys.argv) > 1 else '.'
W = '#F4F6F8'; S = f'stroke="{W}" stroke-width="7" stroke-linecap="round" stroke-linejoin="round" fill="none"'

def medal(name, hue, glow, body):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 234 234">
<defs><radialGradient id="bg-{name}" cx="50%" cy="45%" r="60%"><stop offset="0" stop-color="{glow}"/><stop offset="1" stop-color="#1C2127"/></radialGradient>
<clipPath id="c-{name}"><circle cx="117" cy="117" r="104"/></clipPath></defs>
<circle cx="117" cy="117" r="113" fill="#1C2127" stroke="#A7B6C4" stroke-width="7"/>
<circle cx="117" cy="117" r="105" fill="url(#bg-{name})"/>
<circle cx="117" cy="117" r="105" fill="none" stroke="{hue}" stroke-width="2.5"/>
<g clip-path="url(#c-{name})">{body}</g></svg>'''

ZEUS = medal('zeus', '#F2D14B', '#3b3a5c', f'''
 <!-- storm cloud with code brackets -->
 <g fill="#C9CED6" opacity=".9"><circle cx="58" cy="68" r="16"/><circle cx="78" cy="58" r="20"/><circle cx="100" cy="68" r="15"/><rect x="44" y="66" width="70" height="17" rx="8"/></g>
 <text x="78" y="81" text-anchor="middle" font-family="ui-monospace,Menlo,monospace" font-size="17" font-weight="700" fill="#3b3a5c">&lt;/&gt;</text>
 <!-- body -->
 <line x1="122" y1="108" x2="120" y2="150" {S}/>
 <path d="M120 150 L106 188 M120 150 L136 188" {S}/>
 <path d="M121 120 L100 136" {S}/>
 <path d="M122 118 L146 100 L156 78" {S}/>
 <!-- robe sash -->
 <path d="M109 106 Q122 102 134 108 L130 152 L112 152 Z" fill="{W}"/>
 <path d="M112 108 L132 150" stroke="#F2D14B" stroke-width="3"/>
 <!-- head: crown of points, big beard -->
 <circle cx="122" cy="84" r="14" fill="{W}"/>
 <path d="M108 104 Q122 126 136 104 Q136 92 122 94 Q108 92 108 104 Z" fill="#E6E9EE"/>
 <path d="M110 74 L113 64 L117 72 L122 61 L127 72 L131 64 L134 74 Z" fill="#F2D14B"/>
 <path d="M115 82 l4 1 M129 82 l-4 1" stroke="#333" stroke-width="2" stroke-linecap="round"/>
 <!-- lightning bolt raised -->
 <path d="M164 40 L146 74 L158 74 L148 104 L174 64 L161 64 L172 40 Z" fill="#F2D14B" stroke="#FFF6C2" stroke-width="2" stroke-linejoin="round"/>
 <path d="M150 30 l-6 -8 M178 34 l6 -6 M182 54 l8 0" stroke="#F2D14B" stroke-width="3" stroke-linecap="round"/>''')

POSEIDON = medal('poseidon', '#2E86AB', '#123f52', f'''
 <!-- waves -->
 <path d="M10 190 Q30 178 50 190 T90 190 T130 190 T170 190 T210 190 T250 190 V240 H10 Z" fill="#2E86AB" opacity=".55"/>
 <path d="M10 202 Q30 192 50 202 T90 202 T130 202 T170 202 T210 202 T250 202 V240 H10 Z" fill="#1f6a8a" opacity=".8"/>
 <!-- soap bubbles -->
 <g fill="#BFE6F5" fill-opacity=".15" stroke="#BFE6F5" stroke-width="2"><circle cx="58" cy="122" r="6"/><circle cx="44" cy="104" r="3.5"/><circle cx="66" cy="96" r="2.8"/><circle cx="50" cy="140" r="2.2"/></g>
 <path d="M55 119 a3 3 0 0 1 4 -2" stroke="#fff" stroke-width="1.5" fill="none"/>
 <!-- body -->
 <line x1="110" y1="104" x2="110" y2="150" {S}/>
 <path d="M110 150 L96 188 M110 150 L124 188" {S}/>
 <path d="M110 118 L88 132" {S}/>
 <path d="M110 116 L136 108" {S}/>
 <!-- head: wild hair, sea-foam beard -->
 <circle cx="110" cy="82" r="14" fill="{W}"/>
 <path d="M96 80 Q92 66 102 64 Q106 56 116 60 Q126 58 126 68 Q132 74 124 80" fill="none" stroke="#9FD3E6" stroke-width="5" stroke-linecap="round"/>
 <path d="M97 92 Q110 120 123 92 Q120 86 110 88 Q100 86 97 92 Z" fill="#CFE9F2"/>
 <path d="M104 80 l4 1 M117 80 l-4 1" stroke="#333" stroke-width="2" stroke-linecap="round"/>
 <!-- trident: shaft + three tines, each ending in a flared broom head (bristles up) -->
 <g transform="translate(0 20)">
 <line x1="140" y1="64" x2="140" y2="196" stroke="#C9CED6" stroke-width="5" stroke-linecap="round"/>
 <path d="M120 66 Q140 82 160 66" stroke="#C9CED6" stroke-width="4.5" fill="none" stroke-linecap="round"/>
 <path d="M120 66 V56 M140 74 V52 M160 66 V56" stroke="#C9CED6" stroke-width="4.5" stroke-linecap="round"/>
 <g transform="translate(120 50)">
  <rect x="-3" y="0" width="6" height="7" rx="1.5" fill="#8a5a3a"/>
  <path d="M-4 -1 L4 -1 L13 -30 Q0 -35 -13 -30 Z" fill="#D9B26A" stroke="#A8823F" stroke-width="1.2" stroke-linejoin="round"/>
  <path d="M-2 -2 L-9 -30 M0 -2 L-3 -32 M2 -2 L3 -32 M3 -2 L9 -30 M-1 -2 L-6 -31 M1 -2 L6 -31" stroke="#A8823F" stroke-width="1"/>
  <path d="M-6 -12 L6 -12" stroke="#8a5a3a" stroke-width="2.4" stroke-linecap="round"/></g><g transform="translate(140 46)">
  <rect x="-3" y="0" width="6" height="7" rx="1.5" fill="#8a5a3a"/>
  <path d="M-4 -1 L4 -1 L13 -30 Q0 -35 -13 -30 Z" fill="#D9B26A" stroke="#A8823F" stroke-width="1.2" stroke-linejoin="round"/>
  <path d="M-2 -2 L-9 -30 M0 -2 L-3 -32 M2 -2 L3 -32 M3 -2 L9 -30 M-1 -2 L-6 -31 M1 -2 L6 -31" stroke="#A8823F" stroke-width="1"/>
  <path d="M-6 -12 L6 -12" stroke="#8a5a3a" stroke-width="2.4" stroke-linecap="round"/></g><g transform="translate(160 50)">
  <rect x="-3" y="0" width="6" height="7" rx="1.5" fill="#8a5a3a"/>
  <path d="M-4 -1 L4 -1 L13 -30 Q0 -35 -13 -30 Z" fill="#D9B26A" stroke="#A8823F" stroke-width="1.2" stroke-linejoin="round"/>
  <path d="M-2 -2 L-9 -30 M0 -2 L-3 -32 M2 -2 L3 -32 M3 -2 L9 -30 M-1 -2 L-6 -31 M1 -2 L6 -31" stroke="#A8823F" stroke-width="1"/>
  <path d="M-6 -12 L6 -12" stroke="#8a5a3a" stroke-width="2.4" stroke-linecap="round"/></g>
 </g>
''')

for n, s in [('zeus', ZEUS), ('poseidon', POSEIDON)]:
    open(os.path.join(OUT, f'{n}-draft.svg'), 'w').write(s)
print('ok')
