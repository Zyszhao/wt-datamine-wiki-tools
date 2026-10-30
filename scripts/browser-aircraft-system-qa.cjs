/* Real aircraft regression: dropdown portals, parameters, sensors, economy, legacy presets. */
const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
const {pathToFileURL}=require('node:url');
const {chromium}=require(path.join(process.env.WTW_NODE_MODULES,'playwright'));
const root=path.resolve(__dirname,'..'),report=[];
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.WTW_BROWSER_PATH});try{
for(const width of [1440,390]){
 const page=await browser.newPage({viewport:{width,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.goto(pathToFileURL(path.join(root,'wiki/vehicle-prototype-mig35/preview/index.html')).href);
 assert.deepEqual(await page.locator('.wtv-bwiki-br thead th').allTextContents(),['街机','历史','全真','陆战历史']);
 assert.equal(await page.locator('[data-wtv-mode]').count(),2);
 const beltAxes=await page.locator('#wtv-armaments .game-unit_weapon').first().locator('.wtv-belt-label').evaluateAll(es=>es.map(e=>{
  const icon=e.querySelector('.wtv-belt-icon').getBoundingClientRect(),name=e.querySelector('.wtv-belt-name').getBoundingClientRect();
  return [icon.x+icon.width/2,name.x+name.width/2];
 }));
 assert(beltAxes.length>1);for(const axis of beltAxes)for(let i=0;i<2;i++)assert(Math.abs(axis[i]-beltAxes[0][i])<1);
 const borders=await page.locator('.wtv-store-matrix tr[data-store]').first().locator('th,td').evaluateAll(es=>es.map(e=>[getComputedStyle(e).borderLeftWidth,getComputedStyle(e).borderRightWidth]));
 assert(borders.length>2&&borders.every(b=>b[0]==='1px'&&b[1]==='1px'));
 const categories=await page.locator('.wtv-store-group').evaluateAll(es=>Object.fromEntries(es.map(e=>[e.dataset.category,e.querySelectorAll('tr[data-store]').length])));
 assert.deepEqual(categories,{aam:6,agm:11,bomb:14,guided_bomb:6,rocket:6,fuel:2,pod:1});
 const sides=await page.locator('.game-unit_slot-list thead th[data-slot]').evaluateAll(es=>es.map(e=>e.className));
 assert.equal(sides.filter(s=>s.includes('left')).length,4);assert.equal(sides.filter(s=>s.includes('center')).length,3);assert.equal(sides.filter(s=>s.includes('right')).length,4);
 await page.locator('.wtv-loadout-toggle').click();
 await page.locator('.wtv-slot-choice[data-slot="4"] .wtv-slot-trigger').click();
 const dropdown=page.locator('body>.wtv-dropdown-portal');assert.equal(await dropdown.count(),1);
 assert((await dropdown.locator('img').count())>20);assert((await dropdown.innerText()).includes('KAB'));
 await page.screenshot({path:path.join(root,'work/reports/aircraft-dropdown-'+width+'.png')});
 await page.keyboard.press('Escape');assert.equal(await dropdown.count(),0);
 const name=page.locator('.game-unit_slot-list [data-popup]').first();await name.scrollIntoViewIfNeeded();await name.click();
 const popup=page.locator('body>.wtv-ui-portal');assert((await popup.innerText()).includes('弹体重量'));assert((await popup.innerText()).includes('红外抗干扰'));
 let box=await popup.boundingBox();assert(box.x>=0&&box.x+box.width<=width+1);
 await page.screenshot({path:path.join(root,'work/reports/aircraft-ammo-'+width+'.png')});
 await page.keyboard.press('Escape');assert.equal(await popup.count(),0);
 const sensor=page.locator('#wtv-sensors [data-popup]').filter({hasText:'RWR'}).first();await sensor.scrollIntoViewIfNeeded();await sensor.click();
 assert((await popup.innerText()).includes('70'));assert((await popup.innerText()).includes('跟踪告警'));assert((await popup.innerText()).includes('按威胁类别识别发射'));
 await page.screenshot({path:path.join(root,'work/reports/aircraft-sensors-'+width+'.png')});await page.keyboard.press('Escape');
 await page.locator('#wtv-economy').scrollIntoViewIfNeeded();const economy=await page.locator('#wtv-economy').innerText();
 for(const value of ['4,499','12,934','15,219','100 / 320 / 510','268','305,900','476,000','3,500'])assert(economy.includes(value),value);
 assert(!economy.includes('table:'));await page.screenshot({path:path.join(root,'work/reports/aircraft-economy-'+width+'.png')});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await page.goto(pathToFileURL(path.join(root,'wiki/vehicle-prototype-pe8/preview/index.html')).href);
 assert.equal(await page.locator('.wtv-loadout-editor').count(),0);assert.equal(await page.locator('.wtv-preset').count(),6);assert.equal(await page.locator('.wtv-store-matrix').count(),0);
 assert.deepEqual(await page.locator('.wtv-bwiki-br thead th').allTextContents(),['街机','历史','全真','陆战历史']);
 const fixedBorder=await page.locator('.wtv-fixed-presets td').first().evaluate(e=>getComputedStyle(e).borderLeftWidth);assert.equal(fixedBorder,'1px');
 assert.equal(await page.locator('#wtv-armaments .game-unit_weapon').count(),6);assert.equal(await page.locator('#wtv-armaments .game-unit_belt-list').count(),6);
 const peText=await page.locator('#wtv-armaments').innerText();for(const n of ['750','440','430','400','垂直射界','水平射界'])assert(peText.includes(n));
 await page.locator('#wtv-armaments').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(root,'work/reports/pe8-turrets-'+width+'.png')});
 await page.locator('#wtv-loadouts').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(root,'work/reports/pe8-presets-'+width+'.png')});
 await page.locator('.wtv-preset [data-popup]').last().click();assert((await popup.innerText()).includes('TNT'));await page.keyboard.press('Escape');
 const broken=await page.locator('img[src*="uploads/"]').evaluateAll(es=>es.filter(i=>!i.complete||!i.naturalWidth).map(i=>i.src));assert.deepEqual(broken,[]);
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);assert.deepEqual(errors,[]);
 report.push({width,categories,hardpoints:'passed',dropdown:'passed',ammoPopup:'passed',sensorPopup:'passed',economy:'passed',pe8:{turretWeapons:6,presets:6,customEditor:false},errors});await page.close();
}
fs.writeFileSync(path.join(root,'work/reports/aircraft-system-browser.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1);});
