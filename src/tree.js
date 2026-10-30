/* Optional isolated enhancement; never writes to the Wiki. */
(function(){'use strict';
 // BWiki pins its desktop navigation after scrolling; mobile hides that bar.
 // Use a numeric inline offset: its CSS extension rejects custom-property var().
 var stickyPending=false,siteHeaderSelector='.wiki-nav,.wiki-header,#biliGameHeader,#mw-head';
 function updateStickyToolbars(){
  stickyPending=false;
  var headers=Array.from(document.querySelectorAll(siteHeaderSelector)).map(function(e){return {rect:e.getBoundingClientRect(),style:getComputedStyle(e)};});
  document.querySelectorAll('.wtt-toolbar').forEach(function(toolbar){
   var bounds=toolbar.getBoundingClientRect(),top=0;
   headers.forEach(function(h){var r=h.rect,s=h.style;if((s.position==='fixed'||s.position==='sticky')&&s.display!=='none'&&s.visibility!=='hidden'&&s.opacity!=='0'&&r.width>0&&r.height>0&&r.bottom>0&&r.top<=Math.max(0,parseFloat(s.top)||0)+1&&r.left<bounds.right&&r.right>bounds.left)top=Math.max(top,r.bottom);});
   var value=Math.ceil(top)+'px';if(toolbar.style.top!==value)toolbar.style.top=value;
  });
 }
 function scheduleStickyToolbars(){if(!stickyPending){stickyPending=true;requestAnimationFrame(updateStickyToolbars);}}
 window.addEventListener('scroll',scheduleStickyToolbars,{passive:true});window.addEventListener('resize',scheduleStickyToolbars);
 var watchedHeaders=new WeakSet();
 function watchSiteHeaders(){
  document.querySelectorAll(siteHeaderSelector).forEach(function(e){
   if(watchedHeaders.has(e))return;watchedHeaders.add(e);
   if(window.ResizeObserver)new ResizeObserver(scheduleStickyToolbars).observe(e);
   if(window.MutationObserver)new MutationObserver(scheduleStickyToolbars).observe(e,{attributes:true,attributeFilter:['class','style']});
  });updateStickyToolbars();
 }
 function init(scope){scope.querySelectorAll('.wtt').forEach(function(root){
  if(root.dataset.ready)return;root.dataset.ready='1';
  // Redistribute columns without scaling cards or typography.
  var board=root.querySelector('.wtt-board');
  root.style.maxWidth='1330px';
  function fit(){
   var base=+root.dataset.width||950,width=Math.max(base,root.clientWidth),inset=12,stretch=(width-120-inset*2)/(base-120);
   board.style.zoom='1';board.style.width=width+'px';
   board.style.gridTemplateColumns='repeat('+Math.max(1,Math.floor((width-inset*2+12)/132))+',120px)';
   function map(x){return inset+60+(x-60)*stretch;}
   root.querySelectorAll('.wtt-node,.wtt-arrow').forEach(function(e){if(!e.dataset.baseLeft)e.dataset.baseLeft=String(parseFloat(e.style.left)||0);var x=+e.dataset.baseLeft;e.style.left=(e.classList.contains('wtt-node')?inset+x*stretch:map(x))+'px';});
   var divider=root.querySelector('.wtt-divider');var header=root.querySelector('.wtt-header');
   if(!header.dataset.baseDivider)header.dataset.baseDivider=String(parseFloat(header.style.gridTemplateColumns)||651);
   var split=map(+header.dataset.baseDivider);header.style.gridTemplateColumns=split+'px 1fr';
   if(divider)divider.style.left=split+'px';
   board.style.background='linear-gradient(to right,#242e33 '+split+'px,#3d3623 '+split+'px)';
   drawEdges(map);
  }
  fit();if(root.querySelector('.wtt-requirement')&&board.offsetWidth>root.clientWidth){var first=Math.min.apply(null,Array.from(root.querySelectorAll('.wtt-node')).map(function(n){return parseFloat(n.style.left)||0;}));root.querySelector('.wtt-scroll').scrollLeft=Math.max(0,first-24);}if(window.ResizeObserver){var observer=new ResizeObserver(fit);observer.observe(root);}else window.addEventListener('resize',fit);
  function closeGroup(g){g.classList.remove('wtt-open');g.setAttribute('aria-expanded','false');}
  document.addEventListener('pointerdown',function(e){if(!root.isConnected)return;root.querySelectorAll('.wtt-open').forEach(function(g){if(!g.contains(e.target))closeGroup(g);});});
  root.querySelectorAll('.wtt-group').forEach(function(g){g.setAttribute('aria-expanded','false');function toggle(e){if(e.target.closest('a')||e.target.closest('.wtt-popup'))return;var opening=!g.classList.contains('wtt-open');root.querySelectorAll('.wtt-open').forEach(function(other){if(other!==g)closeGroup(other);});g.classList.toggle('wtt-open',opening);g.setAttribute('aria-expanded',String(opening));}g.addEventListener('click',toggle);g.addEventListener('keydown',function(e){if(e.target===g&&(e.key==='Enter'||e.key===' ')){e.preventDefault();toggle(e);}});});
  root.addEventListener('keydown',function(e){if(e.key==='Escape'){root.querySelectorAll('.wtt-open').forEach(function(g){g.classList.remove('wtt-open');g.setAttribute('aria-expanded','false');});document.activeElement.blur();}});
  root.querySelectorAll('.wtt-mode').forEach(function(b){b.tabIndex=0;b.setAttribute('role','button');function apply(){root.dataset.mode=b.dataset.mode;filter();}b.addEventListener('click',apply);b.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();apply();}});});
  var bar=document.createElement('div');bar.className='wtt-filters';var input=document.createElement('input');input.type='search';input.placeholder='搜索载具名称或游戏代码';input.setAttribute('aria-label','搜索载具');bar.appendChild(input);
  var status=document.createElement('select');status.setAttribute('aria-label','载具状态');[['','所有状态'],['normal','普通'],['premium','高级'],['squadron','联队']].forEach(function(x){var o=document.createElement('option');o.value=x[0];o.textContent=x[1];status.appendChild(o);});bar.appendChild(status);
  function select(label,values){var s=document.createElement('select');s.setAttribute('aria-label',label);[''].concat(values).forEach(function(v){var o=document.createElement('option');o.value=v;o.textContent=v||label;s.appendChild(o);});s.addEventListener('change',filter);bar.appendChild(s);return s;}
  var cards=Array.from(root.querySelectorAll('.wtt-card'));
  var ranks=select('等级',Array.from(new Set(cards.map(function(c){return c.dataset.rank;}))).sort(function(a,b){return +a-+b;}));
  var roles=select('类别',Array.from(new Set(cards.map(function(c){return c.dataset.role;}))).filter(Boolean));
  var brPanel=document.createElement('details');brPanel.className='wtt-br-filter';var summary=document.createElement('summary');summary.textContent='分房权重';brPanel.appendChild(summary);var ranges=document.createElement('div');ranges.className='wtt-br-ranges';brPanel.appendChild(ranges);var brRanges={};
  var brModes=[['ab','街机'],['rb','历史'],['sb','全真']];if(root.querySelector('.wtt-mode[data-mode="grb"]'))brModes.push(['grb','陆战历史']);
  brModes.forEach(function(pair){
   var mode=pair[0],values=Array.from(new Set(cards.map(function(c){return +c.querySelector('.wtt-br-'+mode).textContent;}))).sort(function(a,b){return a-b;});
   var row=document.createElement('div');row.className='wtt-br-row';var title=document.createElement('div');title.textContent=pair[1];row.appendChild(title);var track=document.createElement('div');track.className='wtt-br-track';var fill=document.createElement('span');fill.className='wtt-br-fill';track.appendChild(fill);var output=document.createElement('output');var inputs=[];
   ['下限','上限'].forEach(function(label,k){var slider=document.createElement('input');slider.type='range';slider.min='0';slider.max=String(values.length-1);slider.step='1';slider.value=String(k?values.length-1:0);slider.className=k?'wtt-range-max':'wtt-range-min';slider.setAttribute('aria-label',pair[1]+'权重'+label);slider.addEventListener('input',function(){if(+inputs[0].value>+inputs[1].value)inputs[1-k].value=slider.value;sync();filter();});inputs.push(slider);track.appendChild(slider);});
   function sync(){var lo=values[+inputs[0].value],hi=values[+inputs[1].value],steps=Math.max(1,values.length-1);output.textContent=lo.toFixed(1)+' — '+hi.toFixed(1);inputs.forEach(function(s){s.setAttribute('aria-valuetext',values[+s.value].toFixed(1));});fill.style.left=(+inputs[0].value/steps*100)+'%';fill.style.right=(100-+inputs[1].value/steps*100)+'%';}
   row.appendChild(track);row.appendChild(output);ranges.appendChild(row);brRanges[mode]={values:values,inputs:inputs};sync();
  });bar.appendChild(brPanel);
  document.addEventListener('click',function(e){if(!brPanel.contains(e.target))brPanel.open=false;});brPanel.addEventListener('keydown',function(e){if(e.key==='Escape'){brPanel.open=false;summary.focus();}});
  var result=document.createElement('div');result.className='wtt-results';result.hidden=true;var resultText=document.createElement('span');resultText.setAttribute('role','status');resultText.setAttribute('aria-live','polite');result.appendChild(resultText);var clear=document.createElement('button');clear.type='button';clear.textContent='清除筛选';clear.addEventListener('click',function(){input.value='';status.value='';ranks.value='';roles.value='';Object.keys(brRanges).forEach(function(mode){var r=brRanges[mode];r.inputs[0].value='0';r.inputs[1].value=String(r.values.length-1);r.inputs[0].dispatchEvent(new Event('input'));});filter();});result.appendChild(clear);
  var list=document.createElement('button');list.className='wtt-view-toggle';list.type='button';list.textContent='列表';list.setAttribute('aria-pressed','false');list.addEventListener('click',function(){root.querySelectorAll('.wtt-open').forEach(closeGroup);var isList=root.classList.toggle('wtt-list');list.textContent=isList?'科技树':'列表';list.setAttribute('aria-pressed',String(isList));root.querySelectorAll('.wtt-group').forEach(function(g){g.tabIndex=isList?-1:0;g.setAttribute('role',isList?'group':'button');});filter();});bar.appendChild(list);root.querySelector('.wtt-toolbar').appendChild(bar);root.querySelector('.wtt-toolbar').appendChild(result);
  function filter(){var q=input.value.trim().toLocaleLowerCase(),visible=new Set();var active=!!(q||status.value||ranks.value||roles.value||Object.keys(brRanges).some(function(mode){var r=brRanges[mode];return +r.inputs[0].value!==0||+r.inputs[1].value!==r.values.length-1;}));root.classList.toggle('wtt-filter-active',active);cards.forEach(function(c){var inRange=Object.keys(brRanges).every(function(mode){var r=brRanges[mode],v=+c.querySelector('.wtt-br-'+mode).textContent;return v>=r.values[+r.inputs[0].value]&&v<=r.values[+r.inputs[1].value];});var match=c.dataset.search.toLocaleLowerCase().includes(q)&&(!status.value||c.classList.contains('wtt-'+status.value))&&(!ranks.value||ranks.value===c.dataset.rank)&&(!roles.value||roles.value===c.dataset.role)&&inRange;c.classList.toggle('wtt-filtered-card',!match);c.classList.toggle('wtt-match',active&&match);if(match)visible.add(c.dataset.unit);});root.querySelectorAll('.wtt-node').forEach(function(n){var match=!!n.querySelector('.wtt-card:not(.wtt-filtered-card)');n.classList.toggle('wtt-filtered',!match);n.classList.toggle('wtt-matched-node',active&&match);});result.hidden=!active;resultText.textContent='找到 '+visible.size+' 辆';root.querySelector('.wtt-search-hint').textContent=active?'匹配 '+visible.size+' / '+cards.length+' 辆':'共 '+cards.length+' 辆 · 点击文件夹展开';root.classList.toggle('wtt-no-results',visible.size===0);root.dataset.matches=String(visible.size);}input.addEventListener('input',filter);status.addEventListener('change',filter);
  function drawEdges(map){var ns='http://www.w3.org/2000/svg',svg=board.querySelector('.wtt-lines');if(!svg){svg=document.createElementNS(ns,'svg');svg.classList.add('wtt-lines');board.appendChild(svg);}svg.replaceChildren();root.querySelectorAll('.wtt-edge').forEach(function(e){if(e.dataset.points){var points=e.dataset.points.split(' ').map(function(pair){var v=pair.split(',').map(Number);return [map(v[0]),v[1]];}),path=document.createElementNS(ns,'path'),last=points[points.length-1],prev=points[points.length-2],dx=last[0]-prev[0],dy=last[1]-prev[1],length=Math.hypot(dx,dy),ux=dx/length,uy=dy/length,tip=document.createElementNS(ns,'path');var stem=points.map(function(p){return p.slice();});stem[stem.length-1]=[last[0]-ux*9,last[1]-uy*9];path.setAttribute('d',stem.map(function(p,i){return (i?'L':'M')+p[0]+' '+p[1];}).join(' '));path.setAttribute('fill','none');path.setAttribute('stroke','#638694');path.setAttribute('stroke-width','6');path.setAttribute('stroke-linejoin','miter');path.classList.add('wtt-routed-line');path.dataset.from=e.dataset.from;path.dataset.to=e.dataset.to;svg.appendChild(path);tip.setAttribute('d','M'+last[0]+' '+last[1]+' L'+(last[0]-ux*10-uy*6)+' '+(last[1]-uy*10+ux*6)+' L'+(last[0]-ux*10+uy*6)+' '+(last[1]-uy*10-ux*6)+' Z');tip.setAttribute('fill','#638694');tip.classList.add('wtt-routed-tip');tip.dataset.from=e.dataset.from;tip.dataset.to=e.dataset.to;svg.appendChild(tip);return;}var a=e.dataset,x=map(+a.x1),z=map(+a.x2),y=+a.y1,v=+a.y2,mid=y+Math.max(10,(v-y)/2),p=document.createElementNS(ns,'path');p.setAttribute('d','M'+x+' '+y+' V'+mid+' H'+z+' V'+(v-7));p.dataset.from=a.from;p.dataset.to=a.to;p.setAttribute('fill','none');p.setAttribute('stroke','#638694');p.setAttribute('stroke-width','6');svg.appendChild(p);var h=document.createElementNS(ns,'path');h.setAttribute('d','M'+(z-7)+' '+(v-9)+' L'+z+' '+v+' L'+(z+7)+' '+(v-9)+' Z');h.dataset.from=a.from;h.dataset.to=a.to;h.setAttribute('fill','#638694');svg.appendChild(h);});}
  // Popup coordinates are independent of the stretched board. Only real edges render.
  root.querySelectorAll('.wtt-popup').forEach(function(popup){
   var ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg'),edges=Array.from(popup.querySelectorAll('.wtt-popup-edge'));
   svg.classList.add('wtt-popup-lines');svg.setAttribute('aria-hidden','true');
   edges.forEach(function(e,k){
    var a=+e.dataset.sourceRow-1,b=+e.dataset.targetRow-1,down=b>a,x=65,y=5+a*78+(down?52:-4),end=5+b*78+(down?-4:52),points;
    if(b===a+1)points=[[x,y],[x,end]];
    else {var lane=134+k*12;popup.style.width=(lane+10)+'px';points=[[125,5+a*78+24],[lane,5+a*78+24],[lane,5+b*78+24],[129,5+b*78+24]];}
    var last=points[points.length-1],prev=points[points.length-2],dx=last[0]-prev[0],dy=last[1]-prev[1],length=Math.hypot(dx,dy),ux=dx/length,uy=dy/length,stem=points.map(function(p){return p.slice();});
    stem[stem.length-1]=[last[0]-ux*9,last[1]-uy*9];
    var line=document.createElementNS(ns,'path'),tip=document.createElementNS(ns,'path');
    line.setAttribute('d',stem.map(function(p,i){return (i?'L':'M')+p.join(' ');}).join(' '));line.setAttribute('fill','none');line.setAttribute('stroke','#638694');line.setAttribute('stroke-width','6');line.classList.add('wtt-popup-line');
    tip.setAttribute('d','M'+last.join(' ')+' L'+(last[0]-ux*10-uy*6)+' '+(last[1]-uy*10+ux*6)+' L'+(last[0]-ux*10+uy*6)+' '+(last[1]-uy*10-ux*6)+' Z');tip.setAttribute('fill','#638694');tip.classList.add('wtt-popup-tip');
    [line,tip].forEach(function(p){p.dataset.from=e.dataset.from;p.dataset.to=e.dataset.to;svg.appendChild(p);});
   });popup.appendChild(svg);
  });
  filter();root.dataset.ready='1';
 });watchSiteHeaders();}
 if(window.mw&&mw.hook)mw.hook('wikipage.content').add(function(c){init(c[0]||document);});
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',function(){init(document);});else init(document);
})();
