/* Exercise the production runtime, including its removal of the hint element. */
const fs=require('fs'),path=require('path'),{pathToFileURL}=require('url');
const {chromium}=require(path.join(process.env.WTW_NODE_MODULES||'node_modules','playwright'));
const root=path.resolve(__dirname,'..'),out=path.join(root,'wiki/production');
(async()=>{const browser=await chromium.launch({channel:'msedge',headless:true});try{
 const p=await browser.newPage(),errors=[],results=[];p.on('pageerror',e=>errors.push(e.message));
 const manifest=JSON.parse(fs.readFileSync(path.join(out,'manifest.json'),'utf8'));
 // Remote image availability is reported separately; geometry/interaction checks
 // use local vehicle slots and don't require downloading site media.
 await p.route('https://**/*',route=>route.abort());
 for(const [key,tree] of Object.entries(manifest.trees)){
  for(const viewport of [1500,390]){
   await p.setViewportSize({width:viewport,height:1000});
   await p.goto(pathToFileURL(path.join(root,'work/preview/production',key+'.html')).href);
   await p.waitForFunction(()=>document.querySelector('.wtt-filters')&&document.querySelector('.wtt-results'));
   if(await p.locator('.wtt-search-hint').count())throw Error('hint '+key);
   if(await p.locator('.wtt-card').count()!==tree.visible)throw Error('cards '+key);
   const size=await p.locator('.wtt-card:visible').first().evaluate(e=>{const r=e.getBoundingClientRect();return {w:r.width,h:r.height};});
   if(Math.abs(size.w-120)>1||Math.abs(size.h-48)>1)throw Error('card scaling '+key+' '+viewport+' '+JSON.stringify(size));
   if(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('page overflow '+key);
   await p.locator('body').evaluate(e=>e.style.fontFamily='Georgia, serif');
   if(!(await p.locator('.wtt-name').first().evaluate(e=>getComputedStyle(e).fontFamily)).includes('Georgia'))throw Error('font '+key);
   const role=p.getByLabel('类别',{exact:true}),options=await role.locator('option').evaluateAll(a=>a.map(e=>e.value));
   for(const value of options.filter(Boolean)){
    await role.selectOption(value);
    const active=p.locator('.wtt-card:not(.wtt-filtered-card)');
    if(!await active.count()||await active.evaluateAll((a,v)=>a.some(e=>e.dataset.role!==v),value))throw Error('role '+key);
   }
   await role.selectOption('');
   const search=p.getByLabel('搜索载具',{exact:true}),first=await p.locator('.wtt-card').first().getAttribute('data-unit');
   await search.fill(first);if(!await p.locator('.wtt-card:not(.wtt-filtered-card)').count())throw Error('search '+key);await search.fill('');
   await p.locator('.wtt-br-filter summary').click();const slider=p.getByLabel('历史权重下限',{exact:true});
   await slider.fill('1');await slider.dispatchEvent('input');
   const threshold=+(await slider.getAttribute('aria-valuetext'));
   if(await p.locator('.wtt-card:not(.wtt-filtered-card)').evaluateAll((a,t)=>a.some(e=>+e.querySelector('.wtt-br-rb').textContent<t),threshold))throw Error('BR '+key);
   await p.locator('.wtt-results button').click();await p.mouse.click(1,1);
   await p.locator('.wtt-view-toggle').click();if(await p.locator('.wtt-card:visible').count()!==tree.visible)throw Error('list '+key);
   await p.locator('.wtt-view-toggle').click();
   const group=p.locator('.wtt-group').first();if(await group.count()){
    await group.click();if(await group.getAttribute('aria-expanded')!=='true')throw Error('group '+key);
    await p.mouse.click(1,1);if(await group.getAttribute('aria-expanded')!=='false')throw Error('outside '+key);
   }
   if(['usa_army','china_aviation','germany_boats','japan_ships'].includes(key)&&viewport===1500){
    await p.evaluate(()=>scrollTo(0,0));await p.screenshot({path:path.join(out,key+'-preview.png')});
   }
   results.push({key,viewport,cards:tree.visible,filter:true,br:true,groups:true,width:true,font:true});
  }
 }
 if(errors.length)throw Error(JSON.stringify(errors));
 fs.writeFileSync(path.join(out,'browser-validation.json'),JSON.stringify({passed:true,remoteMediaBlockedForDeterministicInteractionChecks:true,liveWikiImportVerified:false,results},null,2));
 console.log(JSON.stringify({passed:true,trees:Object.keys(manifest.trees).length,viewports:results.length,errors}));
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
