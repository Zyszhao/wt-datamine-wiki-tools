/* Check the formal deployment rendering, including renamed assets. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {pathToFileURL}=require('node:url');
const {chromium}=require(path.join(process.env.WTW_NODE_MODULES,'playwright'));
const root=path.resolve(__dirname,'..'),folder=path.join(root,'wiki/production/vehicle-pages');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.WTW_BROWSER_PATH});const report=[];try{
for(const width of [1440,390])for(const code of ['il_leopard_2a6_hel','mig_35','pe-8_m82']){
 const page=await browser.newPage({viewport:{width,height:1000}}),errors=[];
 page.on('pageerror',e=>errors.push(String(e)));
 await page.goto(pathToFileURL(path.join(folder,'preview',code,'index.html')).href,{waitUntil:'load'});
 assert.equal(await page.locator('[data-wtv-mode]').count(),2);
 assert.deepEqual(await page.locator('.wtv-bwiki-br thead th').allTextContents(),code==='il_leopard_2a6_hel'?['街机','历史','全真']:['街机','历史','全真','陆战历史']);
 assert.equal(await page.locator('.wtv-side .wtv-mode-switch').evaluate(e=>e===e.parentElement.lastElementChild),true);
 const edits=await page.locator('.wtv-content-edit a').evaluateAll(links=>links.map(e=>e.href));
 assert.equal(edits.length,2);assert(edits.every(h=>!h.includes('Testing') && h.includes(code+'/')));
 const broken=await page.locator('img[src*="uploads/"]').evaluateAll(imgs=>imgs.filter(i=>!i.complete||!i.naturalWidth).map(i=>i.src));
 assert.deepEqual(broken,[]);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 const side=page.locator('.wtv-side');
 if(width>820){
  await page.evaluate(()=>window.scrollTo(0,900));await page.waitForTimeout(80);const a=(await side.boundingBox()).y;
  await page.evaluate(()=>window.scrollTo(0,1200));await page.waitForTimeout(80);assert(Math.abs((await side.boundingBox()).y-a)<2);
  await page.evaluate(()=>{const h=document.createElement('div');h.id='mw-head';h.style.cssText='position:fixed;top:0;left:0;width:100%;height:64px';document.body.appendChild(h);dispatchEvent(new Event('scroll'));});
  await page.waitForTimeout(80);assert((await side.boundingBox()).y>=76);
  await page.evaluate(()=>{document.querySelector('#mw-head').remove();dispatchEvent(new Event('scroll'));});
 }
 for(const mode of ['ab','rb']){
  await page.locator('[data-wtv-mode="'+mode+'"]').click();
  assert.equal(await page.locator('.wtv').getAttribute('data-mode'),mode);
  if(code==='il_leopard_2a6_hel')assert((await page.locator('#wtv-sec-mobility').innerText()).includes(mode==='ab'?'76':'68'));
 }
 if(code==='mig_35')assert((await page.locator('.game-unit_slot-list tbody tr').count())>0);
 if(width>820)await page.evaluate(()=>window.scrollTo(0,850));
 else await page.evaluate(()=>window.scrollTo(0,500));
 await page.screenshot({path:path.join(folder,`demo-${code}-${width}.png`)});
 assert.deepEqual(errors,[]);report.push({code,width,twoModes:'passed',sidebar:'passed',renamedImages:'passed',editTargets:'passed',errors});await page.close();
}
fs.writeFileSync(path.join(folder,'browser-validation.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1);});
