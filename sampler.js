/* PS Beatlab Sampler 2.0 (Claude) – Beatlab Real Instruments
 * Spielt echte, mehrschichtige Instrumenten-Samples. Welche es gibt, steht in samples/real/index.js.
 * - Lädt erst bei Bedarf (lazy); AudioBuffer werden einmal dekodiert und für Live-Wiedergabe
 *   UND Offline-WAV-Export geteilt (AudioBuffer sind nicht an einen AudioContext gebunden).
 * - Spielweisen (z. B. sustain/staccato) nach Notenlänge, Dynamikstufe nach Lautstärke,
 *   Varianten (Round-Robin) im Wechsel, nächster Grundton wird gepitcht.
 * - Gehaltene Instrumente: Haltebereich (loopStart/loopEnd) mit eingebackener Überblendung.
 * - Ist ein Instrument (noch) nicht geladen, gibt play() false zurück → Beatlab nutzt den Ersatzklang.
 * Manifest-Formate: beatlab-sampler-1 (nur layers) und beatlab-sampler-2 (articulations).
 */
(function (root) {
  'use strict';

  const BASE = './samples/real/';
  const REGISTRY = {};
  for (const r of (root.PSRealInstruments || [])) REGISTRY[r.id] = r;

  const state = {};   // id → { status: 'idle'|'loading'|'ready'|'error', manifest, articulations, promise, error }

  function decoderContext() {
    const C = root.OfflineAudioContext || root.webkitOfflineAudioContext;
    return new C(2, 1, 44100);
  }

  // MP3-Encoder setzen etwas Stille vor den Ton. Wir suchen den echten Anschlag beim Laden.
  // Haltebereiche sind relativ zum Anschlag angegeben und verschieben sich mit.
  function onsetOf(buf) {
    const d = buf.getChannelData(0), n = Math.min(d.length, Math.floor(buf.sampleRate * 0.15));
    let peak = 0;
    for (let i = 0; i < d.length; i++) { const a = Math.abs(d[i]); if (a > peak) peak = a; }
    const th = Math.max(0.0005, peak * 0.02);
    for (let i = 0; i < n; i++) if (Math.abs(d[i]) > th) return Math.max(0, i - Math.floor(buf.sampleRate * 0.002)) / buf.sampleRate;
    return 0;
  }

  async function fetchBuffer(dec, url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error('Sample fehlt: ' + url + ' (HTTP ' + res.status + ')');
    const ab = await res.arrayBuffer();
    return await new Promise((ok, fail) => {
      const p = dec.decodeAudioData(ab, ok, fail);
      if (p && p.then) p.then(ok, fail);
    });
  }

  function articulationsOf(manifest) {
    if (manifest.format === 'beatlab-sampler-1') return [{ name: 'sustain', layers: manifest.layers }];
    if (manifest.format === 'beatlab-sampler-2') return manifest.articulations;
    throw new Error('Unbekanntes Sampler-Format: ' + manifest.format);
  }

  async function loadInstrument(id) {
    const dir = BASE + REGISTRY[id].dir + '/';
    const res = await fetch(dir + 'manifest.json');
    if (!res.ok) throw new Error('Manifest fehlt (HTTP ' + res.status + ')');
    const manifest = await res.json();
    const dec = decoderContext();
    const arts = [];
    for (const art of articulationsOf(manifest)) {
      const layers = [];
      // Mittlere Stufe zuerst, damit früh etwas spielbar ist; max. 6 Downloads gleichzeitig
      const order = [...art.layers].sort((a, b) => (/^(mf|v2)$/.test(a.name) ? -1 : /^(mf|v2)$/.test(b.name) ? 1 : 0));
      for (const layer of order) {
        const notes = [], queue = layer.notes.map(n => async () => {
          const buffer = await fetchBuffer(dec, dir + encodeURIComponent(n.file));
          notes.push({ midi: n.midi, tune: n.tune || 0, gain: Math.pow(10, (n.gainDb || 0) / 20), rr: n.rr || 1, buffer, offset: onsetOf(buffer),
                       loopStart: n.loopStart, loopEnd: n.loopEnd });
        });
        await Promise.all(Array.from({ length: 6 }, async () => { while (queue.length) await queue.shift()(); }));
        notes.sort((a, b) => a.midi - b.midi || a.rr - b.rr);
        layers.push({ name: layer.name, velMax: layer.velMax, notes });
      }
      layers.sort((a, b) => a.velMax - b.velMax);
      arts.push({ name: art.name, maxDur: art.maxDur, minMidi: art.minMidi, maxMidi: art.maxMidi, layers });
    }
    return { manifest, articulations: arts };
  }

  function load(id) {
    if (!REGISTRY[id]) return Promise.reject(new Error('Kein Sampler-Instrument: ' + id));
    const s = state[id] || (state[id] = { status: 'idle' });
    if (s.status === 'ready') return Promise.resolve(s);
    if (s.status === 'loading') return s.promise;
    s.status = 'loading';
    s.promise = loadInstrument(id).then(r => {
      Object.assign(s, r, { status: 'ready', error: null });
      try { root.dispatchEvent(new CustomEvent('ps-sampler', { detail: { id, status: 'ready' } })); } catch (e) {}
      return s;
    }, err => {
      s.status = 'error'; s.error = err;
      try { root.dispatchEvent(new CustomEvent('ps-sampler', { detail: { id, status: 'error', error: err } })); } catch (e) {}
      throw err;
    });
    return s.promise;
  }

  // Spielweise: kurze Noten → staccato (wenn vorhanden und im Tonumfang), sonst sustain
  function pickArticulation(arts, midi, dur) {
    const fits = a => (a.minMidi == null || midi >= a.minMidi) && (a.maxMidi == null || midi <= a.maxMidi);
    const short = arts.find(a => a.maxDur != null && dur <= a.maxDur && fits(a));
    return short || arts.find(a => a.maxDur == null) || arts[0];
  }

  // Nächster Grundton; bei mehreren Varianten (rr) im Wechsel – deterministisch, damit Live = Export
  function pickNote(id, art, layer, midi, t) {
    let best = null;
    for (const n of layer.notes) if (!best || Math.abs(n.midi - midi) < Math.abs(best.midi - midi)) best = n;
    const variants = layer.notes.filter(n => n.midi === best.midi);
    if (variants.length < 2) return best;
    return variants[Math.floor(t * 1000) % variants.length];   // abhängig vom Zeitpunkt, nicht vom Zufall
  }

  /* v: Beatlab-Lautstärke (typisch 0,1–0,45). Wird auf 0–1 normiert für die Dynamikstufe. */
  function play(ctx, out, id, freq, t, dur, v) {
    const s = state[id];
    if (!s || s.status !== 'ready') { if (!s || s.status === 'idle') load(id).catch(() => {}); return false; }
    const midi = 69 + 12 * Math.log2(freq / 440);
    const vel = Math.max(0, Math.min(1.2, v / 0.3));
    const art = pickArticulation(s.articulations, midi, dur);
    const layer = art.layers.find(l => vel <= l.velMax) || art.layers[art.layers.length - 1];
    const n = pickNote(id, art, layer, midi, t);
    const src = ctx.createBufferSource();
    src.buffer = n.buffer;
    src.detune.value = (midi - n.midi) * 100 + n.tune;          // tune: gemessene Korrektur in Cent
    const rate = Math.pow(2, src.detune.value / 1200);
    const g = ctx.createGain();
    const level = Math.min(0.8, v * 1.25) * n.gain * Math.pow(10, (s.manifest.gainDb || 0) / 20);
    const rel = s.manifest.release || 0.35;
    const hold = Math.max(dur, 0.05);
    let end;
    const canLoop = n.loopStart != null && n.loopEnd != null;
    if (canLoop && hold + rel > (n.loopEnd / rate)) {
      // Länger als das Sample: im Haltebereich schleifen (Überblendung ist eingebacken)
      src.loop = true;
      src.loopStart = n.offset + n.loopStart;
      src.loopEnd = n.offset + n.loopEnd;
      end = t + hold + rel;
    } else {
      const natural = (n.buffer.duration - n.offset) / rate;    // Ende des Samples (mit Ausblendung)
      end = Math.min(t + hold + rel, t + natural);
    }
    // Kurze Note auf einem gehaltenen Sample (z. B. tiefe Flöte ohne Staccato-Aufnahme):
    // langsamen Einschwung überspringen und kurz einblenden, sonst wäre der Ton fast unhörbar.
    let startAt = n.offset;
    const skip = s.manifest.shortSkip || 0;
    if (skip && art.maxDur == null && hold < 0.25) startAt += skip;
    g.gain.setValueAtTime(startAt > n.offset ? 0.0001 : level, t);
    if (startAt > n.offset) g.gain.linearRampToValueAtTime(level, t + 0.008);
    g.gain.setValueAtTime(level, Math.max(t + 0.008, end - rel));
    g.gain.setTargetAtTime(0.0001, Math.max(t, end - rel), rel / 4);   // weich abklingen
    src.connect(g); g.connect(out);
    src.start(t, startAt);
    src.stop(end + 0.05);
    return true;
  }

  root.PSSampler = {
    instruments: () => Object.values(REGISTRY),
    supports: id => !!REGISTRY[id],
    fallback: id => (REGISTRY[id] && REGISTRY[id].fallback) || 'piano',
    info: id => REGISTRY[id],
    status: id => (state[id] && state[id].status) || 'idle',
    error: id => state[id] && state[id].error,
    manifest: id => state[id] && state[id].manifest,
    load,
    ensure: async ids => {
      const wanted = [...new Set(ids)].filter(id => REGISTRY[id]);
      const results = await Promise.allSettled(wanted.map(load));
      return wanted.filter((id, i) => results[i].status === 'rejected');   // fehlgeschlagene IDs
    },
    play
  };
})(window);
