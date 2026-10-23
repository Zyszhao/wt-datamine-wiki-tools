const fs=require('fs'),path=require('path'),{pathToFileURL}=require('url');
const WORK=path.resolve(__dirname,'../work');
let playwright;
try { playwright=require('playwright'); } catch(error) {
 if(error.code!=='MODULE_NOT_FOUND'||!process.env.WTW_NODE_MODULES)throw error;
 playwright=require(path.join(process.env.WTW_NODE_MODULES,'playwright'));
}
const {chromium}=playwright;
(async()=>{const browser=await chromium.launch({headless:true,channel:'msedge'});try{
 const p=await browser.newPage();const errors=[];p.on('pageerror',e=>errors.push(e.message));const results=[];
 for(const [name,width,height] of [['desktop',1500,1000],['mobile',390,844]]){
  await p.setViewportSize({width,height});await p.goto(pathToFileURL(path.join(WORK,'preview/index.html')).href);await p.waitForFunction(()=>document.querySelector('.wtt').dataset.ready==='1');
  if(await p.locator('.wtt-card').count()!==154)throw Error('vehicle count');
  const overflow=await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth);if(overflow)throw Error('page overflow');
  await p.screenshot({path:path.join(WORK,'reports',name+'-top.png')});
  if(name==='desktop'){
   const group=p.locator('[data-node="us_sherman_group"] .wtt-group');await group.click();
   if(await group.getAttribute('aria-expanded')!=='true')throw Error('folder click');
   await p.screenshot({path:path.join(WORK,'reports/folder-open.png')});
   await p.keyboard.press('Escape');await p.mouse.move(0,0);
   if(await group.getAttribute('aria-expanded')!=='false')throw Error('folder Escape');
   await group.focus();await p.keyboard.press('Enter');if(await group.getAttribute('aria-expanded')!=='true')throw Error('folder keyboard');await p.keyboard.press('Escape');
  }
  const popupGroup=p.locator('[data-node="us_sherman_group"] .wtt-group');await popupGroup.scrollIntoViewIfNeeded();await popupGroup.click();
  await popupGroup.locator('.wtt-popup').click({position:{x:2,y:2}});if(await popupGroup.getAttribute('aria-expanded')!=='true')throw Error('popup padding must not close folder');
  await p.mouse.click(4,4);if(await popupGroup.getAttribute('aria-expanded')!=='false')throw Error('outside click must close folder');
  await p.locator('.wtt-card[data-unit="us_m5a1_stuart_canadian_5st_arm"]').hover();
  const hover=await p.locator('.wtt-card[data-unit="us_m5a1_stuart_canadian_5st_arm"] .wtt-name').evaluate(e=>{var s=getComputedStyle(e);return {height:e.getBoundingClientRect().height,card:e.parentElement.getBoundingClientRect().height,background:s.backgroundColor,whiteSpace:s.whiteSpace};});
  if(hover.whiteSpace!=='nowrap'||hover.background!=='rgba(0, 0, 0, 0)'||hover.height>hover.card/2)throw Error('name overlay regression');
  const mode=p.locator('.wtt-mode[data-mode="ab"]');await mode.click();if(await p.locator('.wtt').getAttribute('data-mode')!=='ab')throw Error('mode');
  if(await p.locator('[data-unit="us_m8_scott_snowball"],[data-unit="us_m551_football"],[data-unit="us_m18_hellcat_black_cat_race"]').count())throw Error('special vehicles leaked');
  const categoryOptions=await p.getByLabel('类别',{exact:true}).locator('option').allTextContents();if(categoryOptions.length!==6)throw Error('five game categories');
  const alignment=await p.locator('.wtt-header').evaluate(e=>{var b=e.parentElement.getBoundingClientRect(),h=e.getBoundingClientRect(),second=e.children[1].getBoundingClientRect(),divider=e.parentElement.querySelector('.wtt-divider').getBoundingClientRect();return Math.abs(h.left-b.left)<1&&Math.abs(h.right-b.right)<1&&Math.abs(second.left-divider.left)<1;});if(!alignment)throw Error('header split misaligned');
  if(!await p.locator('.wtt-folder-premium').count())throw Error('premium folder missing');
  const premiumSource=await p.locator('.wtt-folder-premium .wtt-file-background img').first().getAttribute('src');const normalSource=await p.locator('.wtt-folder:not(.wtt-folder-premium) .wtt-file-background img').first().getAttribute('src');if(!premiumSource.includes('folder_prem.png')||!normalSource.includes('folder.png'))throw Error('premium folder File asset');
  await p.locator('.wtt-br-filter summary').click();if(await p.locator('input[type=range]').count()!==6)throw Error('three BR ranges');
  const lower=p.getByLabel('历史权重下限',{exact:true});await lower.fill('5');await lower.dispatchEvent('input');
  const threshold=+(await lower.getAttribute('aria-valuetext'));const incorrect=await p.locator('.wtt-card:not(.wtt-filtered-card)').evaluateAll((a,t)=>a.some(c=>+c.querySelector('.wtt-br-rb').textContent<t),threshold);if(incorrect)throw Error('range filtering');
  await lower.fill('0');await lower.dispatchEvent('input');await p.screenshot({path:path.join(WORK,'reports',name+'-br-slider.png')});await p.mouse.click(4,4);
  const input=p.locator('input[type=search]');await input.fill('us_m2a4');if(await p.locator('.wtt-node:not(.wtt-filtered)').count()!==2)throw Error('search');await input.fill('');
  await p.getByLabel('等级',{exact:true}).selectOption('1');if(await p.locator('.wtt-node:not(.wtt-filtered)').count()!==16)throw Error('rank filter');await p.getByLabel('等级',{exact:true}).selectOption('');
  await p.getByLabel('类别',{exact:true}).selectOption('轻型坦克');
  if(await p.locator('.wtt-card:not(.wtt-filtered-card):not([data-role="轻型坦克"])').count())throw Error('nonmatching folder member');
  if(!await p.locator('.wtt-node.wtt-filtered').count())throw Error('category must mark nonmatches');
  if(await p.locator('.wtt-card[data-unit="us_m18_hellcat_kit_3rank"]').evaluate(e=>e.classList.contains('wtt-filtered-card')))throw Error('matching mixed folder member hidden');
  if(!await p.locator('.wtt-card[data-unit="us_m4a3e8_76w_sherman_kit_3rank"]').evaluate(e=>e.classList.contains('wtt-filtered-card')))throw Error('nonmatching mixed folder member visible');
  const context=await p.locator('.wtt-card[data-unit="us_m4a3e8_76w_sherman_kit_3rank"]').evaluate(e=>getComputedStyle(e).opacity);if(+context>=.5)throw Error('tree nonmatch not dimmed');
  const allNodesVisible=await p.locator('.wtt-node').evaluateAll(a=>a.every(e=>getComputedStyle(e).visibility==='visible'&&getComputedStyle(e).display!=='none'));if(!allNodesVisible)throw Error('tree context removed');
  const matched=await p.locator('.wtt-card:not(.wtt-filtered-card)').count();if(+await p.locator('.wtt').getAttribute('data-matches')!==matched)throw Error('result count');
  await p.locator('.wtt').scrollIntoViewIfNeeded();await p.screenshot({path:path.join(WORK,'reports',name+'-filtered-tree.png')});
  await p.locator('.wtt-view-toggle').click();if(await p.locator('.wtt-card:visible').count()!==matched)throw Error('list should only show matches');
  if(await p.locator('.wtt-short-arrow:visible,.wtt-folder:visible').count())throw Error('list folder decoration');
  await p.locator('.wtt').scrollIntoViewIfNeeded();await p.screenshot({path:path.join(WORK,'reports',name+'-filtered-list.png')});
  const listRects=await p.locator('.wtt-card:visible').evaluateAll(a=>a.map(e=>{var r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height};}));
  for(let i=0;i<listRects.length;i++)for(let j=i+1;j<listRects.length;j++){const a=listRects[i],b=listRects[j];if(a.x<b.x+b.w-1&&a.x+a.w>b.x+1&&a.y<b.y+b.h-1&&a.y+a.h>b.y+1)throw Error('list overlap');}
  await p.locator('.wtt-results button').click();if(await p.locator('.wtt-card:visible').count()!==154)throw Error('reset in list');
  const regularRows=await p.locator('.wtt-card:visible').evaluateAll(a=>{var first=a[0].getBoundingClientRect(),second=a[1].getBoundingClientRect();var pitch=second.left-first.left,columns=getComputedStyle(a[0].closest('.wtt-board')).gridTemplateColumns.split(' ').length;return a.every((e,i)=>{var r=e.getBoundingClientRect();return Math.abs(r.left-(first.left+(i%columns)*pitch))<1;});});if(!regularRows)throw Error('group not flattened into grid');
  await p.locator('.wtt').scrollIntoViewIfNeeded();await p.screenshot({path:path.join(WORK,'reports',name+'-flat-list.png')});
  await input.fill('no_such_vehicle_123456');if(await p.locator('.wtt-card:visible').count()!==0||!await p.locator('.wtt-no-results').count())throw Error('empty list');
  await p.locator('.wtt-results button').click();await p.locator('.wtt-view-toggle').click();
  if(await p.locator('.wtt-filter-active').count())throw Error('reset left highlights');
  await p.locator('[data-node="us_sherman_group"] .wtt-group').click();if(await p.locator('[data-node="us_sherman_group"] .wtt-group').getAttribute('aria-expanded')!=='true')throw Error('folder broken after list roundtrip');await p.keyboard.press('Escape');
  const arrowHeads=await p.locator('.wtt-arrow').evaluateAll(a=>a.every(e=>{var s=getComputedStyle(e,'::before');var h=getComputedStyle(e,'::after');return s.bottom==='8px'&&Math.abs(parseFloat(h.borderTopWidth)-9)<1;}));if(!arrowHeads)throw Error('arrow shaft/head regression');
  const gold=await p.locator('.wtt-board').evaluate(e=>getComputedStyle(e).backgroundImage);if(!gold.includes('61, 54, 35'))throw Error('premium pane background');
  const broken=await p.locator('img').evaluateAll(a=>a.filter(x=>!x.complete||!x.naturalWidth).map(x=>x.src));results.push({name,width,vehicles:154,pageOverflow:overflow,brokenImages:broken,arrowHeads,hoverOverlayAbsent:true,outsideClickCloses:true,memberFilterCorrect:true,treeContextPreserved:true,flatListGrid:true,filterReset:true,emptyResults:true,premiumGold:true,headerAligned:true,gameCategories:5,threeModeBRRanges:true,premiumFolderAsset:true,specialVariantsExcluded:true});
 }
 await p.setViewportSize({width:1900,height:1000});await p.goto(pathToFileURL(path.join(WORK,'preview/index.html')).href);await p.waitForFunction(()=>document.querySelector('.wtt').dataset.ready==='1');
 for(const width of [1500,1100,950,900,680,358]){await p.locator('.wtt').evaluate((e,w)=>{e.parentElement.style.width=w+'px';},width);await p.waitForTimeout(100);const metrics=await p.locator('.wtt').evaluate(e=>{var root=e.getBoundingClientRect(),board=e.querySelector('.wtt-board').getBoundingClientRect(),scroll=e.querySelector('.wtt-scroll').getBoundingClientRect();return {root:root.width,board:board.width,offset:board.left-scroll.left,overflow:document.documentElement.scrollWidth>innerWidth};});if(Math.abs(metrics.root-Math.min(width,1330))>1||Math.abs(metrics.board-Math.max(950,Math.min(width,1330)))>1||Math.abs(metrics.offset)>1||metrics.overflow)throw Error('adaptive container width/gutter regression '+JSON.stringify(metrics));}
 await p.locator('.wtt').evaluate(e=>e.parentElement.style.width='900px');await p.screenshot({path:path.join(WORK,'reports/wiki-narrow-column.png')});
 await p.setViewportSize({width:1200,height:900});await p.goto(pathToFileURL(path.join(WORK,'../wiki/INSTALL.html')).href);
 const installBoxes=p.locator('textarea');if(await installBoxes.count()!==2)throw Error('installer needs site script and styles');
 const expectedFiles=['tree_testing.js','styles.wiki'];for(let i=0;i<2;i++){const expected=fs.readFileSync(path.join(WORK,'../wiki/pages',expectedFiles[i]),'utf8').replace(/\r\n/g,'\n');if(await installBoxes.nth(i).inputValue()!==expected)throw Error('installer source mismatch');}
 await p.locator('button.copy').first().click();await p.waitForFunction(()=>document.querySelector('.copy-status').textContent.trim().length>0);
 await p.screenshot({path:path.join(WORK,'reports/installation-helper.png')});
 if(errors.length)throw Error(JSON.stringify(errors));
 fs.writeFileSync(path.join(WORK,'reports/browser-qa.json'),JSON.stringify({results,errors,scope:'Offline Lua HTML, CSS and isolated JavaScript; remote images may depend on network. Live MW sanitization/memory not verified.'},null,2));console.log(JSON.stringify(results));
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
