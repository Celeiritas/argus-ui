"""Sky: the current weather for the page's background scene (Mount Olympus, rain, snow, storms).

Where it comes from: Open-Meteo (https://open-meteo.com), free, no account or API key. Only this server
calls it - at most once every 20 minutes - so the browser never talks to an outside site, and the
only things Open-Meteo learns are this server's IP address and the rounded location in your config.

Location: ~/.config/argus-ui/weather.json  {"lat": 40.39, "lon": -111.85, "units": "f"}
(or ARGUS_WEATHER="lat,lon"). With no location set, the page still shows the season, just no weather.
"""
import json, os, threading, time, urllib.request

CONF = os.path.expanduser(os.environ.get('ARGUS_WEATHER_CONF', '~/.config/argus-ui/weather.json'))
CACHE = os.path.expanduser('~/.cache/argus-ui/sky.json')
TTL = 20 * 60
API = 'https://api.open-meteo.com/v1/forecast'
_lock = threading.Lock()
_mem = {}

# WMO weather codes (what Open-Meteo returns) -> the scene we draw
def scene(code):
    if code in (95, 96, 99): return 'storm', 'Thunderstorm'
    if code in (71, 73, 75, 77, 85, 86): return 'snow', {71: 'Light snow', 73: 'Snow', 75: 'Heavy snow', 77: 'Snow grains', 85: 'Snow showers', 86: 'Heavy snow showers'}[code]
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        heavy = code in (55, 57, 63, 65, 67, 81, 82)
        return 'rain', ('Heavy rain' if code in (65, 67, 82) else 'Rain' if heavy else 'Drizzle' if code < 60 else 'Light rain')
    if code in (45, 48): return 'fog', 'Fog'
    if code in (2, 3): return 'cloudy', 'Partly cloudy' if code == 2 else 'Overcast'
    return 'clear', 'Clear' if code == 0 else 'Mostly clear'

def where():
    env = os.environ.get('ARGUS_WEATHER')
    try:
        if env: lat, lon = (float(x) for x in env.split(',')[:2]); return {'lat': lat, 'lon': lon, 'units': 'f'}
        c = json.load(open(CONF, encoding='utf-8')); return {'lat': float(c['lat']), 'lon': float(c['lon']), 'units': c.get('units', 'f')}
    except Exception: return None

def fetch(loc):
    unit = 'fahrenheit' if loc['units'] == 'f' else 'celsius'
    q = (f"{API}?latitude={loc['lat']:.2f}&longitude={loc['lon']:.2f}&timezone=auto&temperature_unit={unit}"
         "&current=weather_code,is_day,temperature_2m,precipitation,cloud_cover,wind_speed_10m")
    req = urllib.request.Request(q, headers={'User-Agent': 'argus-ui (github.com/Celeiritas/argus-ui)'})
    with urllib.request.urlopen(req, timeout=5) as r: cur = json.load(r)['current']
    sky, desc = scene(int(cur.get('weather_code', 0)))
    return {'sky': sky, 'desc': desc, 'is_day': bool(cur.get('is_day', 1)), 'temp': round(cur.get('temperature_2m', 0)),
            'unit': loc['units'].upper(), 'precip': cur.get('precipitation', 0), 'clouds': cur.get('cloud_cover', 0),
            'wind': cur.get('wind_speed_10m', 0), 'south': loc['lat'] < 0, 'at': int(time.time()), 'source': 'Open-Meteo'}

def current():
    """The weather, from the cache when it is fresh; never raises. {'sky': None} means 'no weather, season only'."""
    loc = where()
    if not loc: return {'sky': None, 'reason': 'no location set'}
    with _lock:
        if _mem.get('at', 0) > time.time() - TTL: return _mem
        if not _mem:
            try: _mem.update(json.load(open(CACHE)))
            except Exception: pass
            if _mem.get('at', 0) > time.time() - TTL: return _mem
        try:
            data = fetch(loc)
            _mem.clear(); _mem.update(data)
            os.makedirs(os.path.dirname(CACHE), exist_ok=True)
            tmp = CACHE + '.tmp'; json.dump(data, open(tmp, 'w')); os.replace(tmp, CACHE)
        except Exception:
            if not _mem: return {'sky': None, 'reason': 'weather unavailable'}
            _mem['stale'] = True; _mem['at'] = time.time() - TTL + 300     # keep the last reading, try again in 5 min
        return _mem
