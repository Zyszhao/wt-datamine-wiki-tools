local p={}
local prefix='WTJTreeTesting'
local function typeIcon(key)
 if mw.getCurrentFrame then return mw.getCurrentFrame():expandTemplate{title='WTJ/type-icon',args={key}} end
 return '{{WTJ/type-icon|'..key..'}}'
end
local function esc(s) return (tostring(s or ''):gsub('&','&amp;'):gsub('<','&lt;'):gsub('>','&gt;'):gsub('"','&quot;'):gsub("'",'&#39;'):gsub('[%[%]{}|]','')) end
local function run(fn)
 local cache,reads={},{}
 local function load(name,kind)
  if cache[name] then return cache[name] end
  local title=prefix..'/data/'..name..'_testing.json'
  local obj
  if type(mw.loadJsonData)=='function' then obj=mw.loadJsonData(title)
  else local t=mw.title.new(title);local raw=t and t:getContent();if not raw then error('E_DATA_MISSING: '..title) end;obj=mw.text.jsonDecode(raw) end
  if type(obj)~='table' or obj.schema~=1 or obj.kind~=kind then error('E_SCHEMA: '..title) end
  cache[name]=obj;reads[#reads+1]=title;return obj
 end
 return fn(load,reads)
end
local function protected(fn)
 local ok,result=pcall(function() return run(fn) end)
 return ok and result or '<div class="wtr-error">'..esc(result)..'</div>'
end
function p.tree(frame)
 return protected(function(load)
  local args=frame and frame.args or {};local key=args.tree or 'usa_army_tree'
  if not key:match('^[a-z]+_[a-z]+_tree$') then error('E_TREE') end
  local index=load('vehicles_index','vehicle_index');local tree=load(key,'tech_tree')
  if index.game_version~=tree.game_version then error('E_VERSION') end
  local modes={'ab','rb','sb'};if tree.branch=='aviation' then modes[#modes+1]='grb' end
  local existing=args.links=='existing';local mode=args.mode or 'rb';if mode~='ab' and mode~='rb' and mode~='sb' and not (mode=='grb' and tree.branch=='aviation') then error('E_MODE') end
  local profile=args.profile=='bwiki' and 'bwiki' or 'official'
  local roman={'I','II','III','IV','V','VI','VII','VIII','IX'}
  local width=tree.layout.width;local divider=tree.layout.divider or 651
  local out={'<div class="wtt wtt-profile-'..profile..'" data-tree="'..esc(tree.id or 'usa_army')..'" data-width="'..width..'" style="max-width:'..(1330)..'px" data-mode="'..esc(mode)..'"><div class="wtt-toolbar"><span>'..esc(tree.label or '美国陆战')..'</span><div class="wtt-modes">'}
  for _,m in ipairs(modes) do out[#out+1]='<span class="wtt-mode" data-mode="'..m..'">'..({ab='街机',rb='历史',sb='全真',grb='陆战历史'})[m]..'</span>' end
  out[#out+1]='</div><span class="wtt-search-hint">共 '..tree.visible_count..' 辆 · 点击文件夹展开</span><span class="wtt-version">游戏版本 '..esc(tree.game_version)..'</span></div><div class="wtt-scroll"><div class="wtt-board" style="height:'..tree.layout.height..'px;width:'..width..'px;grid-template-columns:repeat('..math.floor((width-2)/132)..',120px);background:linear-gradient(to right,#242e33 '..divider..'px,#3d3623 '..divider..'px)"><div class="wtt-divider" style="left:'..divider..'px"></div><div class="wtt-header" style="grid-template-columns:'..divider..'px 1fr"><span>可研发载具</span><span>高级载具</span></div>'
  for _,r in ipairs(tree.layout.ranks) do out[#out+1]='<div class="wtt-rank" style="top:'..r.top..'px;height:'..r.height..'px"><span>等级 '..(roman[r.rank] or r.rank)..'</span></div>' end
  local function card(code)
   local r=index.records[code];local pr=tree.presentation[code];local dest=existing and (pr.existing_page or pr.fallback_page or r.name) or prefix..'/vehicle/'..code..'_testing';local category=r.category or '未分类'
   if not existing and r.local_page then dest=r.local_page end
   local icon=tree.assets[code];local status=pr.status=='premium' and 'premium' or pr.status=='squadron' and 'squadron' or 'normal'
   local backgrounds={normal='Item_own.png',premium='Item_prem.png',squadron='Item_squad.png'}
   local result={'<div class="wtt-card wtt-'..status..'" data-unit="'..esc(code)..'" data-rank="'..r.rank..'" data-role="'..esc(category)..'" data-search="'..esc(pr.name..' '..code)..'" title="'..esc(pr.name..' · '..category)..'"><span class="wtt-file-background">[[File:'..backgrounds[status]..'|120px|link=]]</span>'}
   if icon['local'] or icon.remote then result[#result+1]='<div class="wtt-image">[[File:'..esc(icon.file)..'|x43px|link=]]</div>' end
   result[#result+1]='<div class="wtt-name">'..esc(pr.name)..'</div><div class="wtt-hit">[['..esc(dest or prefix..'/vehicle/'..code..'_testing')..'|<span class="wtt-sr">'..esc(pr.name)..'</span>]]</div>'
   for i,m in ipairs({'ab','rb','sb'}) do result[#result+1]='<span class="wtt-br wtt-br-'..m..'">'..string.format('%.1f',r.br[i] or 0)..'</span>' end
   if tree.branch=='aviation' then result[#result+1]='<span class="wtt-br wtt-br-grb">'..string.format('%.1f',r.br_ground_rb or r.br[2] or 0)..'</span>' end
   do
    local types={['轻型坦克']='LT_icon.png',['中型坦克']='MT_icon.png',['重型坦克']='HT_icon.png',['坦克歼击车']='TD_icon.png',['自行防空炮']='SPAA_icon.png'}
    local air={exp_fighter='FP_icon.png',exp_bomber='BP_icon.png',exp_assault='AP_icon.png',exp_torpedo_boat='PT_icon.png',exp_naval_ferry_barge='BGI_icon.png',exp_submarine_chaser='PC_icon.png',exp_torpedo_gun_boat='FF_icon.png'}
    local file=types[category] or pr.type_icon or air[r.class];if pr.type_key then result[#result+1]='<span class="wtt-type">'..typeIcon(pr.type_key)..'</span>' elseif file then result[#result+1]='<span class="wtt-type">[[File:'..file..'|10px|link=]]</span>' end
   end
   result[#result+1]='</div>';return table.concat(result)
  end
  for _,a in ipairs(tree.layout.arrows) do
   local x=a.x1;local target=a.x2;local height=a.y2-a.y1
   if a.points then
    local points={};for _,point in ipairs(a.points) do points[#points+1]=point[1]..','..point[2] end
    out[#out+1]='<div class="wtt-edge" data-from="'..esc(a.from)..'" data-to="'..esc(a.to)..'" data-points="'..table.concat(points,' ')..'"></div>'
   elseif a.c1==a.c2 and height>=0 then out[#out+1]='<div class="wtt-arrow" data-from="'..esc(a.from)..'" data-to="'..esc(a.to)..'" style="left:'..x..'px;top:'..a.y1..'px;height:'..height..'px"></div>'
   else out[#out+1]='<div class="wtt-edge" data-from="'..esc(a.from)..'" data-to="'..esc(a.to)..'" data-x1="'..x..'" data-x2="'..target..'" data-y1="'..a.y1..'" data-y2="'..a.y2..'"></div>' end
  end
  for _,n in ipairs(tree.layout.nodes) do
   local x=n.left or ((n.column-1)*132+(n.column>5 and 18 or 0))
   out[#out+1]='<div class="wtt-node" data-node="'..esc(n.id)..'" style="left:'..x..'px;top:'..n.top..'px">'
   if n.folder then
    local icon=tree.assets[n.folder]
    local group=index.groups and index.groups[n.folder];if not group then error('E_GROUP: '..n.folder) end
    local premium=true;for _,code in ipairs(n.units) do if tree.presentation[code].status~='premium' then premium=false end end
    out[#out+1]='<div class="wtt-group'..(premium and ' wtt-group-premium' or '')..'" tabindex="0" role="button" aria-expanded="false" aria-label="'..esc(group.name)..'"><div class="wtt-folder'..(premium and ' wtt-folder-premium' or '')..'"><span class="wtt-file-background">[[File:'..(premium and 'WTJTreeTesting_folder_prem.png' or 'WTJTreeTesting_folder.png')..'|120px|link=]]</span><div class="wtt-image">'
    if icon['local'] or icon.remote then out[#out+1]='[[File:'..esc(icon.file)..'|x43px|link=]]' end
    out[#out+1]='</div><div class="wtt-name">'..esc(group.name)..'</div></div><div class="wtt-popup">'
    local rows={};for i,code in ipairs(n.units) do rows[code]=i end
    for _,edge in ipairs(tree.layout.internal_edges or {}) do
     if rows[edge.from] and rows[edge.to] then
      out[#out+1]='<div class="wtt-popup-edge" data-from="'..esc(edge.from)..'" data-to="'..esc(edge.to)..'" data-source-row="'..rows[edge.from]..'" data-target-row="'..rows[edge.to]..'"></div>'
     end
    end
    for i,code in ipairs(n.units) do
     if i>1 then out[#out+1]='<div class="wtt-popup-gap"></div>' end
     out[#out+1]=card(code)
    end
    out[#out+1]='</div></div>'
   else out[#out+1]=card(n.units[1]) end
   out[#out+1]='</div>'
  end
  out[#out+1]='</div></div></div>'
  local result=table.concat(out)
  if tree.requirements then
   local notes={}
   for _,req in ipairs(tree.requirements) do
    local choices={}
    for _,c in ipairs(req.conditions) do choices[#choices+1]='购入本国至少 '..c.num..(c.unitClass=='tank' and ' 辆' or ' 架')..' '..(roman[c.era] or c.era)..' 级'..(c.rankExactly and '' or '及以上')..(c.unitClass=='tank' and '陆军载具' or '飞机') end
    notes[#notes+1]='<div class="wtt-requirement" data-unlock="'..esc(req.unlock)..'" data-for="'..esc(req.unit)..'">直升机入口：'..table.concat(choices,'，或')..'。高级及联队载具可计入。</div>'
   end
   result=result:gsub('(<div class="wtt%-scroll">)',function(s) return table.concat(notes)..s end,1)
  end
  return result
 end)
end
function p.modifications()
 return protected(function(load)
  local core=load('us_m1a2_modifications','vehicle_modifications');local mods=load('modifications_index','modification_index')
  if core.game_version~=mods.game_version then error('E_VERSION') end
  local out={'<div class="wtr"><div class="wtr-head"><h1>M1A2 · 共享改装库演示</h1><p>名称、图标和描述来自全局库；价格和位置来自载具本地记录。</p></div><div class="wtr-mods">'}
  for _,m in ipairs(core.modifications) do
   local r=mods.records[m.ref];if not r then error('E_MOD_REF: '..m.ref) end
   local icon=mods.icons[r.icons.image_tank or r.icons.image]
   out[#out+1]='<article class="wtr-mod">'..(icon and icon.file and '[[File:'..esc(icon.file)..'|48px|link=]]' or '<span class="wtr-noicon">无静态图标</span>')..'<h3>'..esc(r.name)..'</h3><code>'..esc(m.ref)..'</code><p>'..esc(r.description or '暂无可直接提取的中文静态描述；游戏可能动态生成。')..'</p><p>层级 '..m.position.tier..' · '..esc(m.position.category)..' · 顺序 '..m.position.order..'</p><b>'..tostring(m.rp or '—')..' RP / '..tostring(m.sl or '—')..' SL</b></article>'
  end
  out[#out+1]='</div></div>';return table.concat(out)
 end)
end
function p.check(frame)
 return protected(function(load,reads)
  local key=frame and frame.args and frame.args.tree or 'usa_army_tree';if not key:match('^[a-z]+_[a-z]+_tree$') then error('E_TREE') end
  local index=load('vehicles_index','vehicle_index');local tree=load(key,'tech_tree');local count=0
  for _ in pairs(index.records) do count=count+1 end
  local n=#tree.unplaced;for _ in pairs(tree.excluded or {}) do n=n+1 end;for _,c in ipairs(tree.columns) do for _,node in ipairs(c.nodes) do n=n+#node.units end end
  local groups=0;for _ in pairs(index.groups or {}) do groups=groups+1 end
  return '<pre>global_vehicles='..count..'\nglobal_groups='..groups..'\ntree='..esc(tree.id)..'\nbranch_records='..n..'\nvisible='..tree.visible_count..'\njson_pages_read='..#reads..'\n'..table.concat(reads,'\n')..'</pre>'
 end)
end
return p
