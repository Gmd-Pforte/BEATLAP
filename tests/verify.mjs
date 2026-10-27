import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const checks = [];

function test(name, fn) {
  fn();
  checks.push(name);
}

test('HTML entry file exists and has content', () => {
  assert.ok(html.length > 10000, 'index.html appears incomplete');
  assert.match(html, /<title>Beatlab 4<\/title>/i);
});

const scripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)]
  .map(match => match[1])
  .filter(Boolean);

test('Inline JavaScript parses', () => {
  assert.ok(scripts.length, 'No inline JavaScript found');
  for (const source of scripts) new Function(source);
});

test('HTML element IDs are unique', () => {
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
  assert.equal(ids.length, new Set(ids).size, 'Duplicate element ID found');
});

test('Core studio controls exist', () => {
  for (const id of [
    'playBtn', 'matrix', 'roll', 'pats', 'arranger',
    'songMode', 'mixer', 'ideaBtn', 'composerInfo',
    'exportBtn', 'projectSave', 'projectFile'
  ]) {
    assert.ok(html.includes(`id="${id}"`), `Missing required UI control: ${id}`);
  }
});

test('Audio export and project support are present', () => {
  assert.match(html, /OfflineAudioContext/);
  assert.match(html, /audio\/wav/);
  assert.match(html, /decodeAudioData/);
  assert.match(html, /PS-Beatlab-2/);
});


const instrumentEngine = readFileSync(new URL('../instrument-engine.js', import.meta.url), 'utf8');
test('Procedural instrument engine parses and is loaded by Beatlab', () => {
  new Function(instrumentEngine);
  assert.match(html, /src="\.\/instrument-engine\.js"/);
  assert.match(html, /PSInstrumentEngine\.play/);
  for (const id of ['grand', 'felt', 'upright', 'cello', 'violin', 'acoustic', 'nylon', 'sax', 'tenorSax', 'trumpet']) {
    assert.ok(html.includes(id + ':['), 'Missing instrument menu item: ' + id);
    assert.ok(instrumentEngine.includes(id + ':{'), 'Missing synthesis model: ' + id);
  }
});


test('Composer 2.0 offers distinct song structures and safe lengths', () => {
  for (const id of ['ideaLength', 'ideaMelodyBtn', 'ideaBackingBtn']) {
    assert.ok(html.includes('id="'+id+'"'), 'Missing Composer 2.0 control '+id);
  }
  const start=html.indexOf('const COMPOSER_FORMS=');
  const end=html.indexOf('function generateComposition(',start);
  assert.ok(start>0&&end>start,'Composer song forms are missing');
  const forms=new Function(html.slice(start,end)+';return {COMPOSER_FORMS,composerArrangement};')();
  for (const bars of [16,32,48,64]) {
    const arrangement=forms.composerArrangement(bars);
    assert.equal(arrangement.reduce((sum,s)=>sum+s.bars,0),bars,'Wrong total bars '+bars);
    assert.ok(arrangement.some(s=>s.name==='Intro'),'Intro missing');
    assert.ok(arrangement.some(s=>s.name.includes('Refrain')),'Refrain missing');
    assert.ok(arrangement.every(s=>s.pat>=0&&s.pat<=3),'Invalid pattern');
  }
  assert.match(html,/generateComposition\(false,'melody'\)/);
  assert.match(html,/generateComposition\(false,'backing'\)/);
});

console.log(`✓ Beatlab checks passed (${checks.length} groups)`);
for (const item of checks) console.log(`  ✓ ${item}`);
