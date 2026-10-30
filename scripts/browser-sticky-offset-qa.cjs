/* Regression: site navigation must never cover any tree mode button. */
const fs=require('fs'),path=require('path');
const {chromium}=require(path.join(process.env.WTW_NODE_MODULES||'node_modules','playwright'));
const root=path.resolve(__dirname,'..'),out=path.join(root,'wiki/production');
(async()=>{const browser=await chromium.launch({channel:'msedge',headless:true});try{
 const p=await browser.newPage(),results=[],errors=[];p.on('pageerror',e=>errors.push(e.message));
 await p.route('**/*',r=>r.abort());
 const runtime=fs.readFileSync(path.join(out,'pages/tree.js'),'utf8');
 for(const key of ['germany_aviation','usa_army']){
  const source=fs.readFileSync(path.join(root,'work/preview/production',key+'.html'),'utf8');
  const fixture=source.replace('</style>','</style><style>.wiki-nav{position:fixed;top:0;left:0;width:100%;height:50px;background:#36424e;color:white;z-index:9999}@media(max-width:600px){.wiki-nav{display:none}}</style><nav class="wiki-nav">Site navigation</nav><div style="height:120px"></div>')
   .replace(/<script src="[^"]*tree.js"><\/script>/,'<script>'+runtime+'</script>');
  await p.setViewportSize({width:1500,height:844});await p.setContent(fixture);
  await p.waitForSelector('.wtt-filters');await p.evaluate(()=>scrollTo(0,650));
  async function check(top,label){
   await p.waitForFunction(t=>Math.abs(document.querySelector('.wtt-toolbar').getBoundingClientRect().top-t)<1,top);
   for(const button of await p.locator('.wtt-mode').all()){
    const hit=await button.evaluate(e=>{const r=e.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight&&e.contains(document.elementFromPoint(r.left+r.width/2,r.top+r.height/2));});
    if(!hit)throw Error(key+' mode obscured: '+label+' '+await button.textContent());
    const mode=await button.getAttribute('data-mode');await button.click();
    if(await p.locator('.wtt').getAttribute('data-mode')!==mode)throw Error('Mode click failed '+label);
   }
   results.push({key,scenario:label,top,allModesVisibleAndClickable:true});
  }
  await check(50,'desktop fixed navigation');
  await p.locator('.wiki-nav').evaluate(e=>e.style.height='75px');await check(75,'header height change / zoom');
  await p.setViewportSize({width:390,height:844});await check(0,'mobile navigation hidden');
  await p.setViewportSize({width:1500,height:844});await check(75,'resize back to desktop');
  await p.locator('.wiki-nav').evaluate(e=>e.style.position='relative');await check(0,'navigation no longer fixed');
  await p.locator('.wiki-nav').evaluate(e=>e.style.position='fixed');await check(75,'navigation becomes fixed');
  if(key==='germany_aviation')await p.screenshot({path:path.join(out,'sticky-navigation-preview.png')});
 }
 if(errors.length)throw Error(JSON.stringify(errors));
 fs.writeFileSync(path.join(out,'sticky-offset-validation.json'),JSON.stringify({passed:true,results},null,2));
 console.log(JSON.stringify({passed:true,scenarios:results.length,errors}));
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
