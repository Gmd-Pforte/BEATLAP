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
