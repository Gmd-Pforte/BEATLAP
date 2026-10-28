/* Beatlab Real Instruments – Verzeichnis aller echten Instrumente.
 * Neues Instrument = Ordner samples/real/<dir>/ mit manifest.json + Samples und EIN Eintrag hier.
 * Wird vor Beatlab geladen (normales <script>), damit Menü, Projektprüfung und Sampler es sofort kennen.
 *   id        Beatlab-Sound-ID (bleibt im Projekt gespeichert, nie ändern)
 *   label     Name im Menü
 *   fallback  Ersatzklang, solange die Samples nicht geladen sind oder fehlen (nie Stille)
 *   sizeMB    ungefähre Downloadgröße (für den Ladehinweis)
 */
window.PSRealInstruments = [
  { id: 'grandReal', dir: 'piano', label: 'Flügel (echt) · Salamander', fallback: 'grand', sizeMB: 3.3,
    credit: { work: 'Salamander Grand Piano V3', author: 'Alexander Holm', license: 'CC BY 3.0',
              url: 'https://github.com/sfzinstruments/SalamanderGrandPiano', licenseUrl: 'https://creativecommons.org/licenses/by/3.0/', required: true } },
  { id: 'fluteReal', dir: 'flute', label: 'Flöte (echt) · VSCO', fallback: 'flute', sizeMB: 1.3,
    credit: { work: 'VS Chamber Orchestra 2 Community Edition – Flöte', author: 'Versilian Studios', license: 'CC0 1.0',
              url: 'https://github.com/sgossner/VSCO-2-CE', licenseUrl: 'https://creativecommons.org/publicdomain/zero/1.0/', required: false } }
];
