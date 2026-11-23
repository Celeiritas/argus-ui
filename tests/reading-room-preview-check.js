// Used by the project's isolated library UI test, with the actual bundled HTML and CSP.
module.exports = async function checkReadingRoom(p, assert, path, shots) {
 const noOverflow=async()=>assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'preview overflow');
 assert.equal(await p.locator('.volume').count(),10);
 assert(await p.getByText('Reading room preview · Sample books',{exact:true}).isVisible());
 await p.getByText('How to try it',{exact:true}).click();
 assert(await p.getByText('Open Browse shelves, then choose a shelf by its icon and color.').isVisible());
 await p.getByText('How to try it',{exact:true}).click();
 for(const theme of ['wood','stone']) {
  await p.getByLabel('Shelf material').selectOption(theme);
  for(const width of [320,375,768,1440]) {await p.setViewportSize({width,height:900});await noOverflow();}
  await p.setViewportSize({width:375,height:900});
  if(shots) await p.screenshot({path:path.join(shots,`reading-room-${theme}-v4.png`),fullPage:true});
 }
 const identity={books:['Books','#C2A2EE'],papers:['Papers','#72C9E6'],notes:['Notes','#F2C46B'],guides:['Guides','#89D1A3']};
 for(const [id,[label,color]] of Object.entries(identity)) {
  await p.locator('nav [data-view="home"]').click();
  const key=p.locator(`.shelf-key [data-cat="${id}"]`);
  assert.equal(await key.locator('svg').count(),1);
  assert.equal((await key.evaluate(e=>getComputedStyle(e).getPropertyValue('--accent'))).trim(),color);
  await key.click();assert.equal(await p.locator('#shelf-context').innerText(),label);
  for(const c of await p.locator('.volume').all()) {
   assert.equal((await c.evaluate(e=>getComputedStyle(e).getPropertyValue('--accent'))).trim(),color);
   assert.equal(await c.locator('.jacket svg').count(),1);
  }
  await p.goBack();assert.equal(await p.locator('.volume').count(),10);
 }
 await p.locator('nav [data-view="shelves"]').click();
 await p.locator('#rail').focus();await p.keyboard.press('End');
 assert.equal(await p.locator('#rail').getAttribute('aria-valuetext'),'Guides');
 await p.setViewportSize({width:812,height:375});await noOverflow();assert(await p.locator('#rail').isHidden());assert(await p.getByLabel('Jump to',{exact:true}).isVisible());
 await p.getByLabel('Jump to',{exact:true}).selectOption('0');await p.setViewportSize({width:375,height:900});
 await p.locator('.category[data-cat="books"]').click();
 const rail=await p.locator('#rail').boundingBox();
 await p.mouse.move(rail.x+22,rail.y+10);await p.mouse.down();await p.mouse.move(rail.x+22,rail.y+rail.height-10);await p.mouse.up();
 assert.equal(await p.locator('#rail').getAttribute('aria-valuetext'),'T');
 await p.getByLabel('Jump to',{exact:true}).selectOption('0');
 if(shots) await p.screenshot({path:path.join(shots,'reading-room-index-v4.png'),fullPage:true});
 for(const width of [320,375,768,1440]) {await p.setViewportSize({width,height:900});await noOverflow();}
 await p.setViewportSize({width:375,height:900});
 const title=await p.locator('.volume strong').first().innerText();
 await p.locator('.volume').first().click();await p.locator('#readerTitle').waitFor();
 await p.getByText('Reading controls',{exact:true}).click();await p.getByLabel('Go to section',{exact:true}).selectOption('2');
 await p.getByText('Reading controls',{exact:true}).click();await p.getByRole('button',{name:'Save a ribbon here',exact:true}).click();
 await p.getByLabel('Go to section',{exact:true}).selectOption('4');
 await p.getByText('Reading controls',{exact:true}).click();await p.getByRole('button',{name:'Return to ribbon',exact:true}).click();
 assert.equal(await p.locator('.readerbar small').innerText(),'Section 3 of 5');
 await p.getByRole('button',{name:'Focus on reading',exact:true}).click();assert(await p.locator('nav').isHidden());
 await noOverflow();if(shots) await p.screenshot({path:path.join(shots,'reading-room-reader-v4.png')});
 await p.getByRole('button',{name:'Leave focus',exact:true}).click();
 await p.locator('[data-back]').click();await p.locator('.volume').first().waitFor();
 assert.equal(await p.locator('.volume').count(),4);
 await p.goForward();await p.locator('#readerTitle').waitFor();assert.equal(await p.locator('.readerbar small').innerText(),'Section 3 of 5');
 await p.locator('nav [data-view="home"]').click();assert.equal(await p.locator('.volume strong').first().innerText(),title);
 await p.locator('#query').fill('timing');await p.locator('#search button').click();assert.equal(await p.locator('.volume').count(),1);
 assert.equal(await p.locator('.volume strong').innerText(),'Haptics and Timing');
 await p.locator('#query').fill('no matching sample');await p.locator('#query').press('Enter');assert.equal(await p.locator('.volume').count(),0);
 await p.reload();assert.equal(await p.locator('.volume').count(),10);
 console.log('PASS reading room: category identity, wood/stone, 320/375/768/1440, drag/keyboard/Jump, ribbon/focus, browser Back/Forward, recent Home, search, reload');
};
