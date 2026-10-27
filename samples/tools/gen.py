"""PS AI MUSIC sample pack generator. All sounds are synthesized here; no third-party audio."""
import numpy as np, json, os, wave, sys
from scipy import signal

SR = 44100
OUT = sys.argv[1] if len(sys.argv) > 1 else 'out'
rng = np.random.default_rng(2026)
MANIFEST = []

# ---------------- helpers ----------------
def T(sec): return np.arange(int(SR * sec)) / SR
def mtof(m): return 440.0 * 2 ** ((m - 69) / 12)
def noise(sec): return rng.uniform(-1, 1, int(SR * sec))
def sos(kind, f, order=2, q=None):
    nyq = SR / 2
    if kind == 'bp':
        lo, hi = f
        return signal.butter(order, [max(20, lo) / nyq, min(hi, nyq * .98) / nyq], 'bandpass', output='sos')
    return signal.butter(order, min(f, nyq * .98) / nyq, {'lp': 'lowpass', 'hp': 'highpass'}[kind], output='sos')
def filt(x, kind, f, order=2): return signal.sosfilt(sos(kind, f, order), x)
def bp(x, fc, q=2.0):
    bw = fc / q
    return filt(x, 'bp', (fc - bw / 2, fc + bw / 2))
def sweep_sin(freq, phase0=0.0):
    ph = 2 * np.pi * np.cumsum(freq) / SR + phase0
    return np.sin(ph)
def osc(kind, freq):
    ph = np.cumsum(freq) / SR % 1.0
    if kind == 'sin': return np.sin(2 * np.pi * ph)
    if kind == 'saw': return 2 * ph - 1
    if kind == 'sqr': return np.where(ph < .5, 1.0, -1.0)
    if kind == 'tri': return 2 * np.abs(2 * ph - 1) - 1
    if kind == 'pulse25': return np.where(ph < .25, 1.0, -1.0)
def blsaw(f, sec, harmonics=None):
    """band-limited saw by additive synthesis (clean for melodic use)"""
    t = T(sec); x = np.zeros_like(t); nmax = harmonics or int((SR / 2 * .9) // max(f, 1))
    for k in range(1, max(2, nmax) + 1): x += ((-1) ** (k + 1)) * np.sin(2 * np.pi * k * f * t) / k
    return x * (2 / np.pi)
def blsqr(f, sec):
    t = T(sec); x = np.zeros_like(t); nmax = int((SR / 2 * .9) // max(f, 1))
    for k in range(1, nmax + 1, 2): x += np.sin(2 * np.pi * k * f * t) / k
    return x * (4 / np.pi)
def expenv(sec, dec): return np.exp(-T(sec) / max(dec, 1e-4))
def adsr(sec, a, d, s, r, hold=None):
    n = int(SR * sec); e = np.zeros(n); A = int(SR * a); D = int(SR * d); R = int(SR * r)
    H = int(SR * hold) if hold is not None else n - R
    H = max(min(H, n - R), A + 1)
    e[:A] = np.linspace(0, 1, A, endpoint=False) if A else 0
    seg = np.arange(H - A)
    e[A:H] = s + (1 - s) * np.exp(-seg / max(D, 1) * 3)
    lvl = e[H - 1] if H > 0 else s
    e[H:H + R] = lvl * np.linspace(1, 0, len(e[H:H + R])) ** 2
    return e
def sat(x, drive):
    if drive <= 0: return x
    return np.tanh(x * (1 + drive)) / np.tanh(1 + drive)
def pad_to(x, n): return np.pad(x, (0, max(0, n - len(x))))[:n]
def mix(*xs):
    n = max(len(x) for x in xs); return sum(pad_to(x, n) for x in xs)
def reverb(x, size=.5, wet=.3, sec_tail=1.2):
    """small Schroeder reverb"""
    x = np.concatenate([x, np.zeros(int(SR * sec_tail))]); out = np.zeros_like(x)
    for d, g in [(1557, .84), (1617, .83), (1491, .82), (1422, .81)]:
        d = int(d * (.6 + size)); y = np.zeros_like(x)
        for i in range(0, len(x), d):
            seg = x[i:i + d]; prev = y[i - d:i - d + len(seg)] if i >= d else 0
            y[i:i + len(seg)] = seg + g * prev
        out += y
    out /= 4
    for d, g in [(225, .5), (556, .5)]:
        y = np.zeros_like(out); buf = np.zeros(d)
        b = np.zeros(len(out) + d)
        for i in range(len(out)):
            v = b[i] if i < len(b) else 0
            y[i] = -g * out[i] + v
            b[i + d] = out[i] + g * y[i]
        out = y
    out = filt(out, 'lp', 7000)
    return x * (1 - wet) + out * wet
def lofi(x, bits=10, sr_div=2, noise_amt=.004):
    y = np.round(x * 2 ** (bits - 1)) / 2 ** (bits - 1)
    if sr_div > 1: y = np.repeat(y[::sr_div], sr_div)[:len(x)]
    return y + rng.normal(0, noise_amt, len(y)) * (np.abs(x) > 1e-4)
def stereo(l, r): n = max(len(l), len(r)); return np.stack([pad_to(l, n), pad_to(r, n)], 1)

def finish(x, peak_db=-1.0, fade_in=.0008, fade_out=.012, trim=True):
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 1: x = x - np.mean(x[: min(len(x), SR)]) * 0  # keep transients; DC handled by HP below
    x = signal.sosfilt(sos('hp', 18, 2), x, axis=0)
    a = np.abs(x) if x.ndim == 1 else np.abs(x).max(1)
    if trim:
        thr = a.max() * 10 ** (-62 / 20); idx = np.where(a > thr)[0]
        end = min(len(a), (idx[-1] + int(SR * .02)) if len(idx) else len(a))
        x = x[:end]
    n = len(x); fi = max(1, int(SR * fade_in)); fo = max(1, min(int(SR * fade_out), n // 3))
    ramp_i = np.linspace(0, 1, fi); ramp_o = np.linspace(1, 0, fo) ** 1.5
    if x.ndim == 1: x[:fi] *= ramp_i; x[-fo:] *= ramp_o
    else: x[:fi] *= ramp_i[:, None]; x[-fo:] *= ramp_o[:, None]
    pk = np.abs(x).max()
    if pk > 0: x = x / pk * 10 ** (peak_db / 20)
    return x

def write(path, x):
    full = os.path.join(OUT, path); os.makedirs(os.path.dirname(full), exist_ok=True)
    x = np.clip(x, -1, 1); ch = 1 if x.ndim == 1 else 2
    data = (x * 32767).astype('<i2')
    with wave.open(full, 'wb') as w:
        w.setnchannels(ch); w.setsampwidth(2); w.setframerate(SR); w.writeframes(data.tobytes())
    return len(x) / SR, ch

COUNTERS = {}
def add(cat, sub, name, x, kind='oneshot', tracks=None, root=None, bpm=None, bars=None, tags=None, peak=-1.0, trim=True, fade_out=.012):
    x = finish(x, peak, trim=trim, fade_out=fade_out)
    key = (cat, sub); COUNTERS[key] = COUNTERS.get(key, 0) + 1; i = COUNTERS[key]
    slug = name.lower().replace(' ', '-').replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue').replace('ß', 'ss').replace('/', '-')
    slug = ''.join(c for c in slug if c.isalnum() or c in '-#')
    slug = slug.replace('#', 's')
    fn = f"{cat}/{sub}/ps-{sub}-{i:02d}-{slug}.wav"
    dur, ch = write(fn, x)
    MANIFEST.append({'id': f"{sub}-{i:02d}", 'name': name, 'category': cat, 'group': sub, 'file': fn, 'type': kind,
                     'tracks': tracks or [], 'root': root, 'rootNote': (None if root is None else note_name(root)),
                     'bpm': bpm, 'bars': bars, 'duration': round(dur, 3), 'channels': ch, 'tags': tags or []})
    return x
NN = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
def note_name(m): return f"{NN[m % 12]}{m // 12 - 1}"

# ---------------- DRUMS ----------------
def kick(f0=150, f1=45, pdec=.035, adec=.28, click=.3, drive=.6, lp=None, sub=0, dur=None, crush=False, tone2=0):
    sec = dur or min(2.2, adec * 5 + .08); t = T(sec)
    fr = f1 + (f0 - f1) * np.exp(-t / pdec)
    body = sweep_sin(fr, np.pi / 2 * .0) * np.exp(-t / adec)
    if sub: body += .4 * np.sin(2 * np.pi * f1 * t) * np.exp(-t / (adec * 1.8)) * sub
    if tone2: body += tone2 * sweep_sin(fr * 1.5) * np.exp(-t / (adec * .3))
    cl = filt(noise(sec), 'hp', 2500) * np.exp(-t / .0035) * click
    cl += click * .6 * np.sin(2 * np.pi * 1800 * t) * np.exp(-t / .002)
    x = sat(body + cl, drive)
    if lp: x = filt(x, 'lp', lp, 4)
    if crush: x = lofi(x, 9, 3, .003)
    return x
KICKS = [
 ('Boom Bap', dict(f0=160, f1=47, pdec=.03, adec=.32, click=.25, drive=.8)),
 ('Punch', dict(f0=200, f1=55, pdec=.022, adec=.2, click=.55, drive=1.2)),
 ('Deep', dict(f0=120, f1=40, pdec=.05, adec=.5, click=.1, drive=.4)),
 ('Tight', dict(f0=220, f1=60, pdec=.015, adec=.12, click=.6, drive=.9)),
 ('House', dict(f0=150, f1=50, pdec=.03, adec=.3, click=.35, drive=1.0)),
 ('Techno', dict(f0=170, f1=48, pdec=.028, adec=.38, click=.45, drive=2.2)),
 ('Lo-Fi', dict(f0=140, f1=46, pdec=.035, adec=.3, click=.2, drive=.5, lp=900, crush=True)),
 ('Akustik', dict(f0=110, f1=58, pdec=.04, adec=.22, click=.9, drive=.3, tone2=.25)),
 ('Sub', dict(f0=80, f1=38, pdec=.06, adec=.6, click=0, drive=.3, sub=1)),
 ('808 kurz', dict(f0=130, f1=42, pdec=.03, adec=.45, click=.08, drive=.7, sub=.6)),
 ('808 lang', dict(f0=125, f1=40, pdec=.035, adec=1.0, click=.06, drive=.8, sub=.8, dur=2.2)),
 ('Trap', dict(f0=180, f1=45, pdec=.02, adec=.55, click=.4, drive=1.6, sub=.5)),
 ('Verzerrt', dict(f0=170, f1=50, pdec=.03, adec=.35, click=.4, drive=4.5)),
 ('Weich', dict(f0=110, f1=50, pdec=.045, adec=.25, click=.05, drive=.1, lp=1500)),
 ('Thump', dict(f0=140, f1=62, pdec=.02, adec=.16, click=.3, drive=.6)),
 ('Club', dict(f0=190, f1=52, pdec=.025, adec=.42, click=.5, drive=1.8, sub=.3)),
 ('Hart', dict(f0=260, f1=55, pdec=.018, adec=.3, click=.8, drive=3.0)),
 ('Rund', dict(f0=130, f1=52, pdec=.04, adec=.35, click=.15, drive=.4, sub=.4)),
 ('Staubig', dict(f0=150, f1=48, pdec=.03, adec=.28, click=.3, drive=.9, lp=2200, crush=True)),
 ('Knock', dict(f0=240, f1=70, pdec=.012, adec=.1, click=.7, drive=1.4, tone2=.3)),
 ('Boomy', dict(f0=115, f1=42, pdec=.06, adec=.7, click=.12, drive=.6, sub=.7)),
 ('Kurz', dict(f0=200, f1=65, pdec=.012, adec=.07, click=.5, drive=.8)),
 ('Hip-Hop', dict(f0=155, f1=50, pdec=.028, adec=.36, click=.35, drive=1.1, lp=5000)),
 ('Garage', dict(f0=175, f1=56, pdec=.02, adec=.24, click=.45, drive=1.3, tone2=.15)),
]
for name, p in KICKS: add('drums', 'kick', f"Kick {name}", kick(**p), tracks=['kick'])

def snare(tone=200, tdec=.1, hp=1200, lp=9000, ndec=.18, nmix=.75, drive=.5, ring=0, crush=False, rev=0, body2=0):
    sec = max(tdec, ndec) * 5 + .05; t = T(sec)
    fr = tone * (1 + .35 * np.exp(-t / .01))
    tn = np.sin(2 * np.pi * np.cumsum(fr) / SR) * np.exp(-t / tdec)
    if body2: tn += body2 * np.sin(2 * np.pi * np.cumsum(fr * 1.47) / SR) * np.exp(-t / (tdec * .6))
    nz = filt(filt(noise(sec), 'hp', hp), 'lp', lp) * np.exp(-t / ndec)
    x = tn * (1 - nmix) * 1.6 + nz * nmix
    if ring: x += ring * np.sin(2 * np.pi * tone * 3.1 * t) * np.exp(-t / (ndec * 1.5)) * .3
    x = sat(x, drive)
    if crush: x = lofi(x, 10, 2, .004)
    if rev: x = reverb(x, .4, rev, .8)
    return x
SNARES = [
 ('Klassik', {}), ('Trap', dict(tone=260, tdec=.06, hp=2200, ndec=.13, nmix=.85, drive=.9)),
 ('Fett', dict(tone=180, tdec=.15, hp=800, ndec=.3, nmix=.7, drive=1.2, body2=.4)),
 ('Lo-Fi', dict(tone=190, tdec=.1, hp=900, lp=4000, ndec=.2, crush=True)),
 ('Tight', dict(tone=240, tdec=.05, hp=2500, ndec=.08, nmix=.8, drive=.8)),
 ('Rock', dict(tone=200, tdec=.14, hp=700, ndec=.28, nmix=.65, drive=1.6, ring=.6)),
 ('Hall', dict(tone=210, tdec=.1, hp=1100, ndec=.2, rev=.45)),
 ('Piccolo', dict(tone=360, tdec=.07, hp=3000, ndec=.12, nmix=.7, ring=.5)),
 ('Tief', dict(tone=150, tdec=.16, hp=600, ndec=.25, nmix=.6, drive=.8, body2=.3)),
 ('House', dict(tone=230, tdec=.08, hp=1500, ndec=.16, nmix=.78, drive=.7)),
 ('Breakbeat', dict(tone=210, tdec=.1, hp=1000, lp=6000, ndec=.17, drive=2.0, crush=True)),
 ('Dubstep', dict(tone=190, tdec=.18, hp=900, ndec=.35, nmix=.72, drive=2.4, rev=.3)),
 ('Weich', dict(tone=200, tdec=.09, hp=1600, lp=5000, ndec=.15, nmix=.8, drive=0)),
 ('Crack', dict(tone=300, tdec=.04, hp=3500, ndec=.09, nmix=.9, drive=1.8)),
 ('Snappy', dict(tone=250, tdec=.06, hp=2800, ndec=.22, nmix=.88, drive=.6)),
 ('Boom Bap', dict(tone=195, tdec=.12, hp=1000, lp=7000, ndec=.21, nmix=.72, drive=1.4, crush=True)),
]
for name, p in SNARES: add('drums', 'snare', f"Snare {name}", snare(**p), tracks=['snare'])

def brush(sec=.5, dec=.25, fc=3000):
    t = T(sec); e = (1 - np.exp(-t / .03)) * np.exp(-t / dec)
    return bp(noise(sec), fc, .8) * e
add('drums', 'snare', 'Snare Besen', brush(), tracks=['snare'])
add('drums', 'snare', 'Snare Besen lang', brush(.9, .45, 2500), tracks=['snare'])

def rimshot(f=420, dec=.05, hi=1700):
    t = T(.25); x = np.sin(2 * np.pi * f * t) * np.exp(-t / dec)
    x += .6 * bp(np.sign(np.sin(2 * np.pi * hi * t)), hi, 4) * np.exp(-t / .02)
    x += .5 * filt(noise(.25), 'hp', 2500) * np.exp(-t / .03)
    return sat(x, .8)
for i, (f, d, h) in enumerate([(420, .05, 1700), (500, .03, 2100), (360, .07, 1500), (600, .025, 2600), (450, .04, 1900), (380, .06, 1300)]):
    add('drums', 'rim', f"Rim {['Klassik','Hell','Holz','Klick','Mittel','Dunkel'][i]}", rimshot(f, d, h), tracks=['rim', 'snare'])

def clap(n=3, gap=.011, fc=1150, tail=.2, q=.9, rev=0, drive=.3):
    sec = n * gap + tail * 5 + .05; t = T(sec); env = np.zeros_like(t)
    for i in range(n):
        s = i * gap * (1 + rng.uniform(-.15, .15)); m = t >= s
        env[m] += np.exp(-(t[m] - s) / .006) * (1 if i == 0 else .85)
    s = n * gap; m = t >= s; env[m] += .9 * np.exp(-(t[m] - s) / tail)
    x = bp(noise(sec), fc, q) * env
    x = sat(x, drive)
    if rev: x = reverb(x, .5, rev, 1.0)
    return x
CLAPS = [('Klassik', {}), ('Kurz', dict(n=2, tail=.07, fc=1500)), ('Groß', dict(n=4, tail=.35, fc=950, rev=.3)),
         ('808', dict(n=4, gap=.009, fc=1050, tail=.25, drive=.8)), ('House', dict(n=3, fc=1300, tail=.18, rev=.2)),
         ('Trap', dict(n=3, gap=.008, fc=1400, tail=.15, drive=1.2)), ('Hell', dict(n=3, fc=2000, tail=.12)),
         ('Dunkel', dict(n=3, fc=800, tail=.22, drive=.6)), ('Stadion', dict(n=6, gap=.014, fc=1100, tail=.4, rev=.5)),
         ('Lo-Fi', dict(n=3, fc=1100, tail=.18)), ('Hall', dict(n=3, fc=1200, tail=.2, rev=.55)), ('Dick', dict(n=5, gap=.01, fc=1000, tail=.28, drive=1.5))]
for name, p in CLAPS:
    x = clap(**p)
    if name == 'Lo-Fi': x = lofi(filt(x, 'lp', 4500), 9, 2)
    add('drums', 'clap', f"Clap {name}", x, tracks=['clap', 'snare'])
def snap(fc=2800, dec=.035):
    t = T(.3); return bp(noise(.3), fc, 2.2) * np.exp(-t / dec) + .25 * np.sin(2 * np.pi * fc * .65 * t) * np.exp(-t / .015)
for i, (fc, d) in enumerate([(2800, .035), (3300, .025), (2300, .045), (3800, .03)]):
    add('drums', 'snap', f"Fingerschnipsen {i+1}", snap(fc, d), tracks=['clap', 'rim'])

# metallic cymbals (808-style square cluster)
RATIOS = [205.3, 304.4, 369.6, 522.7, 540.0, 800.0]
def metal(sec, mult=1.7, spread=1.0):
    t = T(sec); x = np.zeros_like(t)
    for r in RATIOS: x += np.sign(np.sin(2 * np.pi * r * mult * spread * t + rng.uniform(0, 6)))
    return x / 6
def hat(dec=.045, hp=7000, bpf=10000, metal_amt=.6, sec=None, open_=False, lp=None, crush=False, mult=1.7):
    sec = sec or (dec * 6 + .03); t = T(sec)
    m = metal(sec, mult) * metal_amt + noise(sec) * (1 - metal_amt)
    x = bp(m, bpf, 1.2) * .7 + filt(m, 'hp', hp) * .6
    x = filt(x, 'hp', hp)
    env = np.exp(-t / dec) if not open_ else (np.exp(-t / dec) * (1 - np.exp(-t / .002)))
    x = x * env
    if lp: x = filt(x, 'lp', lp)
    if crush: x = lofi(x, 9, 2, .002)
    return x
HATS = [('Klassik', dict()), ('Trap', dict(dec=.03, hp=9000, bpf=11000)), ('Lo-Fi', dict(dec=.05, hp=5500, lp=8000, crush=True)),
        ('Tight', dict(dec=.02, hp=8000)), ('Weich', dict(dec=.04, hp=6000, metal_amt=.2, lp=11000)), ('Metall', dict(dec=.05, metal_amt=.95)),
        ('Hell', dict(dec=.035, hp=10000, bpf=13000)), ('Dunkel', dict(dec=.055, hp=4500, bpf=7000, lp=9000)),
        ('Rauschen', dict(dec=.04, metal_amt=0)), ('808', dict(dec=.05, metal_amt=.85, mult=1.6)), ('909', dict(dec=.06, metal_amt=.45, hp=7500)),
        ('Pedal', dict(dec=.03, hp=4000, bpf=6500, metal_amt=.7)), ('Shaker-Hat', dict(dec=.07, metal_amt=.1, hp=6000)),
        ('Knackig', dict(dec=.015, hp=9500)), ('Glanz', dict(dec=.08, hp=8500, bpf=12000)), ('Staubig', dict(dec=.045, hp=6500, lp=7000, crush=True))]
for name, p in HATS: add('drums', 'hihat', f"Hi-Hat {name}", hat(**p), tracks=['hat'])
OPENS = [('Klassik', dict(dec=.3)), ('Kurz', dict(dec=.16)), ('Lang', dict(dec=.6)), ('Trap', dict(dec=.25, hp=9000, bpf=11500)),
         ('Lo-Fi', dict(dec=.3, lp=8000, crush=True)), ('808', dict(dec=.35, metal_amt=.85, mult=1.6)), ('909', dict(dec=.4, metal_amt=.45)),
         ('Dunkel', dict(dec=.35, hp=4500, bpf=7000)), ('Hell', dict(dec=.28, hp=10000, bpf=13000)), ('Rauschen', dict(dec=.32, metal_amt=0))]
for name, p in OPENS: add('drums', 'openhat', f"Open Hat {name}", hat(open_=True, **p), tracks=['open', 'hat'])
def cymbal(sec, dec, hp, bell=0, mult=1.7):
    t = T(sec); m = metal(sec, mult) * .5 + noise(sec) * .5
    x = filt(m, 'hp', hp) * np.exp(-t / dec) * (1 - np.exp(-t / .003))
    if bell: x += bell * bp(metal(sec, mult * 1.9), 4500, 3) * np.exp(-t / (dec * .5))
    return x
for i, (d, hp, b) in enumerate([(.9, 6000, .6), (.7, 7000, .9), (1.2, 5000, .4), (.5, 8000, 1.2)]):
    add('drums', 'ride', f"Ride {['Klassik','Glocke','Dunkel','Hell'][i]}", cymbal(d * 4, d, hp, b), tracks=['open', 'hat'])
for i, (d, hp) in enumerate([(1.4, 4000), (2.0, 3200), (.9, 5000), (1.6, 3800)]):
    x = cymbal(d * 3.5, d, hp)
    if i == 3: x = x[::-1].copy()
    add('drums', 'crash', f"{['Crash','Crash lang','Splash','Crash rückwärts'][i]}", x, tracks=['open'])

def tom(f0, f1, dec, noise_amt=.12, drive=.3):
    sec = dec * 5 + .05; t = T(sec); fr = f1 + (f0 - f1) * np.exp(-t / (dec * .6))
    x = sweep_sin(fr) * np.exp(-t / dec) + noise_amt * bp(noise(sec), 2500, 1) * np.exp(-t / .015)
    return sat(x, drive)
for style, k, dmul in [('Akustik', 1.0, 1.0), ('Elektro', 1.15, .8), ('808', .85, 1.4)]:
    for nm, f0, f1, d in [('hoch', 240, 160, .22), ('mittel', 170, 110, .28), ('tief', 115, 72, .36)]:
        add('drums', 'tom', f"Tom {nm} {style}", tom(f0 * k, f1 * k, d * dmul, .14 if style == 'Akustik' else .05, .4 if style != '808' else .8), tracks=['tom'])

# ---------------- PERCUSSION ----------------
def membrane(f, dec, slap=.3, bend=1.12):
    sec = dec * 6 + .05; t = T(sec); fr = f * (1 + (bend - 1) * np.exp(-t / .02))
    x = sweep_sin(fr) * np.exp(-t / dec) + .35 * sweep_sin(fr * 1.58) * np.exp(-t / (dec * .5))
    x += slap * bp(noise(sec), 3000, 1.5) * np.exp(-t / .01)
    return x
for nm, f, d, s in [('Conga hoch', 340, .16, .25), ('Conga mittel', 280, .2, .2), ('Conga tief', 220, .24, .2), ('Conga Slap', 330, .07, .9),
                    ('Bongo hoch', 470, .1, .3), ('Bongo tief', 380, .13, .3), ('Djembe Bass', 95, .25, .15), ('Djembe Ton', 300, .14, .4),
                    ('Djembe Slap', 420, .06, 1.0), ('Timbale hoch', 650, .25, .5), ('Timbale tief', 480, .3, .5), ('Tabla', 520, .35, .2)]:
    x = membrane(f, d, s, 1.25 if 'Tabla' in nm else 1.12)
    if nm.startswith('Timbale'): x += .3 * bp(noise(len(x) / SR), 3500, 2) * np.exp(-T(len(x) / SR) / .12)
    add('percussion', 'hand', nm, x, tracks=['rim', 'tom', 'shaker'])
def cowbell(f1=540, f2=800, dec=.25):
    t = T(dec * 5); x = blsqr(f1, dec * 5) * .5 + blsqr(f2, dec * 5) * .5
    return bp(x, 800, 1.3) * (np.exp(-t / .05) * .6 + np.exp(-t / dec) * .4)
for i, p in enumerate([(540, 800, .25), (587, 845, .18), (480, 720, .35)]):
    add('percussion', 'metal', f"Cowbell {['Klassik','Kurz','Tief'][i]}", cowbell(*p), tracks=['rim', 'shaker'])
for i, (f, d) in enumerate([(2500, .045), (2200, .06)]):
    t = T(.3); add('percussion', 'wood', f"Clave {i+1}", np.sin(2 * np.pi * f * t) * np.exp(-t / d), tracks=['rim'])
for i, (f, d) in enumerate([(900, .05), (1200, .04), (700, .07)]):
    t = T(.3); x = sweep_sin(f * (1 + .1 * np.exp(-t / .01))) * np.exp(-t / d) + .2 * sweep_sin(f * 2.7 + 0 * t) * np.exp(-t / (d * .4))
    add('percussion', 'wood', f"Holzblock {['mittel','hoch','tief'][i]}", x, tracks=['rim'])
def shaker(dec=.07, att=.018, fc=5200, sec=.4, q=2.2):
    t = T(sec); env = (1 - np.exp(-t / att)) * np.exp(-t / dec)
    return bp(noise(sec), fc, q) * env
for i, p in enumerate([dict(), dict(dec=.05, fc=6500), dict(dec=.1, att=.03, fc=4500), dict(dec=.04, att=.008, fc=7500),
                       dict(dec=.12, att=.04, fc=5000, sec=.6), dict(dec=.06, fc=3800, q=1.2)]):
    add('percussion', 'shaker', f"Shaker {['Klassik','Hell','Weich','Kurz','Lang','Sand'][i]}", shaker(**p), tracks=['shaker'])
def tamb(dec=.12, hits=2):
    sec = dec * 5 + .1; t = T(sec); x = np.zeros_like(t)
    for h in range(hits):
        s = h * .028; m = t >= s
        x[m] += filt(filt(noise(sec), 'hp', 7000), 'lp', 14000)[: m.sum()] * np.exp(-(t[m] - s) / dec)
    x += .3 * bp(metal(sec, 3.1), 9000, 2) * np.exp(-t / dec)
    return x
for i, (d, h) in enumerate([(.12, 2), (.07, 1), (.2, 3), (.1, 2)]):
    add('percussion', 'shaker', f"Tamburin {['Klassik','Kurz','Lang','Hell'][i]}", tamb(d, h), tracks=['shaker', 'open'])
for i, (f, d) in enumerate([(4000, 1.2), (5200, .8)]):
    t = T(d * 4); x = np.sin(2 * np.pi * f * t) + .5 * np.sin(2 * np.pi * f * 1.56 * t) + .3 * np.sin(2 * np.pi * f * 2.2 * t)
    add('percussion', 'metal', f"Triangel {['offen','kurz'][i]}", x * np.exp(-t / d) * .5, tracks=['shaker', 'open'])
def guiro(n=9, gap=.018):
    sec = n * gap + .1; t = T(sec); env = np.zeros_like(t)
    for i in range(n):
        s = i * gap; m = t >= s; env[m] += np.exp(-(t[m] - s) / .005)
    return bp(noise(sec), 3200, 3) * env
add('percussion', 'wood', 'Guiro kurz', guiro(7, .016), tracks=['shaker'])
add('percussion', 'wood', 'Guiro lang', guiro(14, .02), tracks=['shaker'])
for i, (f, d) in enumerate([(3100, 1.8), (2200, 2.4)]):
    t = T(d * 3); x = sum(np.sin(2 * np.pi * f * r * t) * np.exp(-t / (d / r ** .5)) / r for r in [1, 2.76, 5.4, 8.9])
    add('percussion', 'metal', f"Glöckchen {i+1}", x, tracks=['shaker', 'open'])
for i, (f, d) in enumerate([(1200, .4), (900, .6)]):
    t = T(d * 4); x = sum(np.sin(2 * np.pi * f * r * t) * np.exp(-t / d) for r in [1, 1.48, 2.1, 2.9]) * .4
    add('percussion', 'metal', f"Agogo {['hoch','tief'][i]}", x * (1 - np.exp(-t / .002)), tracks=['rim'])
for i, (d, f) in enumerate([(.3, 2000), (.5, 1400)]):
    t = T(d * 3); x = filt(noise(d * 3), 'bp', (f * .7, f * 1.6)) * np.exp(-t / d) * (1 - np.exp(-t / .05))
    add('percussion', 'shaker', f"Cabasa {i+1}", x, tracks=['shaker'])

# ---------------- BASS ----------------
def b808(m=24, dec=.9, drive=.8, glide=0, punch=6, sec=None):
    f = mtof(m); sec = sec or dec * 2.5 + .1; t = T(sec)
    fr = f * (1 + (2 ** (punch / 12) - 1) * np.exp(-t / .03))
    if glide: fr = fr * (2 ** (glide / 12)) ** np.exp(-t / .08)
    x = sweep_sin(fr) * (np.exp(-t / dec) * .7 + np.exp(-t / (dec * .3)) * .3)
    x += .15 * filt(noise(sec), 'hp', 3000) * np.exp(-t / .003)
    return sat(x, drive)
B808 = [('Klassik', {}), ('Kurz', dict(dec=.35)), ('Lang', dict(dec=1.6)), ('Verzerrt', dict(drive=3.5)), ('Glide hoch', dict(glide=-7, dec=1.1)),
        ('Glide tief', dict(glide=7, dec=1.1)), ('Sauber', dict(drive=0, punch=3)), ('Hart', dict(drive=2, punch=12, dec=.7)),
        ('Rund', dict(drive=.3, punch=4, dec=1.2)), ('Dreckig', dict(drive=6, dec=.8)), ('Boom', dict(drive=1.2, punch=9, dec=1.4)), ('Trap', dict(drive=2.6, punch=10, dec=1.0))]
for name, p in B808: add('bass', '808', f"808 {name}", b808(**p), kind='melodic', root=24, tracks=['bass'])
def synbass(kind, m=36, sec=.7, cutoff=900, env_amt=2500, res=1.0, dec=.25, drive=.3, detune=0, sub=0):
    f = mtof(m); t = T(sec)
    if kind == 'saw': x = blsaw(f, sec)
    elif kind == 'sqr': x = blsqr(f, sec)
    elif kind == 'reese': x = blsaw(f * 2 ** (-.12 / 12), sec) + blsaw(f * 2 ** (.12 / 12), sec)
    elif kind == 'sin': x = np.sin(2 * np.pi * f * t)
    if detune: x = x + blsaw(f * 2 ** (detune / 1200), sec)
    if sub: x = x + sub * np.sin(2 * np.pi * f / 2 * t)
    # moving lowpass via block processing
    out = np.zeros_like(x); blk = 256; zi = None
    for i in range(0, len(x), blk):
        tt = i / SR; fc = cutoff + env_amt * np.exp(-tt / dec)
        b, a = signal.iirfilter(2, min(fc, SR * .45) / (SR / 2), btype='low', ftype='butter')
        if res > 1.2:
            b, a = signal.iirpeak(min(fc, SR * .45) / (SR / 2), res) if False else (b, a)
        if zi is None: zi = signal.lfilter_zi(b, a) * 0
        out[i:i + blk], zi = signal.lfilter(b, a, x[i:i + blk], zi=zi)
    if res > 1.2:
        out = out + (res - 1) * .15 * bp(out, cutoff + env_amt * .3, res * 2)
    env = adsr(sec, .004, .2, .6, .08)
    return sat(out * env, drive)
BASSES = [('Synth', dict(kind='sqr', cutoff=700, env_amt=1800, sub=.4)), ('Reese', dict(kind='reese', sec=1.0, cutoff=500, env_amt=600, dec=.5, drive=.8)),
          ('Acid', dict(kind='saw', cutoff=400, env_amt=3500, dec=.12, res=6, drive=1.0)), ('Zupf', dict(kind='saw', sec=.45, cutoff=300, env_amt=2600, dec=.06)),
          ('Sub', dict(kind='sin', sec=.8, cutoff=400, env_amt=0, drive=.4)), ('Saw', dict(kind='saw', cutoff=1200, env_amt=1500, sub=.3)),
          ('Funk', dict(kind='sqr', sec=.4, cutoff=500, env_amt=3000, dec=.05, drive=.5)), ('Wobble', dict(kind='reese', sec=1.2, cutoff=300, env_amt=400, dec=.8, drive=1.5)),
          ('Dunkel', dict(kind='saw', cutoff=250, env_amt=500, sub=.6)), ('Moog', dict(kind='saw', detune=8, cutoff=350, env_amt=2000, dec=.15, drive=.6, sub=.3)),
          ('Pluck tief', dict(kind='sqr', sec=.5, cutoff=200, env_amt=2200, dec=.07, sub=.3)), ('Fett', dict(kind='reese', cutoff=700, env_amt=1500, dec=.2, drive=2.0, sub=.5))]
for name, p in BASSES:
    x = synbass(**p)
    if name == 'Wobble':
        t = T(len(x) / SR); lfo = .5 + .5 * np.sin(2 * np.pi * 4 * t - np.pi / 2); x = x * (.3 + .7 * lfo)
    add('bass', 'synth', f"Bass {name}", x, kind='melodic', root=36, tracks=['bass'])
# upright / picked via karplus
def karplus(f, sec, damp=.996, bright=.5, pluck_pos=.0):
    n = int(SR * sec); N = max(2, int(round(SR / f)))
    buf = rng.uniform(-1, 1, N); buf = filt(buf, 'lp', 1000 + 9000 * bright) if N > 12 else buf
    out = np.zeros(n); idx = 0
    for i in range(n):
        out[i] = buf[idx]; nxt = (idx + 1) % N
        buf[idx] = damp * .5 * (buf[idx] + buf[nxt]); idx = nxt
    return out
add('bass', 'synth', 'Bass Kontrabass', filt(karplus(mtof(36), 1.4, .994, .25), 'lp', 1800) * adsr(1.4, .005, .5, .5, .2), kind='melodic', root=36, tracks=['bass'])
add('bass', 'synth', 'Bass E-Bass', sat(karplus(mtof(36), 1.2, .996, .45), .6), kind='melodic', root=36, tracks=['bass'])

# ---------------- INSTRUMENTS (melodic one-shots at C4) ----------------
M = 60; F = mtof(M)
def fm(f, ratio, index, idec, sec, adec):
    t = T(sec); mod = np.sin(2 * np.pi * f * ratio * t) * f * index * (np.exp(-t / idec) * .92 + .08)
    return np.sin(2 * np.pi * np.cumsum(f + mod) / SR) * np.exp(-t / adec)
def piano(f, sec=2.5, bright=1.0):
    t = T(sec); x = np.zeros_like(t)
    for k in range(1, 14):
        fk = f * k * np.sqrt(1 + .0004 * k * k)
        x += (bright ** (k - 1)) * np.sin(2 * np.pi * fk * t) / k ** 1.1 * np.exp(-t / (1.6 / k ** .7))
    x += .2 * filt(noise(sec), 'bp', (f, f * 8)) * np.exp(-t / .01)
    return x * (1 - np.exp(-t / .002))
def stereo_detune(fn, cents=8):
    return stereo(fn(F * 2 ** (-cents / 1200)), fn(F * 2 ** (cents / 1200)))
INSTR = []
INSTR.append(('keys', 'Piano', piano(F)))
INSTR.append(('keys', 'Piano weich', filt(piano(F, 2.5, .7), 'lp', 3000)))
INSTR.append(('keys', 'Piano Lo-Fi', lofi(filt(piano(F, 2.2, .8), 'lp', 3500), 10, 2, .003)))
INSTR.append(('keys', 'E-Piano', fm(F, 1, 1.8, .5, 2.4, 1.3) + .15 * fm(F, 14, .8, .03, 2.4, .2)))
INSTR.append(('keys', 'E-Piano hell', fm(F, 1, 3.0, .3, 2.2, 1.1) + .2 * fm(F, 14, 1, .02, 2.2, .15)))
t = T(2.0); org = sum(a * np.sin(2 * np.pi * F * m * t) for m, a in [(.5, .6), (1, 1), (2, .6), (3, .35), (4, .25), (8, .12)]) * adsr(2.0, .01, .05, 1, .08)
INSTR.append(('keys', 'Orgel', org * (1 + .15 * np.sin(2 * np.pi * 6 * t))))
t = T(1.2); INSTR.append(('keys', 'Clavinet', bp(blsqr(F, 1.2) * .7 + blsaw(F, 1.2) * .3, F * 4, 1.2) * np.exp(-t / .35)))
INSTR.append(('mallets', 'Glocke', fm(F, 3.5, 3, 1.5, 3.0, 1.4)))
INSTR.append(('mallets', 'Röhrenglocke', fm(F, 2.76, 2, 2.5, 4.0, 2.2)))
t = T(1.2); INSTR.append(('mallets', 'Marimba', np.sin(2 * np.pi * F * t) * np.exp(-t / .35) + .35 * np.sin(2 * np.pi * F * 4 * t) * np.exp(-t / .05) + .1 * np.sin(2 * np.pi * F * 10 * t) * np.exp(-t / .015)))
t = T(1.6); INSTR.append(('mallets', 'Kalimba', np.sin(2 * np.pi * F * t) * np.exp(-t / .55) + .3 * np.sin(2 * np.pi * F * 5.4 * t) * np.exp(-t / .06)))
t = T(3.0); INSTR.append(('mallets', 'Vibraphon', (np.sin(2 * np.pi * F * t) + .12 * np.sin(2 * np.pi * F * 4 * t) * np.exp(-t / .2)) * np.exp(-t / 1.3) * (.8 + .2 * np.sin(2 * np.pi * 5 * t))))
INSTR.append(('mallets', 'Spieluhr', fm(F * 2, 5, 1.2, .3, 2.0, .9)))
t = T(2.5); INSTR.append(('mallets', 'Steeldrum', sum(a * np.sin(2 * np.pi * F * r * t) * np.exp(-t / d) for r, a, d in [(1, 1, .9), (2, .5, .6), (3, .25, .3), (1.98, .3, .4)])))
INSTR.append(('strings', 'Gitarre', filt(karplus(F, 2.5, .997, .55), 'lp', 6000)))
INSTR.append(('strings', 'Gitarre gedämpft', filt(karplus(F, 1.0, .985, .35), 'lp', 3000)))
INSTR.append(('strings', 'Harfe', karplus(F, 3.0, .998, .4)))
INSTR.append(('strings', 'Sitar-artig', sat(karplus(F, 2.5, .998, .9) + .3 * karplus(F * 2.01, 2.5, .997, .9), .8)))
def strings_fn(f, sec=2.6):
    t = T(sec); vib = 1 + .004 * np.sin(2 * np.pi * 5.5 * t) * (1 - np.exp(-t / .4))
    x = sum(blsaw(f * 2 ** (c / 1200), sec, 20) for c in (-7, 0, 7))
    x = x * 0 + sum(osc('saw', np.full(len(t), f * 2 ** (c / 1200)) * vib) for c in (-7, 0, 7))
    return filt(x, 'lp', 3200, 2) * adsr(sec, .25, .3, .85, .5)
INSTR.append(('strings', 'Streicher', stereo_detune(strings_fn, 6)))
INSTR.append(('strings', 'Pizzicato', filt(karplus(F, 1.0, .99, .4), 'lp', 4000) * np.exp(-T(1.0) / .3)))
def brass_fn(f, sec=1.6):
    t = T(sec); x = sum(osc('saw', np.full(len(t), f * 2 ** (c / 1200))) for c in (-6, 6))
    out = np.zeros_like(x); blk = 256; zi = None
    for i in range(0, len(x), blk):
        tt = i / SR; fc = 600 + 2800 * (1 - np.exp(-tt / .05)) * (.7 + .3 * np.exp(-tt / .3))
        b, a = signal.butter(2, fc / (SR / 2))
        if zi is None: zi = signal.lfilter_zi(b, a) * 0
        out[i:i + blk], zi = signal.lfilter(b, a, x[i:i + blk], zi=zi)
    return out * adsr(sec, .04, .2, .8, .15)
INSTR.append(('winds', 'Brass', brass_fn(F)))
def flute_fn(f, sec=1.8):
    t = T(sec); vib = 1 + .005 * np.sin(2 * np.pi * 5 * t) * (1 - np.exp(-t / .3))
    x = osc('sin', np.full(len(t), f) * vib) + .1 * osc('tri', np.full(len(t), 2 * f) * vib) + .06 * bp(noise(sec), f * 2, 2)
    return x * adsr(sec, .07, .1, .85, .15)
INSTR.append(('winds', 'Flöte', flute_fn(F)))
t = T(1.8); INSTR.append(('winds', 'Pan-Flöte', (np.sin(2 * np.pi * F * t) + .25 * bp(noise(1.8), F, 3)) * adsr(1.8, .03, .2, .7, .3)))
def vowel(f, formants, sec=1.6, vib=.006):
    t = T(sec); fr = np.full(len(t), f) * (1 + vib * np.sin(2 * np.pi * 5.2 * t) * (1 - np.exp(-t / .3)))
    src = osc('saw', fr) * .6 + osc('pulse25', fr) * .4
    x = sum(a * bp(src, fc, fc / bw) for fc, bw, a in formants)
    return x * adsr(sec, .08, .2, .85, .3)
FORM = {'A': [(800, 80, 1), (1150, 90, .5), (2900, 120, .25)], 'O': [(450, 70, 1), (800, 80, .4), (2830, 100, .15)],
        'E': [(400, 60, 1), (1600, 80, .4), (2700, 120, .25)], 'I': [(270, 60, 1), (2140, 90, .3), (2950, 100, .2)], 'U': [(325, 50, 1), (700, 60, .3), (2530, 100, .1)]}
INSTR.append(('voices', 'Chor Ah', stereo(vowel(F * 2 ** (-.08 / 12), FORM['A']), vowel(F * 2 ** (.08 / 12), FORM['A']))))
INSTR.append(('voices', 'Chor Oh', stereo(vowel(F * 2 ** (-.08 / 12), FORM['O']), vowel(F * 2 ** (.08 / 12), FORM['O']))))
for v in 'AEIOU':
    INSTR.append(('voices', f"Vox {v}", vowel(F, FORM[v], .7, .01)))
INSTR.append(('synth', 'Pluck', filt(blsaw(F, 1.0), 'lp', 2400) * np.exp(-T(1.0) / .18)))
INSTR.append(('synth', 'Pluck hell', filt(blsqr(F, 1.0) * .6 + blsaw(F, 1.0) * .4, 'lp', 5000) * np.exp(-T(1.0) / .12)))
def lead_fn(f, sec=1.4):
    t = T(sec); vib = 1 + .006 * np.sin(2 * np.pi * 5.5 * t) * (t > .25)
    x = sum(osc('saw', np.full(len(t), f * 2 ** (c / 1200)) * vib) for c in (-10, 10))
    return filt(x, 'lp', 3500) * adsr(sec, .01, .2, .75, .15)
INSTR.append(('synth', 'Lead', lead_fn(F)))
def supersaw_fn(f, sec=1.8):
    t = T(sec); x = sum(osc('saw', np.full(len(t), f * 2 ** (c / 1200))) for c in (-24, -14, -6, 0, 6, 14, 24))
    return filt(x / 3, 'lp', 5500) * adsr(sec, .02, .3, .8, .3)
INSTR.append(('synth', 'Supersaw', stereo_detune(supersaw_fn, 4)))
def pad_fn(f, sec=4.0):
    t = T(sec); x = sum(osc('saw', np.full(len(t), f * 2 ** (c / 1200))) for c in (-12, 0, 12)) + .5 * np.sin(2 * np.pi * f / 2 * t)
    out = np.zeros_like(x); blk = 512; zi = None
    for i in range(0, len(x), blk):
        tt = i / SR; fc = 500 + 1800 * (1 - np.exp(-tt / 1.2))
        b, a = signal.butter(2, fc / (SR / 2))
        if zi is None: zi = signal.lfilter_zi(b, a) * 0
        out[i:i + blk], zi = signal.lfilter(b, a, x[i:i + blk], zi=zi)
    return out * adsr(sec, .8, .5, .9, 1.2)
INSTR.append(('synth', 'Pad warm', stereo_detune(pad_fn, 7)))
def glass_fn(f, sec=4.0):
    t = T(sec); return (fm(f, 2, 1.2, 1.5, sec, 3) + .4 * np.sin(2 * np.pi * f * 2 * t)) * adsr(sec, .6, .5, .9, 1.2)
INSTR.append(('synth', 'Pad gläsern', stereo_detune(glass_fn, 5)))
t = T(.8); INSTR.append(('synth', 'Chiptune', blsqr(F, .8) * .5 * adsr(.8, .002, .05, .7, .05)))
t = T(.8); INSTR.append(('synth', 'Chiptune Puls', (osc('pulse25', np.full(len(t), F))) * .5 * adsr(.8, .002, .05, .7, .05)))
INSTR.append(('synth', 'Sinus Lead', np.sin(2 * np.pi * F * T(1.4)) * adsr(1.4, .01, .1, .8, .2)))
INSTR.append(('synth', 'Wobble Lead', filt(blsaw(F, 1.4), 'lp', 2000) * (0.55 + .45 * np.sin(2 * np.pi * 6 * T(1.4))) * adsr(1.4, .01, .1, .8, .15)))
def hoover_fn(sec=1.6):
    t = T(sec); bend = 1 + .03 * np.exp(-t / .1)
    x = sum(osc('saw', np.full(len(t), F * 2 ** (c / 1200)) * bend) for c in (-30, 0, 30))
    return sat(filt(x / 2, 'lp', 4000) * adsr(sec, .02, .2, .8, .2), .8)
INSTR.append(('synth', 'Hoover', hoover_fn()))
for grp, name, x in INSTR:
    tr = ['lead', 'chords']
    add('instruments', grp, name, x, kind='melodic', root=M, tracks=tr, fade_out=.05)

# ---------------- CHORD STABS (root C4) ----------------
CHORDS = {'Moll': [0, 3, 7], 'Dur': [0, 4, 7], 'Moll7': [0, 3, 7, 10], 'Maj7': [0, 4, 7, 11], 'Sus2': [0, 2, 7], 'Moll9': [0, 3, 7, 10, 14]}
for cname, iv in CHORDS.items():
    for sname, fn in [('E-Piano', lambda f: fm(f, 1, 1.6, .4, 2.0, 1.1)), ('Stab', lambda f: filt(blsaw(f, .8, 30), 'lp', 3000) * np.exp(-T(.8) / .18))]:
        x = sum(fn(F * 2 ** (i / 12)) for i in iv) / len(iv) ** .5
        add('chords', 'stab', f"{sname} {cname}", x, kind='melodic', root=M, tracks=['chords'], tags=[cname], fade_out=.05)
for cname in ['Moll', 'Moll7', 'Dur', 'Maj7']:
    iv = CHORDS[cname]; x = sum(pad_fn(F * 2 ** (i / 12), 4.0) for i in iv) / len(iv) ** .5
    add('chords', 'pad', f"Pad {cname}", stereo(x, np.roll(x, 600)), kind='melodic', root=M, tracks=['chords'], tags=[cname], fade_out=.4)
for cname in ['Moll', 'Dur', 'Moll7']:
    iv = CHORDS[cname]; x = sum(np.roll(pad_to(karplus(F / 2 * 2 ** (i / 12), 2.5, .997, .5), int(SR * 2.6)), int(SR * .018 * k)) for k, i in enumerate(iv + [12]))
    add('chords', 'guitar', f"Gitarre {cname}", x, kind='melodic', root=M - 12, tracks=['chords'], tags=[cname], fade_out=.1)

# ---------------- FX ----------------
def riser(sec=2.0, f0=300, f1=9000):
    t = T(sec); out = np.zeros(len(t)); blk = 256; nz = noise(sec); zi = None
    for i in range(0, len(t), blk):
        fc = f0 * (f1 / f0) ** (i / len(t)); lo, hi = fc * .7, min(fc * 1.4, SR * .45)
        s = signal.butter(2, [lo / (SR / 2), hi / (SR / 2)], 'bandpass', output='sos')
        if zi is None: zi = np.zeros((s.shape[0], 2))
        out[i:i + blk], zi = signal.sosfilt(s, nz[i:i + blk], zi=zi)
    env = (t / sec) ** 2
    tone = np.sin(2 * np.pi * np.cumsum(200 * (8 ** (t / sec))) / SR) * .25
    return (out + tone) * env
for i, (s, f0, f1) in enumerate([(2.0, 300, 9000), (4.0, 200, 12000), (1.0, 500, 8000), (8.0, 150, 10000)]):
    x = riser(s, f0, f1); add('fx', 'riser', f"Riser {['2 s','4 s','1 s','8 s'][i]}", stereo(x, np.roll(x, 300)), tags=['übergang'], fade_out=.02)
for i, (s, f0, f1) in enumerate([(2.0, 9000, 200), (1.0, 7000, 300), (3.0, 12000, 150)]):
    x = riser(s, f0, f1)[::-1][::-1]
    t = T(s); x = riser(s, f1, f0)[::-1]
    add('fx', 'downlifter', f"Downlifter {i+1}", x, tags=['übergang'])
def impact(sec=2.5):
    t = T(sec); boom = sweep_sin(30 + 90 * np.exp(-t / .1)) * np.exp(-t / .7)
    crash = filt(noise(sec), 'hp', 2000) * np.exp(-t / .5) * .4
    return reverb(sat(boom + crash, 1.5), .7, .35, 1.5)
for i in range(4):
    add('fx', 'impact', f"Impact {i+1}", impact([2.5, 1.5, 3.5, 2.0][i]), tags=['drop'])
for i, (f0, f1, d) in enumerate([(140, 30, 1.2), (110, 25, 2.0), (200, 40, .8)]):
    t = T(d * 1.2); x = sweep_sin(f1 + (f0 - f1) * np.exp(-t / (d * .4))) * np.exp(-t / d)
    add('fx', 'drop', f"Sub Drop {i+1}", sat(x, .6), tracks=['kick'])
for i, (f0, f1, d) in enumerate([(2400, 90, .3), (4000, 200, .2), (1200, 60, .5)]):
    t = T(d); x = osc('saw', f1 + (f0 - f1) * np.exp(-t / (d * .3))) * np.exp(-t / (d * .6))
    add('fx', 'laser', f"Laser {i+1}", filt(x, 'lp', 6000), tracks=['rim'])
for i, (f0, d) in enumerate([(1300, .15), (900, .1), (2200, .08)]):
    t = T(d); x = osc('sqr', 55 + f0 * np.exp(-t / (d * .25))) * np.exp(-t / (d * .5))
    add('fx', 'laser', f"Zap {i+1}", x, tracks=['rim'])
for i, (d, f0, f1) in enumerate([(.7, 5000, 400), (1.2, 300, 6000), (.5, 7000, 900)]):
    t = T(d); x = riser(d, f0, f1) if f1 > f0 else riser(d, f1, f0)[::-1]
    add('fx', 'whoosh', f"Whoosh {i+1}", x * np.sin(np.pi * t / d), tags=['übergang'])
def scratch(sec=.35, pattern=(700, 2800, 600, 2400)):
    t = T(sec); fr = np.interp(t, np.linspace(0, sec, len(pattern)), pattern)
    src = piano(110, sec, .9)[:len(t)] + .3 * noise(sec)
    out = np.zeros(len(t)); blk = 128; zi = None
    for i in range(0, len(t), blk):
        fc = fr[i]; s = signal.butter(2, [fc * .6 / (SR / 2), min(fc * 1.6, SR * .45) / (SR / 2)], 'bandpass', output='sos')
        if zi is None: zi = np.zeros((s.shape[0], 2))
        out[i:i + blk], zi = signal.sosfilt(s, src[i:i + blk], zi=zi)
    amp = np.abs(np.gradient(fr)) ; amp = amp / (amp.max() + 1e-9)
    return sat(out * (.3 + .7 * amp), 1.0)
for i, pat in enumerate([(700, 2800, 600, 2400), (1500, 400, 2600), (500, 3000, 500, 3000, 500, 3000)]):
    add('fx', 'scratch', f"Scratch {i+1}", scratch(.35 + .1 * i, pat), tracks=['rim', 'clap'])
for i, (d, rate) in enumerate([(2.0, .0009), (3.0, .0006)]):
    n = int(SR * d); x = rng.normal(0, .02, n); clicks = rng.random(n) < rate; x[clicks] = rng.uniform(-.9, .9, clicks.sum())
    add('fx', 'texture', f"Vinyl-Knistern {i+1}", filt(x, 'bp', (300, 8000)), tracks=['shaker'], trim=False, fade_out=.05)
for i in range(2):
    sec = 1.2; t = T(sec); base = piano(F, sec, .9) + .5 * blsaw(F / 2, sec)
    rate = np.clip(1 - (t / sec) ** (1.5 + i), .02, 1); idx = np.cumsum(rate); idx = idx[idx < len(base) - 1]
    x = np.interp(idx, np.arange(len(base)), base)
    add('fx', 'texture', f"Tape-Stopp {i+1}", x, tags=['übergang'])
def horn(sec=1.0, f=440):
    t = T(sec); env = np.zeros_like(t)
    for k in range(3):
        s, e = k * .17, k * .17 + .12; env[(t >= s) & (t < e)] = 1
    env = filt(env, 'lp', 60)
    fr = f * (1 - .08 * np.exp(-((t % .17) / .03)))
    x = sum(osc('saw', fr * 2 ** (c / 1200)) for c in (-15, 0, 15))
    return filt(x, 'lp', 3000) * env
add('fx', 'horn', 'Air Horn', horn(), tags=['dancehall'])
add('fx', 'horn', 'Air Horn tief', horn(1.0, 330), tags=['dancehall'])
for i in range(3):
    sec = 2.0; t = T(sec); x = filt(noise(sec), 'hp', 3000 + i * 1500) * (t / sec) ** 2.2
    add('fx', 'reverse', f"Reverse Becken {i+1}", x, tags=['übergang'], fade_out=.005)
for i, (f, d) in enumerate([(880, 1.5), (1320, 1.0)]):
    t = T(d * 2); x = np.sin(2 * np.pi * f * t) * np.exp(-t / d) * (1 - np.exp(-t / .003))
    add('fx', 'tone', f"Ping {i+1}", reverb(x, .6, .35, 1.0), kind='melodic', root=81 if i == 0 else 88)

# ---------------- LOOPS (built from the pack) ----------------
LIB = {}
def get(cat, sub, i):
    m = [e for e in MANIFEST if e['category'] == cat and e['group'] == sub]
    e = m[(i - 1) % len(m)]
    with wave.open(os.path.join(OUT, e['file'])) as w:
        d = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').astype(float) / 32767
        if w.getnchannels() == 2: d = d.reshape(-1, 2).mean(1)
    return d
def pitched(x, semis):
    if semis == 0: return x
    r = 2 ** (semis / 12); idx = np.arange(0, len(x) - 1, r); return np.interp(idx, np.arange(len(x)), x)
def loop(bpm, bars, pattern, swing=0.0, pan=None):
    spb = 60 / bpm / 4; n = int(SR * spb * 16 * bars); L = np.zeros(n); R = np.zeros(n)
    for (snd, steps, vel, p) in pattern:
        for b in range(bars):
            for s, ch in enumerate(steps):
                if ch == '.': continue
                semi = 0
                if ch.isdigit(): semi = int(ch) - 1  # unused for drums
                v = vel * (1.0 if ch in 'X' else .72)
                pos = int(SR * (b * 16 + s) * spb + (spb * swing * .5 * SR if s % 2 else 0))
                x = snd * v; e = min(n, pos + len(x))
                if e <= pos: continue
                gl, gr = (1 - max(0, p)), (1 + min(0, p))
                L[pos:e] += x[:e - pos] * gl; R[pos:e] += x[:e - pos] * gr
    return stereo(L, R)
DRUMLOOPS = [
 ('Boom Bap', 90, .35, [(('drums','kick',1), 'X......x..X.....', 1, 0), (('drums','snare',15), '....X.......X...', .9, 0), (('drums','hihat',1), 'x.x.x.x.x.x.x.x.', .45, .25), (('drums','openhat',1), '..............x.', .35, .25)]),
 ('Trap', 140, 0, [(('drums','kick',12), 'X......X..X.....', 1, 0), (('drums','clap',6), '........X.......', .9, 0), (('drums','hihat',2), 'x.x.x.x.x.xxxxxx', .4, .2), (('drums','openhat',4), '...............x', .3, .2)]),
 ('House', 124, .1, [(('drums','kick',5), 'X...X...X...X...', 1, 0), (('drums','clap',5), '....X.......X...', .8, 0), (('drums','openhat',1), '..X...X...X...X.', .4, .3), (('percussion','shaker',1), 'xxxxxxxxxxxxxxxx', .25, -.3)]),
 ('Lo-Fi', 78, .5, [(('drums','kick',7), 'X.......X.x.....', 1, 0), (('drums','snare',4), '....X.......X...', .8, 0), (('drums','hihat',3), 'x.x.xx..x.x.x.xx', .4, .2), (('fx','texture',1), 'X...............', .25, 0)]),
 ('Reggaeton', 96, 0, [(('drums','kick',2), 'X...X...X...X...', 1, 0), (('drums','snare',10), '...x..x....x..x.', .8, 0), (('drums','hihat',1), 'x.x.x.x.x.x.x.x.', .35, .2), (('drums','rim',2), '...x..x....x..x.', .3, -.3)]),
 ('Afrobeats', 104, .2, [(('drums','kick',2), 'X..x..x...x..x..', 1, 0), (('drums','rim',1), '...x..x....x..x.', .6, .2), (('percussion','hand',1), '......x.....x.x.', .55, -.3), (('percussion','shaker',2), 'xxxxxxxxxxxxxxxx', .25, .3), (('percussion','wood',1), 'x..x..x...x.x...', .4, -.2)]),
 ('Techno', 128, 0, [(('drums','kick',6), 'X...X...X...X...', 1, 0), (('drums','hihat',4), '..x...x...x...x.', .45, .2), (('drums','clap',2), '....X.......X...', .5, 0), (('drums','ride',4), 'x.x.x.x.x.x.x.x.', .2, -.3)]),
 ('Drum and Bass', 172, 0, [(('drums','kick',2), 'X.........X.....', 1, 0), (('drums','snare',2), '....X.......X...', .9, 0), (('drums','hihat',7), 'x.x.x.x.x.x.x.x.', .35, .2)]),
 ('Dancehall', 100, .15, [(('drums','kick',1), 'X..x..X...X..x..', 1, 0), (('drums','snare',5), '....X.......X...', .8, 0), (('drums','rim',3), 'x..x..x...x.x...', .4, .3), (('drums','hihat',5), 'x.x.x.x.x.x.x.x.', .3, -.2)]),
 ('Rock', 120, 0, [(('drums','kick',8), 'X.......X.X.....', 1, 0), (('drums','snare',6), '....X.......X...', .95, 0), (('drums','hihat',10), 'x.x.x.x.x.x.x.x.', .4, .2), (('drums','crash',1), 'X...............', .3, -.2)]),
 ('Jersey Club', 140, 0, [(('drums','kick',4), 'X..X..X...X.X.X.', 1, 0), (('drums','clap',2), '....X.......X...', .8, 0), (('drums','hihat',4), 'x.x.x.x.x.x.x.x.', .3, .2)]),
 ('Garage', 132, .45, [(('drums','kick',24), 'X......X..X.....', 1, 0), (('drums','snare',10), '....X.......X...', .8, 0), (('drums','hihat',1), '..x...x...x...x.', .45, .2), (('percussion','shaker',4), 'x.x.x.x.x.x.x.x.', .25, -.25)]),
]
for name, bpm, sw, parts in DRUMLOOPS:
    pat = [(get(*src), steps, vel, p) for (src, steps, vel, p) in parts]
    add('loops', 'drums', f"{name} {bpm} BPM", loop(bpm, 2, pat, sw), kind='loop', bpm=bpm, bars=2, trim=False, fade_out=.003, peak=-1.5)
# melodic loops (C minor) using pack instruments
def note_loop(bpm, bars, src, root_midi, notes, length_steps=2, vel=.7):
    spb = 60 / bpm / 4; n = int(SR * spb * 16 * bars); out = np.zeros(n)
    for (step, semi, ln) in notes:
        x = pitched(src, semi + (root_midi - 60) * 0); dur = int(SR * spb * (ln or length_steps))
        x = x[:dur].copy(); f = min(len(x), int(SR * .02)); x[-f:] *= np.linspace(1, 0, f)
        pos = int(SR * step * spb); e = min(n, pos + len(x)); out[pos:e] += x[:e - pos] * vel
    return out
src_keys = get('instruments', 'keys', 4); src_pluck = get('instruments', 'synth', 1); src_bell = get('instruments', 'mallets', 4)
cm = [0, 3, 7]; ab = [-4, 0, 3]; eb = [3, 7, 10]; bb = [-2, 2, 5]
prog = []
for b, ch in enumerate([cm, ab, eb, bb]):
    for s in (0, 6, 10): prog += [(b * 16 + s, i, 5 if s == 0 else 3) for i in ch]
add('loops', 'melodic', 'Akkorde E-Piano Cm 90 BPM', note_loop(90, 4, src_keys, 60, prog, vel=.45), kind='loop', bpm=90, bars=4, trim=False, fade_out=.003, tags=['C Moll'])
mel = [(0, 7, 2), (3, 10, 1), (4, 12, 3), (8, 10, 2), (10, 7, 2), (12, 3, 4), (16, 8, 3), (20, 7, 2), (22, 3, 2), (24, 0, 6), (32, 7, 2), (35, 10, 1), (36, 15, 3), (40, 12, 4), (44, 10, 2), (48, 10, 3), (52, 8, 2), (54, 7, 2), (56, 5, 6)]
add('loops', 'melodic', 'Melodie Pluck Cm 90 BPM', note_loop(90, 4, src_pluck, 60, mel, vel=.6), kind='loop', bpm=90, bars=4, trim=False, fade_out=.003, tags=['C Moll'])
arp = [(s, [0, 3, 7, 12, 7, 3][s % 6] + [0, -4, 3, -2][s // 16], 2) for s in range(0, 64, 2)]
add('loops', 'melodic', 'Arpeggio Kalimba Cm 140 BPM', note_loop(140, 4, src_bell, 60, arp, vel=.5), kind='loop', bpm=140, bars=4, trim=False, fade_out=.003, tags=['C Moll'])

# ---------------- write manifest ----------------
CAT_NAMES = {'drums': 'Drums', 'percussion': 'Percussion', 'bass': 'Bass', 'instruments': 'Instrumente', 'chords': 'Akkorde', 'fx': 'Effekte', 'loops': 'Loops'}
GROUP_NAMES = {'kick': 'Kicks', 'snare': 'Snares', 'rim': 'Rimshots', 'clap': 'Claps', 'snap': 'Snaps', 'hihat': 'Hi-Hats', 'openhat': 'Open Hats', 'ride': 'Rides', 'crash': 'Crashes',
               'tom': 'Toms', 'hand': 'Handtrommeln', 'metal': 'Metall', 'wood': 'Holz', 'shaker': 'Shaker & Tamburin', '808': '808', 'synth': 'Bass-Synths',
               'keys': 'Tasten', 'mallets': 'Mallets & Glocken', 'strings': 'Saiten', 'winds': 'Bläser', 'voices': 'Stimmen', 'stab': 'Stabs', 'pad': 'Pads', 'guitar': 'Gitarre',
               'riser': 'Riser', 'downlifter': 'Downlifter', 'impact': 'Impacts', 'drop': 'Sub Drops', 'laser': 'Laser & Zaps', 'whoosh': 'Whooshes', 'scratch': 'Scratches',
               'texture': 'Texturen', 'horn': 'Hörner', 'reverse': 'Rückwärts', 'tone': 'Töne', 'drums': 'Drum-Loops', 'melodic': 'Melodie-Loops'}
man = {'name': 'PS AI MUSIC Sample Pack', 'version': '1.0', 'sampleRate': SR, 'bitDepth': 16, 'format': 'wav',
       'license': 'Alle Sounds wurden synthetisch erzeugt (keine Fremdaufnahmen). Frei nutzbar für PS AI MUSIC, auch kommerziell.',
       'categories': CAT_NAMES, 'groups': GROUP_NAMES, 'count': len(MANIFEST), 'samples': MANIFEST}
with open(os.path.join(OUT, 'samples.json'), 'w', encoding='utf-8') as f: json.dump(man, f, ensure_ascii=False, indent=1)
print('samples:', len(MANIFEST))
