// Isolated phone/browser contract checks: production assets, synthetic API responses, no services.
const {chromium} = require('playwright');
const fs = require('fs'), path = require('path'), assert = require('assert/strict');
const root = path.resolve(__dirname, '..');
const built = path.join(root, 'dist', `argus-ui-${fs.readFileSync(path.join(root,'VERSION'),'utf8').trim()}-leafy-realm`, 'static');
const previewPath='plugins/memory/reading-room-preview.html';
const previewCsp="sandbox allow-scripts allow-pointer-lock allow-popups; frame-ancestors 'self'";
const checkReadingRoom=require('./reading-room-preview-check');
const theme = JSON.parse(fs.readFileSync(path.join(root,'themes/leafy-realm/theme.json')));
const state = {title:'LeafyGrove',personas:theme.agents,jobs:[],watch:[],alerts:[],links:[],media:[],soon:[],quiet:[],role:'owner',updated:'Now',now:'Server: calm',now_name:'Server',
  plugins:[{id:'memory',name:'Memory',kind:'server',agent:true,subtitle:'Library and backups',page:'plugins/memory/page.js',style:'plugins/memory/page.css'}],
  modes:{name:'Server',current:'game',switching:null,modes:[{id:'desktop',label:'Desktop'},{id:'game',label:'Game'}]}};
const source = {id:'a'.repeat(64),revision:'b'.repeat(64),title:'Synthetic touch study',kind:'paper',collection:'Research',health:'ready',authorship:'Fixture author',source_version:'1',extraction_version:'1',indexed_at:'2026-11-22',original:'study.pdf',diagnostic:''};
const passage = {...source,source_id:source.id,pdf_page:2,text:'Tactile timing and accuracy. '.repeat(20)};
const backup = {summary:'Backups are fresh.',attention:false,folder:'fixtures',found:true,last:null,job:null,count:0,total_h:'0 B',copies:[],snapshots:[],shelf:7,note:'',why_not:''};
(async () => {
 const browser = await chromium.launch();
 try {
  const p = await browser.newPage({viewport:{width:375,height:812},reducedMotion:'reduce'}), errors=[];
  p.on('pageerror',e=>errors.push(e.message)); let posts=0, failSearch=false, failRead=false;
  await p.route('**/*', async route => {
   const u=new URL(route.request().url()), at=u.pathname.replace(/^\/(?:argus\/)?/,'');
   const json = (data,status=200)=>route.fulfill({json:data,status});
   if(at==='api/state') return json(state);
   if(at==='api/mode'){posts++;state.modes.current=JSON.parse(route.request().postData()).to;return json({ok:true});}
   if(at==='api/memory/state') return json(backup);
   if(at==='api/memory/status') return json({needs:false,line:'Backups are fresh.'});
   if(at==='api/memory/library/catalog') return json({configured:true,sources:[source],total:1,totals:{ready:1},collections:['Research']});
   if(at==='api/memory/library/search') return failSearch?json({msg:'Library unavailable; results kept.'},503):json({configured:true,passages:[passage]});
   if(at==='api/memory/library/source') return json(source);
   if(at==='api/memory/library/read') { assert.equal(u.searchParams.get('revision'),source.revision); if(failRead) return json({msg:'Reader temporarily unavailable.'},503); return json({available:true,offset:Number(u.searchParams.get('offset')),total:2,blocks:[{pdf_page:source.file_format==='epub'?null:2,chapter:source.file_format==='epub'?passage.chapter:null,text:'Exact text <script>throw new Error(1)</script>\n  preserved lines'}]}); }
   if(at.startsWith('api/')) return json({});
   let file;
   if(at===previewPath) file=path.join(built,'..','bundled','memory','reading-room-preview.html');
   else if(at.startsWith('static/')) file=path.join(built,at.slice(7));
   else if(at.startsWith('plugins/memory/')) file=path.join(root,at);
   else return route.fulfill({contentType:'text/html',body:fs.readFileSync(path.join(built,'index.html'),'utf8').replace('/*STATE*/null',JSON.stringify(state))});
   if(!fs.existsSync(file)) return route.fulfill({status:404,body:''});
   const mime={'.html':'text/html','.js':'application/javascript','.css':'text/css','.png':'image/png','.woff2':'font/woff2','.json':'application/json'};
   return route.fulfill({body:fs.readFileSync(file),contentType:mime[path.extname(file)]||'application/octet-stream',headers:at===previewPath?{'content-security-policy':previewCsp,'x-content-type-options':'nosniff'}:{}});
  });
  const origin='http://fixture.test/argus/';
  await p.goto(origin); await p.locator('.home-server #modes').waitFor();
  assert.equal(await p.locator('header #modes').count(),0);
  assert.equal(await p.locator('.mode-seg.on').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(40, 112, 67)');
  assert(await p.evaluate(()=>document.querySelector('#modes').getBoundingClientRect().top>=document.querySelector('.home-server .now').getBoundingClientRect().bottom));
  const btn=p.locator('[data-mode-to="desktop"]');await btn.focus();await p.keyboard.down('Space');await p.waitForTimeout(3300);await p.keyboard.up('Space');
  assert.equal(posts,1); await p.waitForTimeout(2200);
  await p.screenshot({path:path.join(process.env.SHOTS||root,'today-phone.png')});
  for(const at of ['argus','mentor','olympus','phone','memory']) {await p.goto(origin+at);assert(await p.locator('#modes').isHidden());}
  await p.locator('#lib-results article').waitFor();
  assert.equal(await p.locator('#mem-backups').getAttribute('open'),null);
  await p.locator('#lib-query').fill('tactile timing'); await p.locator('#lib-search button').click();
  await p.locator('.lib-excerpt').waitFor();await p.getByText('Read full passage',{exact:true}).click();
  assert.equal(await p.locator('.lib-full').textContent(),passage.text);
  await p.getByText('Read source and details',{exact:true}).click();{const o=p.locator('a.lib-original');await o.waitFor();const h=await o.getAttribute('href');if(!h.includes('api/memory/library/original.pdf?id='+source.id+'&revision='+source.revision)||await o.getAttribute('target')!=='_blank')throw new Error('original PDF link: '+h);}
  {const b=p.locator('.lib-source-body > a.lib-read-book');assert.equal(await b.innerText(),'Read book');const h=await b.getAttribute('href');
   assert(h.includes('plugins/memory/reader/?id='+source.id+'&revision='+source.revision+'&format=pdf'),'Read book link: '+h);assert.equal(await b.getAttribute('target'),null);
   assert.equal(new URL(h,'http://x/').searchParams.get('title'),String(source.title).slice(0,200),'the library title goes to the reader (4.69.1)');
   assert.equal(await p.locator('.lib-source-body').evaluate(x=>x.firstElementChild.className),'lib-read-book');assert((await b.boundingBox()).height>=44);}
  await p.getByText('Read source text',{exact:true}).click();await p.locator('.lib-reader-text').filter({hasText:'preserved lines'}).waitFor();
  assert((await p.locator('.lib-reader-text').textContent()).includes('<script>'));
  assert.equal(await p.locator('.lib-reader script').count(),0);
  await p.getByText('Read next section',{exact:true}).click();await p.waitForTimeout(100);assert(await p.getByText('Read next section',{exact:true}).isDisabled());
  await p.getByText('Read previous section',{exact:true}).click();await p.waitForTimeout(100);assert(await p.getByText('Read previous section',{exact:true}).isDisabled());
  assert.equal(await p.locator('.lib-reader-status').evaluate(e=>e===document.activeElement),true);
  failRead=true;await p.getByText('Read next section',{exact:true}).click();await p.getByText('Reader temporarily unavailable.',{exact:true}).waitFor();assert((await p.locator('.lib-reader-text').textContent()).includes('preserved lines'));failRead=false;
  await p.getByText('Read next section',{exact:true}).click();await p.waitForTimeout(100);
  await p.screenshot({path:path.join(process.env.SHOTS||root,'library-reader-phone-v2.png'),fullPage:true});
  failSearch=true;await p.locator('#lib-search button').click();await p.waitForTimeout(100);assert.equal(await p.locator('.lib-excerpt').count(),1);
  await p.evaluate(()=>refresh());await p.waitForTimeout(100);assert.equal(await p.locator('#lib-query').inputValue(),'tactile timing');
  await p.locator('.lib-source > summary').click(); await p.getByText('Read full passage',{exact:true}).click();
  await p.screenshot({path:path.join(process.env.SHOTS||root,'library-phone.png'),fullPage:true});
  await p.locator('.lib-filters summary').click();await p.locator('#lib-kind').selectOption('learning');
  for(const width of [375,430,1440]) {await p.setViewportSize({width,height:900});assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`overflow at ${width}`);}
  failSearch=false;
  await p.setViewportSize({width:375,height:812});
  await p.goto(origin+'memory');
  const openReader=async(browse=true)=>{if(browse){await p.locator('#lib-browse').click();await p.locator('#lib-status').filter({hasText:'sources in this view'}).waitFor();}await p.getByText('Read source and details',{exact:true}).click();await p.getByText('Read source text',{exact:true}).click();await p.locator('.lib-reader-text').filter({hasText:'preserved lines'}).waitFor();};
  await openReader();
  assert(await p.getByText('Resume reading',{exact:true}).isHidden());
  await p.getByText('Jump to section',{exact:true}).click();
  await p.getByLabel('Section number').fill('2');await p.getByText('Read section',{exact:true}).click();
  await p.getByText(/Section 2 of 2/).waitFor();
  await p.getByText('Save place',{exact:true}).click();await p.getByText('Saved section 2 on this browser. Other devices get it when the server answers.',{exact:true}).waitFor();
  await p.reload();await openReader();
  await p.getByText('Resume reading',{exact:true}).click();await p.getByText(/Section 2 of 2/).waitFor();
  // Merely opening another section or a search match must not replace the saved place.
  await p.getByText('Read previous section',{exact:true}).click();await p.getByText(/Section 1 of 2/).waitFor();
  await p.locator('#lib-query').fill('timing');await p.locator('#lib-search button').click();await p.locator('.lib-excerpt').waitFor();await openReader(false);
  await p.getByText('Saved section 2 on this browser. Other devices get it when the server answers.',{exact:true}).waitFor();
  failRead=true;await p.getByText('Resume reading',{exact:true}).click();await p.getByText('Reader temporarily unavailable.',{exact:true}).waitFor();
  assert((await p.locator('.lib-reader-text').innerText()).includes('preserved lines'));
  await p.getByText('Save place',{exact:true}).click();await p.getByText('Saved section 1 on this browser. Other devices get it when the server answers.',{exact:true}).waitFor();
  failRead=false;await p.getByText('Read next section',{exact:true}).click();await p.getByText(/Section 2 of 2/).waitFor();
  source.revision='c'.repeat(64);passage.revision=source.revision;
  await p.reload();await openReader();assert(await p.getByText('Resume reading',{exact:true}).isHidden());
  // Corrupt and denied storage must never block reading.
  await p.evaluate(()=>localStorage.setItem('mnemosyne-reading-places-v1','{broken'));
  await p.reload();await openReader();assert(await p.getByText('Resume reading',{exact:true}).isHidden());
  await p.getByText('Save place',{exact:true}).click();await p.getByText('Saved section 1 on this browser. Other devices get it when the server answers.',{exact:true}).waitFor();
  await p.evaluate(()=>{Storage.prototype.setItem=function(){throw new Error('denied');};});
  await p.getByText('Save place',{exact:true}).click();await p.getByText('This browser could not save your place. You can keep reading.',{exact:true}).waitFor();
  await p.getByText('Read next section',{exact:true}).click();await p.getByText(/Section 2 of 2/).waitFor();
  await p.getByText('Jump to section',{exact:true}).click();
  await p.screenshot({path:path.join(process.env.SHOTS||root,'library-reading-place-phone.png'),fullPage:true});
  assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await p.reload();
  failSearch=false;source.kind='book';source.file_format='epub';source.original='';passage.kind='book';passage.pdf_page=null;
  passage.chapter={number:2,label:'Ending',reader_offset:1,member:'OPS/ending.xhtml',linear:true};
  await p.setViewportSize({width:375,height:812});await p.locator('.lib-filters summary').click();await p.locator('#lib-kind').selectOption('book');
  await p.locator('#lib-query').fill('conclusion');await p.locator('#lib-search button').click();
  await p.getByText('Read source and details',{exact:true}).click();await p.getByText('Read source text',{exact:true}).click();
  await p.getByText(/Section 2 of 2 · Chapter 2: Ending/).waitFor();
  assert.equal(await p.locator('a.lib-read-book').count(),0,'no original, no Read book');
  assert(!(await p.locator('.lib-reader-status').innerText()).includes('PDF page'));
  await p.screenshot({path:path.join(process.env.SHOTS||root,'library-epub-phone.png'),fullPage:true});
  // Follow the visible entry at both supported mounts using the packaged preview and real sandbox.
  for(const mount of ['/', '/argus/']) {
   await p.goto('http://fixture.test'+mount+'memory');
   const link=p.locator('#lib-preview');await link.waitFor();assert(await link.isVisible());
   const href=await link.evaluate(a=>a.href);assert.equal(new URL(href).pathname,mount+previewPath);
   const requests=[],track=r=>requests.push(r);p.on('request',track);
   const responsePromise=p.waitForResponse(href);await link.click();const response=await responsePromise;
   assert.equal(response.status(),200);assert.equal(response.headers()['content-security-policy'],previewCsp);
   await p.locator('#app [data-open]').first().waitFor();
   assert(await p.evaluate(()=>{try{localStorage.getItem('probe');return false;}catch(e){return e.name==='SecurityError';}}));
   await checkReadingRoom(p,assert,path,mount==='/argus/'?process.env.SHOTS:null);
   assert(requests.every(r=>r.method()==='GET'&&!new URL(r.url()).pathname.includes('/api/')));
   p.off('request',track);
   await p.getByRole('link',{name:'Return to Mnemosyne',exact:false}).click();
   await p.locator('#lib-preview').waitFor();assert.equal(new URL(p.url()).pathname,mount+'memory');
  }
  assert.deepEqual(errors,[]);console.log('PASS Today placement, green state, keyboard hold, five hidden routes, library expansion, original access, retained results, refresh, 375/430/1440 widths');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
