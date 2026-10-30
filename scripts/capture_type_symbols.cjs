/* Read-only official list icon evidence; outputs remain local. */
const fs=require('fs'),path=require('path');
const {chromium}=require(path.join(process.env.WTW_NODE_MODULES||'node_modules','playwright'));
(async()=>{
 const out=path.resolve(__dirname,'../work/research/type-symbols');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({channel:'msedge',headless:true}),branches=[];
 try{
  for(const branch of ['ground','aviation','helicopters','boats','ships']){
   const p=await browser.newPage(),url='https://wiki.warthunder.com/'+branch+'?v=l';
   await p.goto(url,{waitUntil:'domcontentloaded',timeout:60000});
   await p.waitForSelector('table svg use',{state:'attached',timeout:45000});
   const rows=await p.locator('table svg use').evaluateAll(es=>es.filter(e=>(e.getAttribute('href')||'').includes('/class_icon/')).map(e=>{
    const svg=e.closest('svg'),td=e.closest('td'),tr=e.closest('tr');
    return {href:e.getAttribute('href'),color:svg.getAttribute('color'),computedColor:getComputedStyle(e).color,viewBox:svg.getAttribute('viewBox'),width:svg.getAttribute('width'),height:svg.getAttribute('height'),role:td.textContent.trim(),unit:tr.querySelector('a[href^="/unit/"]')?.getAttribute('href'),markup:svg.outerHTML};
   }));
   if(!rows.length)throw Error('No class icons: '+branch);
   fs.writeFileSync(path.join(out,branch+'.html'),await p.content());branches.push({branch,url,rows});console.log(branch,rows.length);await p.close();
  }
  const resources=[...new Set(branches.flatMap(b=>b.rows.map(r=>r.href.split('#')[0])))];
  const context=await browser.newContext();
  for(const resource of resources){const r=await context.request.get('https://wiki.warthunder.com'+resource);if(!r.ok())throw Error(resource+' '+r.status());fs.writeFileSync(path.join(out,path.basename(resource)),await r.body());}
  const mappings=[...new Map(branches.flatMap(b=>b.rows.map(r=>{const v={branch:b.branch,role:r.role,href:r.href,color:r.color,viewBox:r.viewBox,width:r.width,height:r.height};return [JSON.stringify(v),v];}))).values()];
  fs.writeFileSync(path.join(out,'catalogue.json'),JSON.stringify({capturedAt:new Date().toISOString(),branches,resources,mappings},null,2));console.log(JSON.stringify({resources,mappings},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
