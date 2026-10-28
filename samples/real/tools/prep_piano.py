# Bereitet Salamander Grand Piano V3 (CC BY 3.0, Alexander Holm) für Beatlab auf.
# Aufruf: SRC=Pfad/zum/SalamanderGrandPiano-Repo; braucht ffmpeg (mit libmp3lame), numpy.

import subprocess, numpy as np, json, os, re, sys
import os as _os
SRC=_os.environ.get('SRC','SalamanderGrandPiano')
OUT=_os.path.join(_os.path.dirname(_os.path.abspath(__file__)),'..','piano')
SR=44100; LEN=3.5; FADE=1.2
roots=['A1','C2','D#2','F#2','A2','C3','D#3','F#3','A3','C4','D#4','F#4','A4','C5','D#5','F#5','A5','C6','D#6','F#6']
layers={'p':4,'mf':9,'f':14}
# region.txt: Zuordnung Grundton → MIDI-Taste (zur Kontrolle)
tune={l.split()[1][5:]:int(l.split()[2]) for l in open(f'{SRC}/Data/tune_ret.txt') if l.startswith('#define $TUNE')}
regions={}
for l in open(f'{SRC}/Data/region.txt'):
    m=re.search(r'region_label=(\d+) tune=\$TUNE(\d+).*pitch_keycenter=(\d+) sample=([A-G]#?\d)\$VEL',l)
    if m: regions[m.group(4)]=(int(m.group(3)), tune[m.group(2)])
NOTE={'C':0,'D#':3,'F#':6,'A':9}
def midi(n): m=re.match(r'([A-G]#?)(\d)',n); return 12*(int(m.group(2))+1)+NOTE[m.group(1)]
def load(path):
    raw=subprocess.run(['ffmpeg','-v','error','-i',path,'-ac','2','-ar',str(SR),'-f','f32le','-'],capture_output=True,check=True).stdout
    return np.frombuffer(raw,dtype=np.float32).reshape(-1,2).copy()
data={}
for r in roots:
    for lab,v in layers.items():
        rel=f'Samples/{r}v{v}.flac'
        subprocess.run(['git','-C',SRC,'checkout','-q','HEAD','--',rel],check=True)
        x=load(f'{SRC}/{rel}')
        a=np.abs(x).max(axis=1); th=a.max()*0.02; i=int(np.argmax(a>th)); i=max(0,i-int(SR*.002))
        x=x[i:i+int(SR*LEN)]
        if len(x)<int(SR*LEN): x=np.vstack([x,np.zeros((int(SR*LEN)-len(x),2),np.float32)])
        n=int(SR*FADE); w=0.5*(1+np.cos(np.linspace(0,np.pi,n))); x[-n:]*=w[:,None]
        x[:32]*=np.linspace(0,1,32)[:,None]
        data[(r,lab)]=x
peak=max(np.abs(x).max() for x in data.values()); g=10**(-1/20)/peak
man={'format':'beatlab-sampler-1','id':'grandReal','name':'Flügel (echt)',
     'source':'Salamander Grand Piano V3 (Yamaha C5), https://github.com/sfzinstruments/SalamanderGrandPiano',
     'author':'Alexander Holm','license':'CC BY 3.0','licenseUrl':'https://creativecommons.org/licenses/by/3.0/',
     'attribution':'Salamander Grand Piano V3 von Alexander Holm, CC BY 3.0 (bearbeitet: gekürzt, ausgeblendet, normalisiert, MP3)',
     'changes':'3 von 16 Dynamikstufen (v4, v9, v14), 20 Grundtöne A1–F#6 in kleinen Terzen, auf 3,5 s gekürzt mit 1,2 s Ausblendung, gemeinsam normalisiert (-1 dBFS), 44,1 kHz Stereo, MP3 128 kbit/s',
     'gainDb':0,'release':0.35,'maxShift':2,'layers':[]}
for lab,vmax in [('p',0.5),('mf',0.85),('f',99)]:
    notes=[]
    for r in roots:
        x=np.clip(data[(r,lab)]*g,-1,1); fn=f"{r.replace('#','s')}-{lab}.mp3"
        p=subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar',str(SR),'-ac','2','-i','-','-c:a','libmp3lame','-b:a','128k',f'{OUT}/{fn}'],input=x.astype(np.float32).tobytes(),check=True)
        key,_=regions[r]; assert key==midi(r),(r,key)
        notes.append({'midi':key,'tune':0,'file':fn})
    man['layers'].append({'name':lab,'velMax':vmax,'notes':notes})
# Stimmung selbst messen (mittlere Dynamikstufe) und auf gleichstufig korrigieren.
# Die "retuned"-Tabelle der SFZ-Fassung passte bei der Messung nicht konsistent (bis 20 Cent daneben).
def f0(x,exp,sr=SR):
    x=x[int(sr*.1):int(sr*1.6)]; x=x*np.hanning(len(x)); n=1<<19; X=np.abs(np.fft.rfft(x,n)); f=np.fft.rfftfreq(n,1/sr); best=None
    for k in (1,2,3,4):
        lo,hi=np.searchsorted(f,[k*exp*0.97,k*exp*1.03])
        if hi>lo:
            i=lo+np.argmax(X[lo:hi])
            if best is None or X[i]>best[0]: best=(X[i],f[i]/k)
    return best[1]
corr={}
for n in next(l for l in man['layers'] if l['name']=='mf')['notes']:
    raw=subprocess.run(['ffmpeg','-v','error','-i',f"{OUT}/{n['file']}",'-ac','1','-ar',str(SR),'-f','f32le','-'],capture_output=True,check=True).stdout
    exp=440*2**((n['midi']-69)/12); corr[n['midi']]=-round(1200*np.log2(f0(np.frombuffer(raw,np.float32),exp)/exp))
for l in man['layers']:
    for n in l['notes']: n['tune']=corr[n['midi']]
man['changes']+=', Stimmung je Grundton gemessen und auf gleichstufig korrigiert (tune in Cent)'
json.dump(man,open(f'{OUT}/manifest.json','w'),ensure_ascii=False,indent=1)
print('peak',peak,'files',len(os.listdir(OUT)))
