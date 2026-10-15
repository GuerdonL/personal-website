import fs from 'fs';
const html = fs.readFileSync('index.html','utf8');
const js = html.slice(html.indexOf('<script>')+8, html.lastIndexOf('</script>'));
// pull out only the pure helpers
const start = js.indexOf('/* ---------- diff engine'); const end = js.indexOf('/* ---------- reader');
const src = js.slice(start, end) + '\nglobalThis.__x={myers,tokenize,wordDiff,normWord};';
new Function(src)();
const {tokenize, wordDiff} = globalThis.__x;
// synthetic 40k-word article with 50 revisions, random edits (insert/delete/replace sentences), plus one big section move
let words = []; const vocab = 'the harbour town granite breakwater salted fish trade nineteenth century settlers warehouses quay storm lantern festival coast anchorage sailors founded'.split(' ');
let r = 1; const rnd = () => (r = (r*1103515245+12345) & 0x7fffffff) / 0x7fffffff;
for (let i=0;i<40000;i++){ words.push(vocab[Math.floor(rnd()*vocab.length)]); if (i%18===17) words.push('.\n'); }
let text = words.join(' ');
const revs=[text];
for (let k=1;k<50;k++){ let lines=text.split('\n'); for(let e=0;e<6;e++){ const i=Math.floor(rnd()*lines.length); const op=rnd(); if(op<.33) lines.splice(i,0,'new sentence number '+k+' about the '+vocab[k%vocab.length]+' and more words here .'); else if(op<.66) lines.splice(i,1); else lines[i]=lines[i].replace(/harbour/g,'port'+k); } if(k===25){ const chunk=lines.splice(100,300); lines.splice(1500,0,...chunk);} text=lines.join('\n'); revs.push(text); }
console.time('tokenize+diff 50 revs');
let cur = tokenize(revs[0]).map(t=>({...t,author:null}));
let attributed=0;
for (let i=1;i<revs.length;i++){ const next=tokenize(revs[i]); const segs=wordDiff(cur,next); const merged=[]; for(const s of segs){ if(s.t==='=') for(let k=0;k<s.b.length;k++) merged.push({...s.b[k],author:s.a[k].author}); else if(s.t==='+') for(const t of s.b) merged.push({...t,author:'u'+(i%5)}); } cur=merged; }
console.timeEnd('tokenize+diff 50 revs');
const finalText = cur.map(t=>t.s).join(''); console.log('reconstructed text identical:', finalText===revs[49]);
const counts={}; for(const t of cur) if(t.w) counts[t.author]=(counts[t.author]||0)+1; console.log('author word counts', counts);
