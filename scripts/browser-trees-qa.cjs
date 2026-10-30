/* Same browser script, different JSON-derived HTML. No per-tree runtime. */
const fs=require('fs'),path=require('path'),{pathToFileURL}=require('url');
const {chromium}=require(path.join(process.env.WTW_NODE_MODULES||'node_modules','playwright'));
const root=path.resolve(__dirname,'..');
(async()=>{const browser=await chromium.launch({channel:'msedge',headless:true});try{
 const p=await browser.newPage();const results=[];
 for(const [key,count,base,roles] of [['china_aviation',91,818,3],['germany_boats',39,686,5]]){
  for(const viewport of [1500,390]){
   await p.setViewportSize({width:viewport,height:1000});await p.goto(pathToFileURL(path.join(root,'work/preview',key+'.html')).href);await p.waitForFunction(()=>document.querySelector('.wtt')?.dataset.ready==='1');
   await p.locator('img').evaluateAll(a=>a.forEach(e=>e.loading='eager'));await p.waitForFunction(()=>Array.from(document.images).every(e=>e.complete));
   const broken=await p.locator('img').evaluateAll(a=>a.filter(e=>!e.naturalWidth).map(e=>e.src));if(broken.length)throw Error(JSON.stringify(broken));
   if(await p.locator('.wtt-card').count()!==count)throw Error('count');
   const metrics=await p.locator('.wtt').evaluate(e=>{const b=e.querySelector('.wtt-board').getBoundingClientRect(),r=e.getBoundingClientRect(),s=e.querySelector('.wtt-scroll').getBoundingClientRect();return {root:r.width,board:b.width,left:b.left-s.left,overflow:document.documentElement.scrollWidth>innerWidth}});
   if(metrics.overflow||Math.abs(metrics.board-Math.max(base,metrics.root))>1||Math.abs(metrics.left)>1)throw Error('width '+JSON.stringify(metrics));
   const cardSize=await p.locator('.wtt-card').first().evaluate(e=>{const r=e.getBoundingClientRect();return {width:r.width,height:r.height,font:getComputedStyle(e).fontFamily}});
   if(Math.abs(cardSize.width-120)>1||Math.abs(cardSize.height-48)>1)throw Error('cards must not scale '+JSON.stringify(cardSize));
   const edgeInset=await p.locator('.wtt-board').evaluate(e=>{const b=e.getBoundingClientRect();return Array.from(e.querySelectorAll('.wtt-node')).every(n=>{const r=n.getBoundingClientRect();return r.left-b.left>=11&&b.right-r.right>=11})});
   if(!edgeInset)throw Error('unbalanced tree card edge');
   await p.locator('body').evaluate(e=>e.style.fontFamily='Georgia, serif');
   if(!(await p.locator('.wtt-name').first().evaluate(e=>getComputedStyle(e).fontFamily)).includes('Georgia'))throw Error('site font not inherited');
   if(!(await p.getByLabel('搜索载具',{exact:true}).evaluate(e=>getComputedStyle(e).fontFamily)).includes('Georgia'))throw Error('control font not inherited');
   await p.locator('body').evaluate(e=>e.style.fontFamily='');
   if(await p.getByLabel('类别',{exact:true}).locator('option').count()!==roles+1)throw Error('wrong categories');
   const options=await p.getByLabel('类别',{exact:true}).locator('option').allTextContents();
   for(const role of options.slice(1)){
    await p.getByLabel('类别',{exact:true}).selectOption(role);
    const matching=await p.locator('.wtt-card:not(.wtt-filtered-card)').count();if(!matching||matching>=count)throw Error('category count');
    if(await p.locator('.wtt-card:not(.wtt-filtered-card)').evaluateAll((a,r)=>a.some(e=>e.dataset.role!==r),role))throw Error('category mismatch');
   }
   await p.getByLabel('类别',{exact:true}).selectOption('');
   await p.screenshot({path:path.join(root,'work/reports',key+'-'+viewport+'.png')});
   const search=p.getByLabel('搜索载具',{exact:true}),first=await p.locator('.wtt-card').first().getAttribute('data-unit');await search.fill(first);
   if(!(await p.locator('.wtt-card:not(.wtt-filtered-card)').count()))throw Error('search');await search.fill('');
   await p.locator('.wtt-br-filter summary').click();if(await p.locator('input[type=range]').count()!==(key==='china_aviation'?8:6))throw Error('ranges');
   const slider=p.getByLabel('历史权重下限',{exact:true});await slider.fill('2');await slider.dispatchEvent('input');
   const threshold=+(await slider.getAttribute('aria-valuetext'));
   if(await p.locator('.wtt-card:not(.wtt-filtered-card)').evaluateAll((a,t)=>a.some(e=>+e.querySelector('.wtt-br-rb').textContent<t),threshold))throw Error('br range');
   await p.locator('.wtt-results button').click();await p.mouse.click(1,1);
   await p.locator('.wtt-view-toggle').click();if(await p.locator('.wtt-card:visible').count()!==count)throw Error('list '+key+' '+viewport+' visible='+await p.locator('.wtt-card:visible').count()+' state='+await p.locator('.wtt').getAttribute('class'));
   const rects=await p.locator('.wtt-card:visible').evaluateAll(a=>a.map(e=>{let r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}}));
   const columns=await p.locator('.wtt-board').evaluate(e=>getComputedStyle(e).gridTemplateColumns.split(' ').length);
   const listBounds=await p.locator('.wtt-board').boundingBox();
   if(Math.abs(rects[0].x-listBounds.x-12)>1||Math.abs(listBounds.x+listBounds.width-rects[columns-1].x-120-12)>1)throw Error('list row trailing whitespace');
   for(let i=0;i<rects.length;i++)for(let j=i+1;j<rects.length;j++){let a=rects[i],b=rects[j];if(a.x<b.x+b.w-1&&a.x+a.w>b.x+1&&a.y<b.y+b.h-1&&a.y+a.h>b.y+1)throw Error('list overlap');}
   await search.fill('no_such_unit_12345');if(await p.locator('.wtt-card:visible').count())throw Error('empty search');await p.locator('.wtt-results button').click();
   await p.locator('.wtt-view-toggle').click();
   if(await p.locator('.wtt-group').count()){await p.locator('.wtt-group').first().click();await p.mouse.click(1,1);if(await p.locator('.wtt-open').count())throw Error('outside close');}
   results.push({key,viewport,count,categories:roles,width:metrics,cardSize,siteFontInherited:true,controlFontInherited:true,brokenImages:broken,filterAndList:true});
  }
 }
 await p.goto(pathToFileURL(path.join(root,'wiki/MULTI-TREE.html')).href);if(await p.locator('textarea').count()!==8)throw Error('helper count');
 await p.locator('button.copy').first().click();await p.waitForFunction(()=>document.querySelector('.copy-status').textContent.trim().length>0);
 fs.writeFileSync(path.join(root,'work/reports/multi-tree-browser.json'),JSON.stringify({passed:true,results},null,2));console.log(JSON.stringify(results));
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
