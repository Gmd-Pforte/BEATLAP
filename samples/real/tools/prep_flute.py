# Bereitet die Flöte aus VSCO 2 Community Edition (CC0, Versilian Studios) für Beatlab auf.
# Aufruf: SRC=Pfad/zum/VSCO-2-CE-Repo python3 prep_flute.py   (braucht ffmpeg mit libmp3lame, numpy)
# VSCO benennt eine Oktave tiefer als üblich: Datei „A3“ klingt als A4 = 440 Hz (gemessen).
import os, re, json, subprocess, numpy as np
SRC = os.environ.get('SRC', 'VSCO-2-CE') + '/Woodwinds/Flute'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'flute')
SR = 44100
NOTE = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
def midi_of(name):  # VSCO-Name → MIDI (Oktave +1)
    m = re.match(r'([A-G])(#?)(\d)', name); return 12 * (int(m.group(3)) + 2) + NOTE[m.group(1)] + (1 if m.group(2) else 0)
NAMES = ['C', 'Cs', 'D', 'Ds', 'E', 'F', 'Fs', 'G', 'Gs', 'A', 'As', 'B']
def sci(midi): return f'{NAMES[midi % 12]}{midi // 12 - 1}'  # Dateiname in üblicher Schreibweise (A4 = 440 Hz)
def load(p):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', p, '-ac', '2', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()
def trim(x):
    a = np.abs(x).max(axis=1); i = int(np.argmax(a > a.max() * 0.02)); return x[max(0, i - int(SR * .002)):]
def fade_out(x, sec):
    n = min(len(x), int(SR * sec)); x[-n:] *= (0.5 * (1 + np.cos(np.linspace(0, np.pi, n))))[:, None]; return x
def f0(x, exp):
    y = x.mean(axis=1); y = y[int(SR * .15):int(SR * 1.2)] if len(y) > SR * 1.3 else y[int(SR * .04):int(SR * .4)]
    y = y * np.hanning(len(y)); n = 1 << 19; X = np.abs(np.fft.rfft(y, n)); f = np.fft.rfftfreq(n, 1 / SR); best = None
    for k in (1, 2, 3):
        lo, hi = np.searchsorted(f, [k * exp * 0.97, k * exp * 1.03])
        if hi > lo:
            i = lo + np.argmax(X[lo:hi])
            if best is None or X[i] > best[0]: best = (X[i], f[i] / k)
    return best[1]
def make_loop(x, start=1.2, end_max=3.4, xf=0.35):
    """Haltebereich mit eingebackener Überblendung: Ende der Schleife geht nahtlos in den Anfang über."""
    win = int(SR * .25)  # Hüllkurve in 250-ms-Fenstern, unempfindlich gegen Vibrato
    env = np.sqrt(np.convolve((x ** 2).mean(axis=1), np.ones(win) / win, 'same'))
    sus = np.median(env[int(SR * .6):int(SR * 3)]); alive = np.where(env > sus * 0.35)[0]
    sus_end = alive[-1] / SR if len(alive) else len(x) / SR
    ls, le = start, min(end_max, sus_end - 0.15); assert le - ls > 1.0, ('Haltebereich zu kurz', le - ls)
    a, b, n = int(SR * ls), int(SR * le), int(SR * xf)
    w = np.sin(np.linspace(0, np.pi / 2, n))[:, None]  # gleiche Leistung
    x[b - n:b] = x[b - n:b] * np.cos(np.linspace(0, np.pi / 2, n))[:, None] + x[a - n:a] * w
    y = x[:b + int(SR * .3)].copy(); fade_out(y, .3)
    return y, ls, le

files = {}
sustain = []
for fn in sorted(os.listdir(f'{SRC}/susvib')):
    m = re.match(r'LDFlute_susvib_([A-G]#?\d)_v1_1\.wav', fn)
    if not m: continue
    x = trim(load(f'{SRC}/susvib/{fn}')); y, ls, le = make_loop(x)
    k = f's-{sci(midi_of(m.group(1)))}'; files[k] = y; sustain.append((midi_of(m.group(1)), k, ls, le))
stac = {}
for fn in sorted(os.listdir(f'{SRC}/stac')):
    m = re.match(r'LDFlute_stac_([A-G]#?\d)_v([123])_rr([12])\.wav', fn)
    if not m: continue
    x = trim(load(f'{SRC}/stac/{fn}'))[:int(SR * .9)].copy(); fade_out(x, .25)
    key = f't-{sci(midi_of(m.group(1)))}-v{m.group(2)}-rr{m.group(3)}'; files[key] = x
    stac.setdefault(m.group(2), []).append((midi_of(m.group(1)), key, int(m.group(3))))

peak = max(np.abs(v).max() for v in files.values()); g = 10 ** (-1 / 20) / peak
for key, x in files.items():
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '2', '-i', '-', '-c:a', 'libmp3lame', '-b:a', '128k', f'{OUT}/{key.replace("#", "s")}.mp3'],
                   input=np.clip(x * g, -1, 1).astype(np.float32).tobytes(), check=True)
def tune(key, midi):
    exp = 440 * 2 ** ((midi - 69) / 12); return -round(1200 * np.log2(f0(files[key], exp) / exp))
man = {'format': 'beatlab-sampler-2', 'id': 'fluteReal', 'name': 'Flöte (echt)',
       'source': 'VS Chamber Orchestra 2 Community Edition, Woodwinds/Flute – https://github.com/sgossner/VSCO-2-CE',
       'author': 'Versilian Studios (Sam Gossner, Simon Dalzell)', 'license': 'CC0 1.0', 'licenseUrl': 'https://creativecommons.org/publicdomain/zero/1.0/',
       'attribution': 'Flöte aus VSCO 2 Community Edition (Versilian Studios), CC0',
       'changes': 'Sustain mit Vibrato (10 Töne C4–C7) mit Haltebereich und eingebackener Überblendung; Staccato in 3 Dynamikstufen × 2 Varianten (A4–C7); Anfang beschnitten, ausgeblendet, gemeinsam auf -1 dBFS normalisiert, MP3 128 kbit/s; Stimmung gemessen und korrigiert; Lautstärkeunterschied zwischen tiefen und hohen Tönen zur Hälfte ausgeglichen (gainDb)',
       'release': 0.18, 'gainDb': 3.0, 'shortSkip': 0.1, 'articulations': []}
# Tiefe Flötentöne sind von Natur aus viel leiser (bis ~18 dB). Für den Mix die Hälfte davon ausgleichen.
def rms_db(x): return 20 * np.log10(np.sqrt(np.mean(x[int(SR * .4):int(SR * 1.2)] ** 2)) + 1e-9)
lvl = {m: rms_db(files[k]) for m, k, _, _ in sustain}; mid = float(np.median(list(lvl.values())))
def comp(midi):
    near = min(lvl, key=lambda r: abs(r - midi)); return round(float(np.clip(0.5 * (mid - lvl[near]), -6, 6)), 1)
man['articulations'].append({'name': 'sustain', 'layers': [{'name': 'vib', 'velMax': 99, 'notes': [
    {'midi': m, 'tune': tune(k, m), 'gainDb': comp(m), 'file': k.replace('#', 's') + '.mp3', 'loopStart': round(ls, 4), 'loopEnd': round(le, 4)} for m, k, ls, le in sorted(sustain)]}]})
lay = []
for v, vmax in (('1', 0.5), ('2', 0.85), ('3', 99)):
    lay.append({'name': 'v' + v, 'velMax': vmax, 'notes': [{'midi': m, 'tune': tune(k, m), 'gainDb': comp(m), 'file': k.replace('#', 's') + '.mp3', 'rr': rr} for m, k, rr in sorted(stac[v])]})
man['articulations'].append({'name': 'staccato', 'maxDur': 0.22, 'minMidi': min(n['midi'] for n in lay[0]['notes']) - 1, 'layers': lay})
json.dump(man, open(f'{OUT}/manifest.json', 'w'), ensure_ascii=False, indent=1)
print('Dateien', len(files), 'Peak', round(float(peak), 3))
for a in man['articulations']:
    for l in a['layers']: print(a['name'], l['name'], [(n['midi'], n['tune'], n['gainDb']) for n in l['notes']])
