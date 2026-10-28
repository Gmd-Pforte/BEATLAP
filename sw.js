const SHELL='ps-beatlab-shell-v4';
const AUDIO='ps-beatlab-audio-v1';
const REAL='ps-beatlab-real-v1'; // echte Instrumente: klein, fest, ohne Verdrängung
const SHELL_FILES=['./index.html','./instrument-engine.js','./sampler.js','./samples/real/index.js','./samples/samples.json'];

self.addEventListener('install',event=>{
  event.waitUntil(caches.open(SHELL).then(cache=>cache.addAll(SHELL_FILES)).then(()=>self.skipWaiting()));
});
self.addEventListener('activate',event=>{
  event.waitUntil(Promise.all([caches.keys().then(keys=>Promise.all(keys.filter(k=>![SHELL,AUDIO,REAL].includes(k)).map(k=>caches.delete(k)))),self.clients.claim()]));
});
self.addEventListener('fetch',event=>{
  const request=event.request;
  if(request.method!=='GET')return;
  const url=new URL(request.url);
  if(url.origin!==self.location.origin)return;

  if(request.mode==='navigate'||url.pathname.endsWith('/index.html')){
    event.respondWith((async()=>{
      const cache=await caches.open(SHELL);
      try{
        const response=await fetch(request,{cache:'no-store'});
        if(response.ok)await cache.put('./index.html',response.clone());
        return response;
      }catch(e){return (await cache.match('./index.html'))||Response.error();}
    })());
    return;
  }

  // Verzeichnis und Manifeste: immer frisch holen (offline aus dem Cache), damit neue Instrumente ankommen
  if(url.pathname.includes('/samples/real/')&&/\.(js|json)$/.test(url.pathname)){
    event.respondWith((async()=>{
      const cache=await caches.open(REAL);
      try{const response=await fetch(request,{cache:'no-store'});if(response.ok)await cache.put(request,response.clone());return response;}
      catch(e){return (await cache.match(request))||Response.error();}
    })());
    return;
  }

  // Samples selbst: einmal laden, dann dauerhaft aus dem Cache
  if(url.pathname.includes('/samples/real/')){
    event.respondWith((async()=>{
      const cache=await caches.open(REAL);
      const cached=await cache.match(request);
      if(cached)return cached;
      const response=await fetch(request);
      if(response.ok)await cache.put(request,response.clone());
      return response;
    })());
    return;
  }

  if(url.pathname.includes('/samples/')&&url.pathname.endsWith('.wav')){
    event.respondWith((async()=>{
      const cache=await caches.open(AUDIO);
      const cached=await cache.match(request);
      if(cached)return cached;
      const response=await fetch(request);
      if(response.ok){
        await cache.put(request,response.clone());
        const keys=await cache.keys();
        for(const old of keys.slice(0,Math.max(0,keys.length-24)))await cache.delete(old);
      }
      return response;
    })());
    return;
  }

  if(url.pathname.endsWith('/samples/samples.json')){
    event.respondWith((async()=>{
      const cache=await caches.open(SHELL);
      try{const response=await fetch(request,{cache:'no-store'});if(response.ok)await cache.put(request,response.clone());return response;}
      catch(e){return (await cache.match(request))||Response.error();}
    })());
  }
});
