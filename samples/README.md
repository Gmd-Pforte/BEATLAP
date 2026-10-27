# PS AI MUSIC Sample Pack 1.0

285 Sounds für Beatlab: Drums, Percussion, 808 und Bässe, Instrumente, Akkorde, Stimmen, Effekte und Loops.

- **Format:** WAV, 44,1 kHz, 16 Bit (Mono, Pads/Streicher/Riser teils Stereo)
- **Größe:** ca. 52 MB
- **Rechte:** Alle Sounds wurden per Synthese erzeugt (keine Fremdaufnahmen, keine Sample-CDs). Frei nutzbar für PS AI MUSIC, auch kommerziell.

## Inhalt

| Ordner | Gruppen | Anzahl |
|---|---|---|
| `drums/` | kick (24), snare (18), clap (12), hihat (16), openhat (10), tom (9), rim (6), snap (4), ride (4), crash (4) | 107 |
| `percussion/` | hand (Conga, Bongo, Djembe, Timbale, Tabla), shaker (Shaker, Tamburin, Cabasa), metal (Cowbell, Triangel, Agogo, Glöckchen), wood (Clave, Holzblock, Guiro) | 40 |
| `bass/` | 808 (12, Grundton C1), synth (14, Grundton C2) | 26 |
| `instruments/` | keys, mallets, strings, winds, voices, synth (Grundton C4) | 41 |
| `chords/` | stab, pad, guitar (Moll, Dur, Moll7, Maj7, Sus2, Moll9 auf C) | 19 |
| `fx/` | riser, downlifter, impact, drop, laser, whoosh, scratch, texture, horn, reverse, tone | 37 |
| `loops/` | drums (12 Stile, je 2 Takte), melodic (3, C-Moll, 4 Takte) | 15 |

Zum Anhören: `index.html` im Browser öffnen (über GitHub Pages oder einen Webserver, nicht als lokale Datei).

`tools/gen.py` erzeugt das komplette Pack neu (`python3 tools/gen.py samples`, braucht numpy und scipy). Damit lassen sich auch weitere Sounds ergänzen.

---

## Anleitung für den Einbau in Beatlab (für ChatGPT)

### 1. Dateien ins Repo legen

Den kompletten Ordner als `samples/` ins Repo legen, direkt neben die `index.html` von Beatlab:

```
/index.html            ← Beatlab
/samples/samples.json
/samples/index.html    ← Hörprobe-Seite
/samples/drums/kick/ps-kick-01-kick-boom-bap.wav
/samples/...
/samples/tools/gen.py
```

Die Pfade in `samples.json` sind relativ zum Ordner `samples/` (z. B. `drums/kick/ps-kick-01-kick-boom-bap.wav`). Aus Beatlab lädt man also `samples/` + `file`.

### 2. Aufbau von `samples.json`

```json
{
  "name": "PS AI MUSIC Sample Pack", "version": "1.0", "sampleRate": 44100,
  "categories": { "drums": "Drums", "bass": "Bass", ... },
  "groups": { "kick": "Kicks", "808": "808", ... },
  "samples": [
    {
      "id": "kick-01",
      "name": "Kick Boom Bap",
      "category": "drums",
      "group": "kick",
      "file": "drums/kick/ps-kick-01-kick-boom-bap.wav",
      "type": "oneshot",
      "tracks": ["kick"],
      "root": null, "rootNote": null,
      "bpm": null, "bars": null,
      "duration": 1.68, "channels": 1, "tags": []
    }
  ]
}
```

- `type`: `oneshot` (Drum/FX), `melodic` (hat einen Grundton) oder `loop` (hat `bpm` und `bars`)
- `tracks`: passende Beatlab-Spuren (`kick`, `snare`, `clap`, `hat`, `open`, `rim`, `tom`, `shaker`, `bass`, `chords`, `lead`). Damit kann die Auswahl pro Spur gefiltert werden.
- `root`: MIDI-Note des Grundtons (24 = C1, 36 = C2, 60 = C4). Alle melodischen Samples stehen auf **C**.

### 3. Einbau in Beatlab

Beatlab hat schon alles, was nötig ist: Eigene Samples werden in `samples[trackId]` (AudioBuffer) gehalten und in `play()` statt des eingebauten Sounds gespielt. Die Bibliothek muss nur einen Puffer dort hineinlegen.

**Laden der Liste (einmal beim Start, ohne die WAVs vorzuladen):**

```js
let LIB = null;
async function loadLibrary(){
  try { LIB = await (await fetch('samples/samples.json')).json(); }
  catch(e){ LIB = null; }   // ohne Server/Pages einfach ausblenden
}
```

**Auswahl im Klang-Blatt der Spur** (gefiltert über `tracks`):

```js
function libraryFor(trackId){
  return LIB ? LIB.samples.filter(s => s.tracks.includes(trackId)) : [];
}
```

Gruppiert nach `LIB.groups[s.group]` als `<optgroup>` in einem `<select>`, Option „Eingebauter Sound“ zuerst.

**Ein Sample aus der Bibliothek aktivieren:**

```js
const libCache = {};
async function useLibrarySample(trackId, s){
  ensureAudio();
  if(!libCache[s.id]){
    const bytes = await (await fetch('samples/' + s.file)).arrayBuffer();
    libCache[s.id] = await new Promise((res, rej) => ac.decodeAudioData(bytes, res, rej));
  }
  samples[trackId] = libCache[s.id];
  P.params[trackId].lib = s.id;          // merken, damit es nach dem Neuladen wieder da ist
  P.params[trackId].libRoot = s.root;    // Grundton für melodische Samples
  delete sampleBytes[trackId];           // ist kein hochgeladenes Sample
  save(); renderEditor(); renderPads();
}
```

Beim Start nach `loadLibrary()` für jede Spur mit `P.params[id].lib` das Sample wieder laden. Beim Entfernen `lib` und `libRoot` löschen.

**Tonhöhe richtig umrechnen.** Beatlab nimmt bei eigenen Samples aktuell an, dass sie auf C stehen, und rechnet relativ zu C. Das passt zu diesem Pack. Wer es exakt über `root` machen will:

```js
// gewünschte MIDI-Note → playbackRate
function rateFor(targetMidi, root){ return Math.pow(2, (targetMidi - root) / 12); }
```

Bass-Töne spielt Beatlab um C1 bis C2, Melodie und Akkorde ab C4. Die 808-Samples (C1) und Bass-Samples (C2) passen dadurch ohne Oktav-Korrektur.

**Loops** im Tempo des Projekts abspielen:

```js
src.playbackRate.value = P.bpm / s.bpm;   // Loop passt sich ans Tempo an (Tonhöhe ändert sich mit)
```

### 4. Hinweise

- **Nicht alle WAVs vorladen.** Das Pack hat 52 MB. Nur laden, was ausgewählt wird, und im `libCache` halten.
- **Projektdateien:** Für Bibliotheks-Sounds reicht es, `lib` (die id) zu speichern. Die WAV-Daten müssen nicht ins Projekt, anders als bei hochgeladenen Samples.
- **Export (WAV/Einzelspuren)** funktioniert automatisch, weil der Export ebenfalls `samples[trackId]` nutzt.
- **Lokal geöffnet** (`file://`) blockiert der Browser `fetch`. Zum Testen GitHub Pages oder `python3 -m http.server` verwenden.
- **Namen und ids nicht ändern**, sonst finden gespeicherte Projekte ihre Sounds nicht mehr. Neue Sounds einfach hinten anhängen.
