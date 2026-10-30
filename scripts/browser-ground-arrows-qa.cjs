const fs=require('fs'),path=require('path'),{pathToFileURL}=require('url');
const {chromium}=require(path.join(process.env.WTW_NODE_MODULES||'node_modules','playwright'));
const root=path.resolve(__dirname,'..');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const p=await browser.newPage(),results=[],errors=[];
  p.on('pageerror',e=>errors.push(e.message));
  const tree=JSON.parse(fs.readFileSync(path.join(root,'work/exports/usa_army_svg_arrows.json'),'utf8'));
  for(const viewport of [1500,390]){
   await p.setViewportSize({width:viewport,height:1000});
   await p.goto(pathToFileURL(path.join(root,'work/preview/usa_army_svg_arrows.html')).href);
   await p.waitForFunction(()=>document.querySelector('.wtt')?.dataset.ready==='1');
   await p.waitForFunction(()=>Array.from(document.images).every(i=>i.complete));
   const geometry=await p.evaluate(()=>{
    const root=document.querySelector('.wtt'),board=root.querySelector('.wtt-board'),r=board.getBoundingClientRect();
    const cards=[...board.querySelectorAll('.wtt-node')].map(n=>({id:n.dataset.node,r:n.getBoundingClientRect()}));
    const collisions=[],outside=[];
    for(const line of board.querySelectorAll('.wtt-routed-line')){
     const v=line.getAttribute('d').match(/-?\d+(?:\.\d+)?/g).map(Number);
     for(let i=0;i<v.length-2;i+=2){
      const [x,y,xx,yy]=v.slice(i,i+4);
      if(Math.min(x,xx)<0||Math.max(x,xx)>r.width||Math.min(y,yy)<0||Math.max(y,yy)>r.height)outside.push(line.dataset.from);
      for(const {id,r:c} of cards){
       const a=c.left-r.left,b=c.top-r.top,z=a+c.width,d=b+c.height;
       if(x===xx?(a<x&&x<z&&Math.max(Math.min(y,yy),b)<Math.min(Math.max(y,yy),d)):(b<y&&y<d&&Math.max(Math.min(x,xx),a)<Math.min(Math.max(x,xx),z)))collisions.push({from:line.dataset.from,to:line.dataset.to,node:id});
      }
     }
    }
    return {collisions,outside,broken:[...document.images].filter(i=>!i.naturalWidth).map(i=>i.src),pageOverflow:document.documentElement.scrollWidth>innerWidth};
   });
   if(geometry.collisions.length||geometry.outside.length||geometry.broken.length||geometry.pageOverflow)throw Error(JSON.stringify({viewport,...geometry}));
   const pairs=await p.locator('.wtt-routed-line').evaluateAll(a=>a.map(e=>e.dataset.from+'>'+e.dataset.to).sort());
   if(JSON.stringify(pairs)!==JSON.stringify(tree.layout.arrows.map(e=>e.from+'>'+e.to).sort()))throw Error('edge identity');
   if(await p.locator('.wtt-routed-tip').count()!==66||await p.locator('.wtt-card').count()!==154)throw Error('count');
   await p.screenshot({path:path.join(root,'work/reports/usa_army-svg-arrows-'+viewport+'.png'),fullPage:true});
   const search=p.getByLabel('搜索载具',{exact:true});await search.fill('us_m1a2_abrams');
   if(await p.locator('.wtt-card:not(.wtt-filtered-card)').count()!==1)throw Error('filter');
   await search.fill('');await p.locator('.wtt-view-toggle').click();
   if(await p.locator('.wtt-card:visible').count()!==154||await p.locator('.wtt-lines:visible').count())throw Error('list');
   await p.locator('.wtt-view-toggle').click();
   const group=p.locator('[data-node="us_sherman_group"] .wtt-group');await group.scrollIntoViewIfNeeded();await group.click();
   if(await group.getAttribute('aria-expanded')!=='true')throw Error('group');
   const popupPairs=await p.locator('.wtt-popup-line').evaluateAll(a=>a.map(e=>e.dataset.from+'>'+e.dataset.to).sort());
   if(JSON.stringify(popupPairs)!==JSON.stringify(tree.layout.internal_edges.map(e=>e.from+'>'+e.to).sort()))throw Error('popup edge identity');
   const popupGeometry=await group.locator('.wtt-popup').evaluate(popup=>{
    const bounds=popup.getBoundingClientRect(),cards=[...popup.querySelectorAll('.wtt-card')];
    return [...popup.querySelectorAll('.wtt-popup-line')].map(line=>{
     const tip=popup.querySelector('.wtt-popup-tip[data-to="'+line.dataset.to+'"]'),v=tip.getAttribute('d').match(/-?[0-9]+(?:[.][0-9]+)?/g).map(Number),a=cards.find(c=>c.dataset.unit===line.dataset.from).getBoundingClientRect(),b=cards.find(c=>c.dataset.unit===line.dataset.to).getBoundingClientRect();
     const stem=line.getAttribute('d').match(/-?[0-9]+(?:[.][0-9]+)?/g).map(Number);
     return {from:line.dataset.from,to:line.dataset.to,startGap:stem[1]-(a.bottom-bounds.top-1),endGap:(b.top-bounds.top-1)-v[1],centerError:Math.abs(v[0]-(b.left-bounds.left-1+b.width/2))};
    });
   });
   if(popupGeometry.some(e=>e.startGap!==4||e.endGap!==4||e.centerError!==0))throw Error('popup geometry '+JSON.stringify(popupGeometry));
   await group.screenshot({path:path.join(root,'work/reports/sherman-popup-'+viewport+'.png')});
   await p.screenshot({path:path.join(root,'work/reports/sherman-popup-page-'+viewport+'.png')});
   await p.keyboard.press('Escape');
   const unlinked=p.locator('[data-node="us_kit_3rank_group"] .wtt-group');await unlinked.scrollIntoViewIfNeeded();await unlinked.click();
   if(await unlinked.locator('.wtt-popup-line').count())throw Error('invented premium group edge');
   await p.keyboard.press('Escape');
   results.push({viewport,cards:154,routedEdges:pairs.length,internalEdges:17,...geometry,filterListFolder:true});
  }
  if(errors.length)throw Error(JSON.stringify(errors));
  fs.writeFileSync(path.join(root,'work/reports/ground-arrow-browser.json'),JSON.stringify({passed:true,results},null,2));
  console.log(JSON.stringify({passed:true,results}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
