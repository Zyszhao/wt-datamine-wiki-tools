/* Local rendered Lua output: real coordinates, branched edges and responsive geometry. */
const fs=require('fs'),path=require('path'),{pathToFileURL}=require('url');
const {chromium}=require(path.join(process.env.WTW_NODE_MODULES||'node_modules','playwright'));
const root=path.resolve(__dirname,'..');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage(),results=[],errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  const keys=fs.readdirSync(path.join(root,'work/exports/trees')).filter(n=>n.endsWith('_helicopters_tree_testing.json'));
  for(const filename of keys){
   const tree=JSON.parse(fs.readFileSync(path.join(root,'work/exports/trees',filename),'utf8'));
   for(const width of [1500,390]){
    await page.setViewportSize({width,height:1000});
    await page.goto(pathToFileURL(path.join(root,'work/preview',tree.id+'.html')).href);
    await page.waitForFunction(()=>document.querySelector('.wtt')?.dataset.ready==='1');
    await page.waitForFunction(()=>Array.from(document.images).every(i=>i.complete));
    const geometry=await page.evaluate(()=>{
     const root=document.querySelector('.wtt'),board=root.querySelector('.wtt-board'),bounds=board.getBoundingClientRect();
     const cards=Array.from(board.querySelectorAll('.wtt-node')).map(n=>({id:n.dataset.node,rect:n.getBoundingClientRect()}));
     const collisions=[],outside=[];
     for(const line of board.querySelectorAll('.wtt-routed-line')){
      const coords=line.getAttribute('d').match(/-?\d+(?:\.\d+)?/g).map(Number);
      for(let i=0;i<coords.length-2;i+=2){
       const x=coords[i],y=coords[i+1],xx=coords[i+2],yy=coords[i+3];
       if(Math.min(x,xx)<0||Math.max(x,xx)>bounds.width||Math.min(y,yy)<0||Math.max(y,yy)>bounds.height)outside.push(line.dataset.from+'>'+line.dataset.to);
       for(const {id,rect:r} of cards){
        const a=r.left-bounds.left,b=r.top-bounds.top,c=a+r.width,d=b+r.height;
        if(x===xx?(a<x&&x<c&&Math.max(Math.min(y,yy),b)<Math.min(Math.max(y,yy),d)):(b<y&&y<d&&Math.max(Math.min(x,xx),a)<Math.min(Math.max(x,xx),c)))collisions.push({from:line.dataset.from,to:line.dataset.to,node:id});
       }
      }
     }
     return {collisions,outside,broken:Array.from(document.images).filter(i=>!i.naturalWidth).map(i=>i.src),overflow:document.documentElement.scrollWidth>innerWidth,cards:cards.length,edges:board.querySelectorAll('.wtt-routed-line').length,tips:board.querySelectorAll('.wtt-routed-tip').length};
    });
    if(geometry.collisions.length||geometry.outside.length||geometry.broken.length||geometry.overflow)throw Error(tree.id+' '+width+' '+JSON.stringify(geometry));
    if(await page.locator('.wtt-card').count()!==tree.visible_count||geometry.edges!==tree.layout.arrows.length||geometry.tips!==geometry.edges)throw Error('missing card/edge '+tree.id);
    const emitted=await page.locator('.wtt-routed-line').evaluateAll(lines=>lines.map(e=>[e.dataset.from,e.dataset.to].join('>')).sort());
    if(JSON.stringify(emitted)!==JSON.stringify(tree.layout.arrows.map(e=>e.from+'>'+e.to).sort()))throw Error('edge identity '+tree.id);
    if(await page.locator('.wtt-requirement').count()!==1||!(await page.locator('.wtt-requirement').innerText()).includes('或'))throw Error('entry condition');
    if(width===390){
     const visible=await page.locator('.wtt-scroll').evaluate(e=>{const r=e.getBoundingClientRect();return [...e.querySelectorAll('.wtt-node')].some(n=>{const a=n.getBoundingClientRect();return a.left>=r.left&&a.right<=r.right;});});
     if(!visible)throw Error('mobile must initially show a full card '+tree.id);
    }
    for(const mode of ['ab','sb','rb']){await page.locator('.wtt-mode[data-mode='+mode+']').click();if(await page.locator('.wtt').getAttribute('data-mode')!==mode)throw Error('mode');}
    if(['usa_helicopters','france_helicopters','sweden_helicopters','israel_helicopters'].includes(tree.id))await page.screenshot({path:path.join(root,'work/reports',tree.id+'-'+width+'.png'),fullPage:true});
    const search=page.getByLabel('搜索载具',{exact:true});
    await search.fill(tree.columns[0].nodes[0].units[0]);
    if(!(await page.locator('.wtt-card:not(.wtt-filtered-card)').count()))throw Error('search');
    await search.fill('');await page.locator('.wtt-view-toggle').click();
    if(await page.locator('.wtt-card:visible').count()!==tree.visible_count)throw Error('list');
    await page.locator('.wtt-view-toggle').click();
    if(await page.locator('.wtt-group').count()){
     const group=page.locator('.wtt-group').first();await group.scrollIntoViewIfNeeded();await group.click();
     if(await group.getAttribute('aria-expanded')!=='true'||await group.locator('.wtt-card:visible').count()!==2)throw Error('folder');
     await page.keyboard.press('Escape');
    }
    results.push({tree:tree.id,viewport:width,visible:tree.visible_count,...geometry});
   }
  }
  if(errors.length)throw Error(JSON.stringify(errors));
  fs.writeFileSync(path.join(root,'work/reports/helicopter-browser.json'),JSON.stringify({passed:true,results},null,2));
  console.log(JSON.stringify({passed:true,trees:keys.length,viewports:results.length,visible:results.filter(r=>r.viewport===1500).reduce((n,r)=>n+r.visible,0)}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
