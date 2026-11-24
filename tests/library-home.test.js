// Isolated phone/browser contract checks: production assets, synthetic API responses, no services.
const {chromium} = require('playwright');
const fs = require('fs'), path = require('path'), assert = require('assert/strict');
const root = path.resolve(__dirname, '..');
const built = path.join(root, 'dist', `argus-ui-${fs.readFileSync(path.join(root,'VERSION'),'utf8').trim()}-leafy-realm`, 'static');
const theme = JSON.parse(fs.readFileSync(path.join(root,'themes/leafy-realm/theme.json')));
const state = {title:'LeafyGrove',personas:theme.agents,jobs:[],watch:[],alerts:[],links:[],media:[],soon:[],quiet:[],role:'owner',updated:'Now',now:'Server: calm',now_name:'Server',
  plugins:[{id:'memory',name:'Memory',kind:'server',agent:true,subtitle:'Library and backups',page:'plugins/memory/page.js',style:'plugins/memory/page.css'}],
  modes:{name:'Server',current:'game',switching:null,modes:[{id:'desktop',label:'Desktop'},{id:'game',label:'Game'}]}};
const source = {id:'a'.repeat(64),revision:'b'.repeat(64),title:'Synthetic touch study',kind:'paper',collection:'Research',health:'ready',authorship:'Fixture author',source_version:'1',extraction_version:'1',indexed_at:'2026-11-22',original:'study.pdf',diagnostic:''};
const sources=Array.from({length:12},(_,i)=>({...source,id:(i+1).toString(16).padStart(64,'0'),title:'Library document '+(i+1),kind:i%2?'book':'note',original:''}));
const reads=[], missing=new Set();
const passage = {...source,source_id:source.id,pdf_page:2,text:'Tactile timing and accuracy. '.repeat(20)};
const backup = {summary:'Backups are fresh.',attention:false,folder:'fixtures',found:true,last:null,job:null,count:0,total_h:'0 B',copies:[],snapshots:[],shelf:7,note:'',why_not:''};
(async () => {
 const browser = await chromium.launch();
 try {
  const p = await browser.newPage({viewport:{width:375,height:812},reducedMotion:'reduce'}), errors=[];
  p.on('pageerror',e=>errors.push(e.message)); let posts=0, failSearch=false, failRead=false;
  await p.route('**/*', async route => {
   const u=new URL(route.request().url()), at=u.pathname.replace(/^\/argus\//,'');
   const json = (data,status=200)=>route.fulfill({json:data,status});
   if(at==='api/state') return json(state);
   if(at==='api/mode'){posts++;state.modes.current=JSON.parse(route.request().postData()).to;return json({ok:true});}
   if(at==='api/memory/state') return json(backup);
   if(at==='api/memory/status') return json({needs:false,line:'Backups are fresh.'});
   if(at==='api/memory/library/catalog') return json({configured:true,sources:sources,total:sources.length,totals:{ready:sources.length},collections:['Research']});
   if(at==='api/memory/library/search') return failSearch?json({msg:'Library unavailable; results kept.'},503):json({configured:true,passages:[passage]});
   if(at==='api/memory/library/source') { const d=sources.find(s=>s.id===u.searchParams.get('id'));return !d||missing.has(d.id)?json({msg:'Source not found'},404):json(d); }
   if(at==='api/memory/library/read') { const d=sources.find(s=>s.id===u.searchParams.get('id')); assert.equal(u.searchParams.get('revision'),d.revision); const offset=Number(u.searchParams.get('offset'));reads.push({id:d.id,revision:d.revision,offset});return failRead?json({msg:'Read failed'},503):json({available:true,offset,total:3,blocks:[{text:'Reading '+d.title+' section '+offset}]}); }
   if(at.startsWith('api/')) return json({});
   let file;
   if(at.startsWith('static/')) file=path.join(built,at.slice(7));
   else if(at.startsWith('plugins/memory/')) file=path.join(root,at);
   else return route.fulfill({contentType:'text/html',body:fs.readFileSync(path.join(built,'index.html'),'utf8').replace('/*STATE*/null',JSON.stringify(state))});
   if(!fs.existsSync(file)) return route.fulfill({status:404,body:''});
   const mime={'.js':'application/javascript','.css':'text/css','.png':'image/png','.woff2':'font/woff2','.json':'application/json'};
   return route.fulfill({body:fs.readFileSync(file),contentType:mime[path.extname(file)]||'application/octet-stream'});
  });
  const origin='http://fixture.test/argus/memory', key='mnemosyne-recent-v1';
  const history=()=>p.evaluate(k=>JSON.parse(localStorage.getItem(k)||'[]'),key);
  const sourceDetails=id=>p.locator('.lib-source[data-source="'+id+'"]');
  const browse=async()=>{await p.locator('#lib-browse').click();await p.locator('#lib-status').filter({hasText:'sources in this view'}).waitFor();};
  const open=async id=>{const d=sourceDetails(id);await d.locator(':scope > summary').click();await d.locator('.lib-reader > summary').click();await d.locator('.lib-reader-text').filter({hasText:'Reading'}).waitFor();};
  const home=async()=>{await p.locator('#lib-home').click();await p.locator('#lib-status').filter({hasText:'checked out documents on this browser'}).waitFor();};
  await p.goto(origin);await p.locator('#lib-results article').first().waitFor();
  assert.deepEqual(await history(),[]);
  await sourceDetails(sources[0].id).locator(':scope > summary').click();
  await sourceDetails(sources[0].id).locator('.lib-reader').waitFor();assert.deepEqual(await history(),[]);
  await p.locator('#lib-query').fill('topic');await p.locator('#lib-search button').click();await p.locator('.lib-excerpt').waitFor();assert.deepEqual(await history(),[]);
  for(const d of sources){await browse();await open(d.id);}
  assert.deepEqual((await history()).map(d=>d.id),sources.slice(2).reverse().map(d=>d.id));
  await home();assert.equal(await p.locator('.lib-continue').count(),10);
  assert.equal(await p.locator('.lib-result h4').first().innerText(),sources[11].title);
  await p.screenshot({path:path.join(process.env.SHOTS||root,'library-home-phone.png'),fullPage:true});
  assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await browse();await open(sources[4].id);
  const d=sourceDetails(sources[4].id);await d.getByText('Read next section',{exact:true}).click();await d.locator('.lib-reader-status').filter({hasText:'Section 2 of 3'}).waitFor();
  assert.equal((await history())[0].id,sources[4].id);assert.equal((await history())[0].offset,1);assert.equal((await history()).length,10);
  await p.reload();await p.locator('.lib-continue').first().click();await p.locator('.lib-reader-status').filter({hasText:'Section 2 of 3'}).waitFor();
  assert.deepEqual(reads.at(-1),{id:sources[4].id,revision:sources[4].revision,offset:1});
  const before=await history();failRead=true;await p.getByText('Read next section',{exact:true}).click();await p.getByText('Read failed',{exact:true}).waitFor();assert.deepEqual(await history(),before);failRead=false;
  sources[4].revision='d'.repeat(64);await home();await p.getByText('Open updated document',{exact:true}).click();await p.locator('.lib-reader-status').filter({hasText:'Section 1 of 3'}).waitFor();assert.equal(reads.at(-1).offset,0);
  missing.add(sources[4].id);await home();assert.equal(await p.getByText('Unavailable document',{exact:true}).count(),1);assert.equal(await p.locator('.lib-continue').count(),9);assert.equal((await history()).length,10);
  // A book read in the page-turning reader (4.69.0): its row says how far, and Continue opens the reader, not the text.
  sources[3].original='book.epub';
  await p.evaluate(({id,revision})=>localStorage.setItem('mnemosyne-book-places-v1',JSON.stringify({[id]:{id,revision,cfi:'epubcfi(/6/4!/4/2/1:0)',fraction:0.34,at:new Date(Date.now()+60000).toISOString(),pending:true}})),{id:sources[3].id,revision:sources[3].revision});
  await home();{const row=p.locator('.lib-result').first();assert.equal(await row.locator('h4').innerText(),sources[3].title);assert.match(await row.locator('.lib-meta').first().innerText(),/· 34% read$/);
   const c=row.locator('a.lib-continue');assert.equal(await c.innerText(),'Continue reading');assert((await c.getAttribute('href')).includes('plugins/memory/reader/?id='+sources[3].id+'&revision='+sources[3].revision+'&format=epub'));
   assert.equal(await row.locator('button.lib-continue').count(),0);}
  await p.evaluate(()=>localStorage.removeItem('mnemosyne-book-places-v1'));sources[3].original='';
  // Existing persisted history must not mask new session-only positions when writes fail.
  await p.evaluate(()=>{const set=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k==='mnemosyne-recent-v1')throw Error('quota');return set.call(this,k,v);};});
  await browse();await open(sources[0].id);await home();assert.equal(await p.locator('.lib-result h4').first().innerText(),sources[0].title);
  // A fresh document load resets the in-memory fallback. Reject array IDs and oversized history.
  await p.reload();await p.locator('#lib-home').waitFor();
  await p.evaluate(({key,id,revision})=>localStorage.setItem(key,JSON.stringify([{id:[id],revision,offset:0},{id:[id],revision,offset:1}])) ,{key,id:sources[1].id,revision:sources[1].revision});
  await p.reload();await p.getByText(/No recently checked out documents yet/).waitFor();assert.equal(await p.locator('.lib-continue').count(),0);
  await p.evaluate(key=>localStorage.setItem(key,'x'.repeat(10001)),key);await p.reload();await p.getByText(/No recently checked out documents yet/).waitFor();
  assert.deepEqual(errors,[]);console.log('PASS recent Home: empty/browse/search, ten distinct, reorder, resume, failed read, changed/retired, denied write, malformed/oversized history, 375px');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
