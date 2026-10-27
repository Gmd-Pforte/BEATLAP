/* PS AI MUSIC Real Instrument Engine 1.0 – procedural audio, no downloaded samples.
 * Keep drum synthesis and user-uploaded samples in Beatlab unchanged.
 * Each AudioContext (including OfflineAudioContext for WAV export) gets its own buffers. */
(function(global){
'use strict';
const SPECS={
 piano:{kind:'piano',soft:.4,decay:1.18,partial:9},
 epiano:{kind:'tine',soft:.56,decay:.98,partial:8},
 clav:{kind:'pluck',soft:.16,decay:1.55,partial:12},
 music:{kind:'mallet',soft:.24,decay:.62,partial:8},
 grand:{kind:'piano',soft:.18,decay:1.00,partial:11},
 felt:{kind:'piano',soft:.85,decay:1.24,partial:7},
 upright:{kind:'piano',soft:.58,decay:1.35,partial:9},
 guitar:{kind:'pluck',soft:.28,decay:1.12,partial:9},
 acoustic:{kind:'pluck',soft:.28,decay:1.12,partial:9},
 nylon:{kind:'pluck',soft:.73,decay:1.22,partial:7},
 harp:{kind:'pluck',soft:.46,decay:.82,partial:10},
 cello:{kind:'bow',soft:.68,decay:1.1,partial:8,attack:.16},
 violin:{kind:'bow',soft:.28,decay:1.0,partial:10,attack:.10},
 strings:{kind:'ensemble',soft:.48,decay:1.0,partial:9,attack:.26},
 flute:{kind:'wind',soft:.86,decay:1,partial:5,attack:.075},
 sax:{kind:'reed',soft:.30,decay:1,partial:9,attack:.075},
 tenorSax:{kind:'reed',soft:.45,decay:1,partial:8,attack:.09},
 trumpet:{kind:'brass',soft:.28,decay:1,partial:9,attack:.07},
 brass:{kind:'brass',soft:.42,decay:1,partial:9,attack:.075},
 bell:{kind:'mallet',soft:.14,decay:.68,partial:8},
 marimba:{kind:'mallet',soft:.60,decay:1.3,partial:6},
 kalimba:{kind:'mallet',soft:.76,decay:.95,partial:7},
 vibes:{kind:'mallet',soft:.46,decay:.50,partial:8}
};
const buffers=new WeakMap();
function random(seed){let s=seed>>>0;return()=>{s=(Math.imul(s,1664525)+1013904223)>>>0;return s/4294967296;};}
function getBuf(ctx,id,f){
 let cache=buffers.get(ctx);if(!cache){cache=new Map();buffers.set(ctx,cache);}
 const key=id+':'+Math.round(f*20);if(cache.has(key))return cache.get(key);
 const spec=SPECS[id],sr=22050,duration=spec.kind==='piano'?4.0:spec.kind==='pluck'?3.2:spec.kind==='mallet'?3.6:4;
 const length=Math.floor(sr*duration),buffer=ctx.createBuffer(1,length,sr),data=buffer.getChannelData(0);
 const rand=random((Math.round(f*10)*8171+id.length*91753)>>>0);
 const isPiano=spec.kind==='piano',isPluck=spec.kind==='pluck',isMallet=spec.kind==='mallet',isTine=spec.kind==='tine';
 const copies=isPiano?3:isPluck?2:spec.kind==='ensemble'?3:1;
 const modes=[],b=isPiano?.00016:.000038;
 for(let string=0;string<copies;string++){
  const cents=isPiano?[-.75,0,.68][string]:isPluck?[-.3,.35][string]:[-4,0,4][string];
  for(let h=1;h<=spec.partial;h++){
   let multiplier=h;
   if(isMallet) {
    // Metal bars, wooden bars, tines and music boxes have different modal frequencies.
    const ratios=id==='bell'?[1,2.1,3.95,5.45,7.8,10.5,13.2,16]:
      id==='marimba'?[1,3.93,9.2,15.1,20,25,29,34]:
      id==='kalimba'?[1,2.85,5.35,8.8,12.1,16.3,19.1,22.3]:
      id==='music'?[1,2.02,3.87,5.9,7.8,10.3,12.5,15.1]:
      [1,2,4.05,6.1,8.2,10.4,12.5,14.8];
    multiplier=ratios[h-1];
   } else if(isTine) multiplier=h===1?1:h===2?2.01:h*1.008;
   const hz=f*multiplier*Math.sqrt(1+b*h*h)*Math.pow(2,cents/1200);
   if(hz>sr*.46)continue;
   const weight=Math.pow(h,-(isMallet?1.55:isTine?1.62:1.25+spec.soft*.7))/copies;
   const brightness=id==='marimba'&&h>3?.28:id==='kalimba'&&h>4?.36:id==='clav'&&h>7?.62:1;
   const dec=spec.decay*(isPiano?.53:isPluck?.8:isMallet?.58:isTine?.42:.12)*(1+.12*h*h);
   const omega=2*Math.PI*hz/sr;
   const phase=rand()*6.28;
   modes.push({sin:Math.sin(phase),cos:Math.cos(phase),ss:Math.sin(omega),cc:Math.cos(omega),amp:weight*brightness,factor:Math.exp(-dec/sr)});
  }
 }
 let noise=0;
 for(let i=0;i<length;i++){
  const t=i/sr;let sum=0;
  for(const m of modes){
   const sin=m.sin*m.cc+m.cos*m.ss;
   m.cos=m.cos*m.cc-m.sin*m.ss;m.sin=sin;
   sum+=sin*m.amp;m.amp*=m.factor;
  }
  noise=noise*.67+(rand()*2-1)*.33;
  const attack=1-Math.exp(-t*(isPiano?1200:isPluck?900:isMallet?1100:isTine?800:35));
  const click=(isPiano?.10:isPluck?.14:isMallet?.18:isTine?.12:.015)*(1-spec.soft)*noise*Math.exp(-t*(isPiano?70:85));
  const body=isPiano?Math.sin(2*Math.PI*137*t)*Math.exp(-t*7)*.006:0;
  const keyRelease=id==='clav'?Math.exp(-t*.85):1;
  const breath=['flute','sax','tenorSax','trumpet','brass'].includes(id)?noise*.006*(1-Math.exp(-t*15)):0;
  const bow=id==='cello'||id==='violin'||id==='strings'?noise*.004*(1-Math.exp(-t*18)):0;
  data[i]=Math.tanh((sum*.25*keyRelease+click+body+breath+bow)*attack*1.3);
 }
 if(cache.size>=96)cache.delete(cache.keys().next().value);
 cache.set(key,buffer);
 return buffer;
}
function play(ctx,out,id,f,t,dur,vol){
 const spec=SPECS[id];if(!spec||!Number.isFinite(f)||f<=0)return false;
 const src=ctx.createBufferSource();src.buffer=getBuf(ctx,id,f);
 const amp=ctx.createGain();
 const filter=ctx.createBiquadFilter();filter.type='lowpass';
 const bright=spec.kind==='piano'?5400:spec.kind==='pluck'?4200:spec.kind==='tine'?4900:spec.kind==='mallet'?(id==='marimba'?3000:id==='kalimba'?4900:6100):spec.kind==='reed'?3700:4300;
 filter.frequency.setValueAtTime(Math.min(9000,bright*(1.1-spec.soft*.3)),t);
 if(['piano','pluck','mallet','tine'].includes(spec.kind))
  filter.frequency.exponentialRampToValueAtTime(Math.max(700,bright*.47),t+.65);
 src.connect(filter);filter.connect(amp);amp.connect(out);
 const isSustain=['bow','ensemble','wind','reed','brass'].includes(spec.kind);
 const release=isSustain?.35:spec.kind==='piano'?.85:spec.kind==='tine'?.65:.5;
 const end=t+Math.max(.09,dur);
 const peak=Math.max(.0001,vol)*(spec.kind==='ensemble'?.65:1.0);
 amp.gain.setValueAtTime(.0001,t);
 amp.gain.linearRampToValueAtTime(peak,t+(isSustain?spec.attack:.005));
 if(isSustain){
  amp.gain.setTargetAtTime(peak*.8,t+spec.attack,.19);
  amp.gain.setValueAtTime(peak*.72,end);
 }else{
  amp.gain.setTargetAtTime(peak*.25,t+.025,spec.kind==='piano'?.75:.35);
  amp.gain.setValueAtTime(Math.max(.0001,peak*.15),end);
 }
 amp.gain.exponentialRampToValueAtTime(.0001,end+release);
 src.start(t);src.stop(Math.min(t+src.buffer.duration,end+release+.05));
 return true;
}
global.PSInstrumentEngine={supports:id=>!!SPECS[id],play,version:'1.1'};
})(window);