# Nachweise für echte Instrumenten-Samples

## Flügel (echt) – `samples/real/piano/`

- **Werk:** Salamander Grand Piano V3 (Yamaha C5)
- **Urheber:** Alexander Holm
- **Quelle:** https://github.com/sfzinstruments/SalamanderGrandPiano (SFZ-Fassung von kinwie, Original: https://archive.org/details/SalamanderGrandPianoV3)
- **Lizenz:** Creative Commons Namensnennung 3.0 Unported (CC BY 3.0) – https://creativecommons.org/licenses/by/3.0/
- **Änderungen für Beatlab:**
  - Auswahl: 20 Grundtöne A1–F#6 (kleine Terzen), 3 von 16 Dynamikstufen (v4 = leise, v9 = mittel, v14 = laut)
  - Stille am Anfang entfernt, auf 3,5 s gekürzt, letzte 1,2 s ausgeblendet
  - Gemeinsam normalisiert auf −1 dBFS, umgerechnet auf 44,1 kHz Stereo, kodiert als MP3 128 kbit/s
  - Stimmung je Grundton gemessen und beim Abspielen auf gleichstufig korrigiert (`manifest.json` → `tune`, in Cent)
- Die bearbeiteten Dateien stehen unter derselben Lizenz (CC BY 3.0). Der Urheber unterstützt diese Bearbeitung nicht ausdrücklich.

Die Namensnennung erscheint auch in Beatlab unter **Datei → Sample-Nachweise**.

Das Skript zur Aufbereitung liegt in `samples/real/tools/prep_piano.py`.

## Flöte (echt) – `samples/real/flute/`

- **Werk:** VS Chamber Orchestra 2 Community Edition (VSCO 2 CE), Woodwinds/Flute
- **Urheber:** Versilian Studios (Aufnahme Sam Gossner & Simon Dalzell, Schnitt Elan Hickler/Soundemote)
- **Quelle:** https://github.com/sgossner/VSCO-2-CE
- **Lizenz:** CC0 1.0 (Public Domain Dedication) – https://creativecommons.org/publicdomain/zero/1.0/ – keine Namensnennung nötig, wir nennen die Quelle trotzdem.
- **Änderungen für Beatlab:**
  - Sustain mit Vibrato: 10 Töne C4–C7, Haltebereich 1,2–3,4 s mit eingebackener Überblendung (0,35 s), danach 0,3 s Ausklang
  - Staccato: 3 Dynamikstufen × 2 Varianten (Round-Robin), A4–C7, auf 0,9 s gekürzt
  - VSCO benennt eine Oktave tiefer (Datei „A3“ = 440 Hz), Dateinamen hier in üblicher Schreibweise
  - Anfang beschnitten, gemeinsam auf −1 dBFS normalisiert, 44,1 kHz Stereo, MP3 128 kbit/s, Stimmung je Datei gemessen und korrigiert
  - Tiefe Töne sind bei der Flöte von Natur aus deutlich leiser; die Hälfte des Unterschieds wird beim Abspielen ausgeglichen (`gainDb`)

Skript: `samples/real/tools/prep_flute.py`.
