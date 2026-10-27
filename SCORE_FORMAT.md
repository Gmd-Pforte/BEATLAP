# Beatlap Notensong-Format 1.0

Ab Beatlap 4 können vollständige, mehrspurige Notenkompositionen im Reiter **Datei → Song aus Noten importieren** geladen werden. Die bisherige Beat-/Pattern-Ansicht bleibt erhalten.

## Unterstützte Formate

- **JSON** mit dem Kennzeichen `"format": "PS-Beatlap-Score-1"`
- **TXT** mit Titel, BPM, TRACK-Blöcken und einzelnen Notenzeilen

MIDI und MusicXML sind für einen späteren Ausbau vorgesehen und werden in dieser Version noch nicht unterstützt.

## Beispiel JSON

```json
{
  "format": "PS-Beatlap-Score-1",
  "title": "Mein erster Song",
  "bpm": 76,
  "beatsPerBar": 4,
  "sections": [
    {"name": "Intro", "start": 0},
    {"name": "Strophe", "start": 16}
  ],
  "tracks": [
    {
      "name": "Klavier",
      "instrument": "piano",
      "volume": 0.8,
      "pan": 0,
      "notes": [
        {"pitch": "A3", "start": 0, "duration": 2, "velocity": 0.8},
        {"pitch": "C4", "start": 2, "duration": 1, "velocity": 0.75},
        {"pitch": "E4", "start": 3, "duration": 1, "velocity": 0.75}
      ]
    },
    {
      "name": "Cello",
      "instrument": "cello",
      "volume": 0.7,
      "notes": [
        {"pitch": "A2", "start": 0, "duration": 4, "velocity": 0.6}
      ]
    }
  ]
}
```

Jeder **Start** und jede **Dauer** wird in Viertelschlägen angegeben: `start: 0` beginnt beim ersten Schlag, `start: 4` im zweiten Takt. `duration: 0.5` ist eine Achtelnote, `duration: 1` eine Viertelnote und `duration: 4` eine ganze Note. `velocity` und `volume` liegen jeweils zwischen 0 und 1. `pitch` ist etwa `C4`, `F#4`, `Bb3` oder eine MIDI-Notennummer von 24 bis 108.

## Beispiel TXT

```text
TITLE: Mein erster Song
BPM: 76
TRACK: Piano|piano
A3 0 2 0.8
C4 2 1 0.75
E4 3 1 0.75

TRACK: Cello|cello
A2 0 4 0.6
```

## Instrumenten-IDs

Alle Schlüssel aus den vorhandenen Beatlap-Instrumentenlisten können verwendet werden, etwa `piano`, `grand`, `felt`, `upright`, `epiano`, `organ`, `guitar`, `acoustic`, `nylon`, `cello`, `violin`, `strings`, `flute`, `sax`, `trumpet`, `marimba`, `kalimba`, `vibes`, `music`, `sub`, `808`, `kickBoom` oder `snare`.

## Grenzen und Export

- 4/4-Takt; Tempo 40–200 BPM
- Bis zu 16 Spuren und 6000 Noten pro Datei
- Maximal 256 Viertelschläge bzw. 64 Takte
- Live-Abspielen sowie WAV-Mix und ZIP-Einzelspuren aus dem importierten Notensong
- Die Notenkomposition wird beim Speichern des Beatlap-Projekts mitgesichert

Die Songdatei ersetzt nicht die bisherigen Patterns. Über **Zurück zu Beats** kann jederzeit umgeschaltet werden. Längere Exporte benötigen insbesondere auf Android Zeit und Speicher.
