/* Offline rendering/interaction checks for the shared JSON modification tree. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
let playwright;
try { playwright = require('playwright'); }
catch (error) {
  if (error.code !== 'MODULE_NOT_FOUND' || !process.env.WTW_NODE_MODULES) throw error;
  playwright = require(path.join(process.env.WTW_NODE_MODULES, 'playwright'));
}
const root = path.resolve(__dirname, '..');
(async () => {
  const browser = await playwright.chromium.launch({headless:true,
    ...(process.env.WTW_BROWSER_PATH ? {executablePath:process.env.WTW_BROWSER_PATH} : {})});
  const report = [];
  try {
    for (const [kind, folder, count, id] of [['ground','vehicle-prototype',18,'il_leopard_2a6_hel'],['air','vehicle-prototype-mig35',28,'mig_35']]) {
      const data = JSON.parse(fs.readFileSync(path.join(root,'wiki',folder,'pages/data/vehicle',id+'.json'),'utf8'));
      const lookup = new Map(data.modifications.map(m=>[m.id,m]));
      for (const mod of data.modifications) {
        for (const parent of mod.requires) {
          assert(lookup.has(parent), `Missing parent ${parent}`);
          assert(lookup.get(parent).tier <= mod.tier, 'Parent must not follow target tier');
        }
      }
      for (const width of [1440,390]) {
        const page = await browser.newPage({viewport:{width,height:900}});
        const errors=[];
        page.on('pageerror',e=>errors.push(String(e)));
        await page.goto(pathToFileURL(path.join(root,'wiki',folder,'preview/index.html')).href);
        await page.locator('#wtv-modifications').scrollIntoViewIfNeeded();
        await page.waitForTimeout(150);
        const state = await page.evaluate(()=>({
          pageOverflow:document.documentElement.scrollWidth>innerWidth,
          cards:document.querySelectorAll('.wtv-mod-node').length,
          brokenIcons:[...document.querySelectorAll('.wtv-mod-card img')].filter(i=>!i.complete||!i.naturalWidth).length,
          groups:[...document.querySelectorAll('.wtv-mod-group thead')].map(x=>x.textContent),
          cardWidths:[...document.querySelectorAll('.wtv-mod-card')].map(x=>x.getBoundingClientRect().width),
          links:[...document.querySelectorAll('.wtv-mod-node')].filter(x=>x.dataset.requires||x.dataset.previous).length,
          connectorPixels:(()=>{const c=document.querySelector('.wtv-mod-lines');return c?c.getContext('2d').getImageData(0,0,c.width,c.height).data.filter((v,i)=>i%4===3&&v>0).length:0;})(),
          gateText:document.querySelector('.wtv-mod-tiers').innerText
        }));
        const geometry = await page.evaluate(()=>{
          const nodes=[...document.querySelectorAll('.wtv-mod-node')];
          const card=id=>nodes.find(n=>n.dataset.mod===id).querySelector('.wtv-mod-card').getBoundingClientRect();
          const rows=[...document.querySelectorAll('.wtv-mod-group:first-of-type tbody tr')];
          const heights=[...document.querySelector('.wtv-mod-group').querySelectorAll('tbody tr')].map(r=>r.getBoundingClientRect().height);
          const canvas=document.querySelector('.wtv-mod-lines'), bounds=canvas.getBoundingClientRect();
          const sx=canvas.width/bounds.width,sy=canvas.height/bounds.height,ctx=canvas.getContext('2d');
          const horizontal=[];
          nodes.forEach(n=>(n.dataset.requires||'').split(',').filter(Boolean).forEach(id=>{
            const a=card(id),b=n.querySelector('.wtv-mod-card').getBoundingClientRect();
            if(Math.abs(a.top-b.top)>=1)return;
            const x=(a.right+b.left)/2,y=b.top+b.height/2;
            const pixel=ctx.getImageData(Math.floor((x-bounds.left)*sx),Math.floor((y-bounds.top)*sy),1,1).data[3];
            horizontal.push({from:id,to:n.dataset.mod,gap:b.left-a.right,pixel});
          }));
          return {heights,horizontal};
        });
        assert(geometry.heights.every(h=>h<=58), 'Compact row heights: '+JSON.stringify(geometry.heights));
        for(const edge of geometry.horizontal){assert(edge.gap>=16);assert(edge.pixel>0,'Horizontal connector must be painted between cards');}
        assert.equal(state.pageOverflow,false); assert.equal(state.cards,count);
        assert.equal(state.brokenIcons,0); assert(state.cardWidths.every(x=>x===150));
        if (kind==='air') { assert(state.links>0); assert(state.connectorPixels>0); assert(state.gateText.includes('3项')); }
        const section = page.locator('#wtv-modifications');
        await section.screenshot({path:path.join(root,'work/reports',`modifications-${kind}-${width}.png`)});
        const first = page.locator('.wtv-mod-card').first();
        await first.click();
        await page.waitForTimeout(80);
        const popup = page.locator('body > .wtv-mod-portal');
        assert(await popup.isVisible());
        assert.equal(await popup.locator('img[alt="研发点"], img[alt="银狮"], img[alt="金鹰"]').count(),3);
        assert(await popup.evaluate(p=>{const r=p.getBoundingClientRect();return p.contains(document.elementFromPoint(r.left+10,r.top+10));}));
        const box=await popup.boundingBox();
        assert(box.x>=0 && box.x+box.width<=width && box.y>=0 && box.y+box.height<=900);
        await page.keyboard.press('Escape');
        assert.equal(await page.locator('.wtv-mod-node[data-open="1"]').count(),0);
        const scroll=page.locator('.wtv-mod-scroll');
        await scroll.evaluate(x=>x.scrollLeft=x.scrollWidth);
        await section.screenshot({path:path.join(root,'work/reports',`modifications-${kind}-${width}-right.png`)});
        const outer = page.locator('.wtv-mod-accordion');
        assert.equal(await outer.locator(':scope > .wtv-mod-toggle').count(),0);
        assert.equal(await outer.locator('.wtv-mod-scroll').isVisible(),true);
        assert.deepEqual(errors,[]);
        report.push({kind,width,...state,...geometry,interaction:'passed',errors});
        await page.close();
      }
    }
    fs.writeFileSync(path.join(root,'work/reports/vehicle-modifications-qa.json'),JSON.stringify(report,null,2));
    console.log(JSON.stringify(report,null,2));
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exit(1);});
