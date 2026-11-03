import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
import vm from 'node:vm';

const html=readFileSync(new URL('../index.html',import.meta.url),'utf8');
const generator=readFileSync(new URL('../sound-generator.html',import.meta.url),'utf8');
assert.equal(html,generator,'The published entry page must match the Melody Studio.');
assert.ok(html.length>20000,'Melody Studio appears incomplete');
assert.match(html,/<title>Beatlap Sound Generator<\/title>/);
const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);
assert.equal(ids.length,new Set(ids).size,'Duplicate element IDs');
for(const id of ['play','melodyOnly','generate','wav','melodyWav','export','mood','pattern','variation','density','register','sections','graph','beatstyle','bass','drums']){
  assert.ok(html.includes('id="'+id+'"'),'Missing control: '+id);
}
const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
assert.equal(scripts.length,2,'Expected two inline scripts');
scripts.forEach(code=>new vm.Script(code));
assert.match(html,/OfflineAudioContext/);
assert.match(html,/audio\/wav/);
assert.match(html,/PS-Beatlap-Score-1/);
const engine=readFileSync(new URL('../instrument-engine.js',import.meta.url),'utf8');
new vm.Script(engine);
const defaults={wave:'triangle',attack:'.04',release:'.5',cutoff:'2600',detune:'7',volume:'.35',root:'4',mode:'minor',bpm:'125',pattern:'singing',mood:'melancholy',density:'balanced',register:'mid',variation:'70',length:'short',beatstyle:'house',drums:'full',bass:'on'};
const els=new Map();
function element(id){return {value:defaults[id]??'',dataset:{},textContent:'',style:{setProperty(){}},classList:{toggle(){}},replaceChildren(){},append(){},addEventListener(){},querySelectorAll(){return []}}}
const document={getElementById(id){if(!els.has(id))els.set(id,element(id));return els.get(id)},createElement(){return element('dynamic')}};
const injected=scripts[1].replace(/drawPlan\(\);\s*\}\)\(\);\s*$/,'drawPlan();globalThis.__tests={makeSong,setSeed:n=>seed=n};})();');
assert.notEqual(injected,scripts[1],'Test hook injection failed');
const sandbox={document,window:{},console,setInterval,clearInterval,setTimeout,clearTimeout,Math,Blob,URL,alert(){},localStorage:{getItem(){return null},setItem(){}}};
vm.runInNewContext(injected,sandbox,{timeout:3000});
const {makeSong,setSeed}=sandbox.__tests;
let signatures=new Set();
for(const mood of ['grief','melancholy','nostalgia','hope','dream','mystery','happy','euphoria','groove','epic']){
  document.getElementById('mood').value=mood;
  const song=makeSong(),mel= song.events.filter(e=>e.track==='Melodie');
  assert.ok(mel.length>50,'Too few notes: '+mood);
  assert.ok(song.events.every(e=>Number.isFinite(e.beat)&&Number.isFinite(e.duration)&&e.beat>=0&&e.beat<song.totalBeats),'Invalid note event');
  signatures.add(mel.slice(0,30).map(e=>e.pitch+':'+e.beat).join(','));
}
assert.ok(signatures.size>=8,'Mood choices should produce distinct melodies');
document.getElementById('mood').value='melancholy';signatures.clear();
for(const pattern of ['singing','gentle','drive','rising','broken','leaping','arpeggio','minimal','syncopated','cinematic','longing','question','waltz','heartbeat','folk','anthem','jazzy','ostinato','flutter','tender','dramatic','call']){
  document.getElementById('pattern').value=pattern;
  signatures.add(makeSong().events.filter(e=>e.track==='Melodie').slice(0,30).map(e=>e.pitch+':'+e.beat).join(','));
}
assert.ok(signatures.size>=18,'Expanded melody patterns should differ');
document.getElementById('pattern').value='singing';
setSeed(110);const first=makeSong().events.filter(e=>e.track==='Melodie').slice(0,50).map(e=>e.pitch).join(',');
setSeed(8201);const next=makeSong().events.filter(e=>e.track==='Melodie').slice(0,50).map(e=>e.pitch).join(',');
assert.notEqual(first,next,'Regeneration should change the melody');
for(const length of ['short','full','long']){
 document.getElementById('length').value=length;
 const song=makeSong();
 assert.ok(song.sections.length>=6);
 assert.ok(song.sections.some(s=>s.name.includes('Refrain')));
 assert.ok(song.events.some(e=>e.track==='Kick'));
 assert.ok(song.events.some(e=>e.track==='Bass'));
}
for(const id of ['findMelodies','showFavorites','batchCount','batchMix','melodyResults','finderInfo'])assert.ok(html.includes('id="'+id+'"'),'Missing Melody Finder '+id);
for(const n of ['8','16','32','64'])assert.match(html,new RegExp('option value="'+n+'"'));
assert.match(html,/function findMelodies\(/);
assert.match(html,/localStorage\.setItem\('beatlap-melody-favorites-v1'/);
console.log('✓ Beatlap Melody Studio checks passed: 22 melody styles, batch finder, favorites, moods and song generation');
