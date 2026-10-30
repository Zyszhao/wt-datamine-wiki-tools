/* Exercise the production runtime, including its removal of the hint element. */
const fs=require('fs'),path=require('path'),{pathToFileURL}=require('url');
const {chromium}=require(path.join(process.env.WTW_NODE_MODULES||'node_modules','playwright'));
const root=path.resolve(__dirname,'..'),out=path.join(root,'wiki/production');
(async()=>{const browser=await chromium.launch({channel:'msedge',headless:true});try{
 const p=await browser.newPage(),errors=[],results=[];p.on('pageerror',e=>errors.push(e.message));
 const manifest=JSON.parse(fs.readFileSync(path.join(out,'manifest.json'),'utf8'));
 const cssReport=JSON.parse(fs.readFileSync(path.join(out,'wiki-css-validation.json'),'utf8'));
 const cssSource=fs.readFileSync(path.join(root,'src/tree.css'),'utf8').replace(/\r\n/g,'\n');
 if(!cssReport.passed||cssReport.css_sha256!==require('crypto').createHash('sha256').update(cssSource).digest('hex'))throw Error('Missing or stale BWiki CSS parse validation');
 const parsedCss=fs.readFileSync(path.join(out,'site-parsed-tree.css'),'utf8').replace(/\r\n/g,'\n');
 // Remote image availability is reported separately; geometry/interaction checks
 // use local vehicle slots and don't require downloading site media.
 await p.route('https://**/*',route=>route.abort());
 for(const [key,tree] of Object.entries(manifest.trees)){
  for(const viewport of [1500,390]){
   await p.setViewportSize({width:viewport,height:viewport===390?844:1000});
   await p.goto(pathToFileURL(path.join(root,'work/preview/production',key+'.html')).href);
   if(!await p.locator('style').evaluateAll((a,css)=>a.some(e=>e.textContent.includes(css)),parsedCss))throw Error('Preview must use BWiki-parsed CSS '+key);
   await p.waitForFunction(()=>document.querySelector('.wtt-filters')&&document.querySelector('.wtt-results'));
   if(await p.locator('.wtt-search-hint').count())throw Error('hint '+key);
   if(await p.locator('.wtt-extra').count())throw Error('data notes remain '+key);
   const version=p.locator('.wtt-toolbar > .wtt-version');
   if(await version.textContent()!=='游戏版本 '+manifest.game_version)throw Error('game version '+key);
   if(!await version.isVisible())throw Error('hidden game version '+key);
   if(!await version.evaluate(e=>Math.abs(e.getBoundingClientRect().right-(e.parentElement.getBoundingClientRect().right-parseFloat(getComputedStyle(e.parentElement).paddingRight)))<2))throw Error('version right alignment '+key);
   if(await p.locator('.wtt-card').count()!==tree.visible)throw Error('cards '+key);
   const size=await p.locator('.wtt-card:visible').first().evaluate(e=>{const r=e.getBoundingClientRect();return {w:r.width,h:r.height};});
   if(Math.abs(size.w-120)>1||Math.abs(size.h-48)>1)throw Error('card scaling '+key+' '+viewport+' '+JSON.stringify(size));
   if(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('page overflow '+key);
   const data=JSON.parse(fs.readFileSync(path.join(out,'pages',key+'_tree.json'),'utf8'));
   const expectedIcons=Object.values(data.presentation).filter(x=>x.type_key).length;
   if(await p.locator('.wtt-type img[src$=".svg"]').count()!==expectedIcons)throw Error('SVG icon coverage '+key);
   if(await p.locator('.wtt').evaluate(e=>e.textContent.includes('{{WTJ/type-icon')))throw Error('unexpanded icon template '+key);
   const collisions=await p.evaluate(()=>{
    const board=document.querySelector('.wtt-board'),r=board.getBoundingClientRect(),nodes=[...board.querySelectorAll('.wtt-node')].map(n=>n.getBoundingClientRect());
    const bad=[];
    for(const line of board.querySelectorAll('.wtt-routed-line')){
     const v=line.getAttribute('d').match(/-?[0-9]+(?:[.][0-9]+)?/g).map(Number);
     for(let i=0;i<v.length-2;i+=2){const [x,y,xx,yy]=v.slice(i,i+4);
      for(const n of nodes){const a=n.left-r.left,b=n.top-r.top,c=n.right-r.left,d=n.bottom-r.top;
       if(x===xx?(a<x&&x<c&&Math.max(Math.min(y,yy),b)<Math.min(Math.max(y,yy),d)):(b<y&&y<d&&Math.max(Math.min(x,xx),a)<Math.min(Math.max(x,xx),c)))bad.push(line.dataset.from+'>'+line.dataset.to);
      }
     }
    }return bad;
   });
   if(collisions.length)throw Error('research arrow card collision '+key+' '+JSON.stringify(collisions));
   await p.locator('body').evaluate(e=>e.style.fontFamily='Georgia, serif');
   if(!(await p.locator('.wtt-name').first().evaluate(e=>getComputedStyle(e).fontFamily)).includes('Georgia'))throw Error('font '+key);
   const role=p.getByLabel('类别',{exact:true}),options=await role.locator('option').evaluateAll(a=>a.map(e=>e.value));
   for(const value of options.filter(Boolean)){
    await role.selectOption(value);
    const active=p.locator('.wtt-card:not(.wtt-filtered-card)');
    if(!await active.count()||await active.evaluateAll((a,v)=>a.some(e=>e.dataset.role!==v),value))throw Error('role '+key);
   }
   await role.selectOption('');
   // Scroll far enough that the original toolbar position is outside the viewport.
   await p.evaluate(()=>{const tree=document.querySelector('.wtt'),footer=document.createElement('div');footer.id='qa-footer';footer.style.height='1000px';document.body.appendChild(footer);scrollTo(0,tree.getBoundingClientRect().top+scrollY+Math.min(400,tree.offsetHeight-tree.querySelector('.wtt-toolbar').offsetHeight-60));});
   const sticky=await p.locator('.wtt-toolbar').evaluate(e=>{const r=e.getBoundingClientRect();return {top:r.top,bottom:r.bottom};});
   if(Math.abs(sticky.top)>1||sticky.bottom>(viewport===390?844:1000))throw Error('sticky toolbar '+key+' '+viewport+' '+JSON.stringify(sticky));
   await p.locator('.wtt-br-filter summary').click();
   if(!await p.getByLabel('历史权重下限',{exact:true}).isVisible())throw Error('sticky BR controls '+key);
   await p.locator('.wtt-br-filter summary').click();
   const search=p.getByLabel('搜索载具',{exact:true}),first=await p.locator('.wtt-card').first().getAttribute('data-unit');
   await search.fill(first);if(!await p.locator('.wtt-card:not(.wtt-filtered-card)').count())throw Error('search '+key);await search.fill('');
   const groundMode=p.locator('.wtt-mode[data-mode="grb"]');
   if(data.branch==='aviation'){
    if(await groundMode.count()!==1||await groundMode.textContent()!=='陆战历史')throw Error('ground RB mode '+key);
    await groundMode.click();
    if(await p.locator('.wtt').getAttribute('data-mode')!=='grb')throw Error('ground RB switching '+key);
    if(!await p.locator('.wtt-card:visible .wtt-br-grb').first().isVisible())throw Error('ground RB display '+key);
    await p.locator('.wtt-br-filter summary').click();
    const groundSlider=p.getByLabel('陆战历史权重下限',{exact:true});
    await groundSlider.fill('1');await groundSlider.dispatchEvent('input');
    const groundThreshold=+(await groundSlider.getAttribute('aria-valuetext'));
    const groundMatches=p.locator('.wtt-card:not(.wtt-filtered-card)');
    if(!await groundMatches.count()||await groundMatches.evaluateAll((a,t)=>a.some(e=>+e.querySelector('.wtt-br-grb').textContent<t),groundThreshold))throw Error('ground RB filtering '+key);
    if(await groundMatches.count()>=tree.visible)throw Error('ground RB filter did not narrow results '+key);
    await p.locator('.wtt-results button').click();await p.mouse.click(1,1);
    await p.locator('.wtt-mode[data-mode="rb"]').click();
   }else if(await groundMode.count()||await p.locator('.wtt-br-grb').count())throw Error('ground RB on non-aircraft tree '+key);
   await p.evaluate(()=>{scrollTo(0,0);document.getElementById('qa-footer').remove();});
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
   results.push({key,viewport,cards:tree.visible,filter:true,br:true,stickyToolbar:true,groundRB:data.branch==='aviation',groups:true,width:true,font:true});
  }
 }
 if(errors.length)throw Error(JSON.stringify(errors));
 fs.writeFileSync(path.join(out,'browser-validation.json'),JSON.stringify({passed:true,remoteMediaBlockedForDeterministicInteractionChecks:true,liveWikiImportVerified:false,results},null,2));
 console.log(JSON.stringify({passed:true,trees:Object.keys(manifest.trees).length,viewports:results.length,errors}));
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
