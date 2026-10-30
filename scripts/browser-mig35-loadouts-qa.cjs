const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
const {pathToFileURL}=require('node:url');
const {chromium}=require(path.join(process.env.WTW_NODE_MODULES,'playwright'));
const root=path.resolve(__dirname,'..');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.WTW_BROWSER_PATH});const checks=[];try{
for(const width of [1440,390]){
 const page=await browser.newPage({viewport:{width,height:1000}}), errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.goto(pathToFileURL(path.join(root,'wiki/vehicle-prototype-mig35/preview/index.html')).href);
 assert.equal(await page.locator('.game-unit_slot-list tbody tr[data-store]').count(),46);
 assert.equal(await page.locator('.game-unit_slot-list thead th').count(),13);
 assert.equal(await page.locator('.wtv-belt-icon').count(),5);
 assert.equal(await page.locator('.wtv-belt-icon').first().locator('img').count(),4);
 assert.equal(await page.locator('#wtv-sec-aircraft-general .wtv-pending').count(),0);
 for(const [mode,weight,speed] of [['ab','11.73 → 11.12','2203 → 2378'],['rb','11.8 → 11.42','2155 → 2286']]){
  await page.locator('[data-wtv-mode="'+mode+'"]').click();
  assert((await page.locator('#wtv-sec-aircraft-general').innerText()).includes(weight));
  assert((await page.locator('#wtv-sec-mobility').innerText()).includes(speed));
 }
 await page.locator('#wtv-armaments').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(root,'work/reports/mig35-belts-'+width+'.png')});
 await page.locator('#wtv-loadouts').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(root,'work/reports/mig35-loadouts-'+width+'.png')});
 await page.locator('.wtv-loadout-editor>.wtv-loadout-toggle').click();
 const result=page.locator('.wtv-loadout-result');
 async function choose(slot,option){await page.locator('.wtv-slot-choice[data-slot="'+slot+'"] .wtv-slot-trigger').click();await page.locator('body>.wtv-dropdown-portal .wtv-store-choice[data-option="'+option+'"]').click();}
 assert.equal(await result.getAttribute('data-validity'),'passed');
 await choose(4,'kab_500l');assert.equal(await result.getAttribute('data-validity'),'invalid');assert((await result.innerText()).includes('t220'));
 await choose(7,'t220');assert.equal(await result.getAttribute('data-validity'),'passed');assert((await result.innerText()).includes('825.0 kg'));
 await choose(4,'kab_1500kr');assert.equal(await result.getAttribute('data-validity'),'invalid');assert((await result.innerText()).includes('失衡'));
 await choose(8,'kab_1500kr');assert.equal(await result.getAttribute('data-validity'),'passed');
 await choose(3,'kab_500kr');await choose(4,'kab_1500kr');assert.equal(await result.getAttribute('data-validity'),'passed');
 await choose(3,'fab_500_m54');await choose(4,'kab_1500kr'); // 2003 kg on one wing remains under 2500.
 await choose(3,'kh_31pd');await choose(1,'r77');await choose(2,'r77_default');
 assert.equal(await result.getAttribute('data-validity'),'invalid');assert((await result.innerText()).includes('右翼重量超过上限'));
 await choose(1,'');await choose(2,'');
 assert.equal(await page.locator('.wtv-slot-choice[data-slot="9"] [data-option="kab_1500kr"]').count(),0);
 // Fuel tanks require the paired opposite wing option.
 for(const slot of [3,4,7,8])await choose(slot,'');
 await choose(3,'ptb_slot3');assert.equal(await result.getAttribute('data-validity'),'invalid');
 await choose(9,'ptb_slot9');assert.equal(await result.getAttribute('data-validity'),'passed');
 await choose(3,'b8m1_s_8ko');await choose(9,'');assert((await result.innerText()).includes('20'));
 const broken=await page.locator('img[src*="uploads/"]').evaluateAll(imgs=>imgs.filter(i=>!i.complete||!i.naturalWidth).map(i=>i.src));assert.deepEqual(broken,[]);
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);assert.deepEqual(errors,[]);
 checks.push({width,matrix:46,belts:5,modes:'passed',dependency:'passed',imbalance:'passed',pairedTanks:'passed',counts:'passed',brokenImages:broken});await page.close();
}fs.writeFileSync(path.join(root,'work/reports/mig35-loadouts-browser.json'),JSON.stringify(checks,null,2));console.log(JSON.stringify(checks));
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1);});
