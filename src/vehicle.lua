-- Vehicle page prototype: JSON data page + scoped rendering. Never writes to the Wiki.
-- Invoke: {{#invoke:WTJ/vehicle|page|id=il_leopard_2a6_hel|mode=rb}}
local p={}
local prefix='WTJ'
local modes={ab='街机',rb='历史'}
local modeOrder={'ab','rb'}
local pendingText='待计算'

-- Plain-text escaping. Wiki markup characters are replaced, never emitted.
local function esc(s)
 if s==nil then return '' end
 local t=tostring(s)
 t=t:gsub('&','&amp;'):gsub('<','&lt;'):gsub('>','&gt;'):gsub('"','&quot;'):gsub("'",'&#39;')
 t=t:gsub('%[','&#91;'):gsub('%]','&#93;'):gsub('{','&#123;'):gsub('}','&#125;'):gsub('|','&#124;')
 return t
end

local function err(text) return '<div class="wtv wtv-error" role="alert">'..esc(text)..'</div>' end

local function isNumber(v) return type(v)=='number' and v==v and v~=math.huge and v~=-math.huge end
local function hasKeys(t) if type(t)~='table' then return false end for _ in pairs(t) do return true end return false end
local function nonEmpty(v) return v~=nil and v~='' and not (type(v)=='table' and not hasKeys(v)) end
local function text(v) if type(v)=='string' or type(v)=='number' then return tostring(v) end return nil end
local function pending() return '<span class="wtv-pending">'..pendingText..'</span>' end

-- Display numbers without inventing precision for string values.
local function numText(v)
 if isNumber(v) then
  if v==math.floor(v) then
   local s=string.format('%d',v)
   repeat
    local replaced
    s,replaced=s:gsub('^(-?%d+)(%d%d%d)','%1,%2')
   until replaced==0
   return s
  end
  return (string.format('%.2f',v):gsub('0+$',''):gsub('%.$',''))
 end
 return esc(tostring(v or ''))
end

local function currency(kind,value)
 if value==nil then return pending() end
 return numText(value)..' [[File:'..({rp='Specs-Card-Exp.png',sl='Specs-Card-Lion.png',ge='Specs-Card-Eagle.png'})[kind]..'|14px|link=|alt='..({rp='研发点',sl='银狮',ge='金鹰'})[kind]..']]'
end

local function isSafeFile(name)
 if type(name)~='string' or name=='' or #name>160 then return false end
 if name:find('%.%.',1,true) or name:find('[/\\:%c]') then return false end
 if not name:match('^[A-Za-z0-9]') then return false end
 local plain=name:gsub('[_ ]资料卡%.png$','.png')
 if not plain:match('^[A-Za-z0-9_%-%. ]+%.[A-Za-z0-9]+$') then return false end
 return true
end

-- {ab,rb,sb} table detection. Only numeric or string members are accepted.
local function splitModes(v)
 if type(v)~='table' then return nil end
 if v.ab==nil and v.rb==nil and v.sb==nil then return nil end
 local out={}
 for _,m in ipairs(modeOrder) do
  local x=v[m]
  if x~=nil and not isNumber(x) and type(x)~='string' then return nil end
  out[m]=x
 end
 return out
end

local function unitHtml(unit) if unit and unit~='' then return '<span class="wtv-unit">'..esc(unit)..'</span>' end return '' end

-- Per-mode values: the visible one is chosen by CSS from the root data-mode (and JS).
local function renderModes(v,unit)
 local parts={}
 for _,m in ipairs(modeOrder) do
  local x=v[m]
  local body=(x==nil or x=='') and pending() or (numText(x)..unitHtml(unit))
  parts[#parts+1]='<span class="wtv-mode-value" data-mode="'..m..'"><span class="wtv-mode-tag">'..modes[m]..'</span>'..body..'</span>'
 end
 return table.concat(parts)
end

-- Generic cell: nil -> pending, mode table -> per-mode spans, number/string -> text.
local function renderValue(v,unit)
 if v==nil then return pending() end
 local mv=splitModes(v)
 if mv then return renderModes(mv,unit) end
 if type(v)=='table' then return pending() end
 return numText(v)..unitHtml(unit)
end

local function labelHtml(v)
 if type(v)=='string' then return esc(v) end
 if isNumber(v) then return esc(tostring(v)) end
 local mv=splitModes(v)
 if mv then
  local parts={}
  for _,m in ipairs(modeOrder) do
   local x=mv[m]
   parts[#parts+1]='<span class="wtv-mode-value" data-mode="'..m..'">'..((x==nil or x=='') and esc('—') or esc(tostring(x)))..'</span>'
  end
  return table.concat(parts)
 end
 return '—'
end

local function anchor(id) return 'wtv-sec-'..id:gsub('[^%w%-]','_') end

-- Data loading: mw.loadJsonData first, then title:getContent + jsonDecode.
local function loadData(title)
 local obj
 if type(mw.loadJsonData)=='function' then
  obj=mw.loadJsonData(title)
 else
  if type(mw.title)~='table' or type(mw.title.new)~='function' then error('E_NO_DATA_API') end
  local t=mw.title.new(title)
  local content=t and t:getContent()
  if type(content)~='string' then error('E_DATA_MISSING: '..title) end
  if type(mw.text)~='table' or type(mw.text.jsonDecode)~='function' then error('E_NO_JSON_DECODER') end
  obj=mw.text.jsonDecode(content)
 end
 if not hasKeys(obj) then error('E_DATA_MISSING: '..title) end
 return obj
end

-- Safe MediaWiki file transclusion. The caller validates the basename first;
-- this leaves image resizing and file URLs to the site's own parser.
local function fileMarkup(file)
 if isSafeFile(file) then return '[[File:'..file..'|center|600px|link=]]' end
 return nil
end

function p.page(frame)
 local ok,result=pcall(function() return p._page(frame) end)
 if ok and type(result)=='string' then return result end
 return err('E_RENDER: '..tostring(result))
end

-- The wikitext page template uses this before #ifexist/transclusion so its
-- manually edited child-page title obeys the same identifier whitelist.
function p.content_id(frame)
 local args=frame and frame.args or {}
 local id=args.id
 if id==nil or id=='' then id='il_leopard_2a6_hel' end
 id=tostring(id)
 if #id>96 or not id:match('^[a-z0-9_%-]+$') then return '' end
 return id
end

function p._page(frame)
 local args=frame and frame.args or {}
 local id=args.id
 if id==nil or id=='' then id='il_leopard_2a6_hel' end
 id=tostring(id)
 if #id>96 or not id:match('^[a-z0-9_%-]+$') then error('E_ID') end
 local mode=args.mode
 if mode==nil or mode=='' then mode='rb' end
 mode=tostring(mode)
 if not modes[mode] then error('E_MODE') end

 local title=prefix..'/data/vehicle/'..id..'.json'
 local data=loadData(title)
 if data.schema~=1 or data.kind~='vehicle_page' then error('E_SCHEMA: '..title) end
 if data.id~=id then error('E_ID_MISMATCH: '..title) end
 local ordnance={}
 for _,sharedTitle in ipairs(data.ordnance_pages or {}) do
  local base=prefix..'/data/ordnance/'
  if type(sharedTitle)~='string' or sharedTitle:sub(1,#base)~=base or not sharedTitle:sub(#base+1):match('^aircraft%-%d+%.json$') then error('E_ORDNANCE_TITLE') end
  local shared=loadData(sharedTitle)
  if shared.schema~=1 or shared.kind~='aircraft_ordnance' then error('E_ORDNANCE_SCHEMA') end
  for key,item in pairs(shared.items or {}) do ordnance[key]=item end
 end

 local out={}
 local function add(...) for i=1,select('#',...) do out[#out+1]=select(i,...) end end

 add('<div class="wtv" data-mode="',mode,'" data-vehicle="',esc(id),'">')

 -- Hero -------------------------------------------------------------------
 local name=text(data.name)
 if name==nil or name=='' then name=id end
 local br=type(data.br)=='table' and data.br or {}
 local meta={}
 local function metaItem(label,value)
  if not nonEmpty(value) then return end
  local t=text(value)
  if t==nil then return end
  meta[#meta+1]='<li><span class="wtv-k">'..esc(label)..'</span><span class="wtv-v">'..esc(t)..'</span></li>'
 end
 metaItem('游戏代码',data.id)
 metaItem('国家',data.country)
 metaItem('分支',data.branch)
 metaItem('类别',data.category)
 local rank=data.rank
 local roman={ [1]='I',[2]='II',[3]='III',[4]='IV',[5]='V',[6]='VI',[7]='VII',[8]='VIII',[9]='IX' }
 if isNumber(rank) then rank=roman[rank] or tostring(rank) end
 metaItem('等级',rank)
 metaItem('游戏版本',data.game_version)

 local background='车库'
 add('<div class="wtv-bwiki-hero" id="wtv-top"><div class="wtv-bwiki-background">[[File:载具图鉴-'..background..'背景.jpg|1200px|link=]]</div><div class="wtv-bwiki-image">')
 local file=data.image_file
 if isSafeFile(file) then add(fileMarkup(file)) end
 add('</div><div class="wtv-bwiki-card"><h2 class="wtv-title">',esc(name),'</h2><div class="wtv-bwiki-country">',esc(data.country),'　',esc(rank),' 级</div><hr/><div class="wtv-bwiki-br-title">分房权重：</div><table class="wtv-bwiki-br"><thead><tr>')
 local brModes={ab='街机',rb='历史',sb='全真',grb='陆战历史'}
 local brOrder={'ab','rb','sb'}
 if data.branch_id=='aviation' or (data.branch_id==nil and data.branch=='空军') then brOrder[#brOrder+1]='grb' end
 for _,m in ipairs(brOrder) do add('<th>',brModes[m],'</th>') end
 add('</tr></thead><tbody><tr>')
 for _,m in ipairs(brOrder) do add('<td>',numText(br[m]),'</td>') end
 add('</tr></tbody></table><div class="wtv-bwiki-category">',esc(data.category),'</div><div class="wtv-bwiki-cost"><div><span>研发需求</span><strong>',currency('rp',data.research_cost),'</strong></div><div><span>价格</span><strong>',currency('sl',data.purchase_cost),'</strong></div></div></div><div class="wtv-bwiki-tab">简介</div></div>')
 add('<div class="wtv-layout"><div class="wtv-main">')

 -- Sections, modifications, warnings ---------------------------------------
 local sections={}
 if type(data.sections)=='table' then
  for _,s in ipairs(data.sections) do
   if type(s)=='table' and type(s.id)=='string' and s.id:match('^[%w_%-]+$') and type(s.rows)=='table' and #s.rows>0 then
    sections[#sections+1]=s
   end
  end
 end

 local function rowsTable(rows)
  add('<div class="game-unit_chars">')
  for _,row in ipairs(rows or {}) do
   if type(row)=='table' then
    local value=row.value
    if type(value)=='table' and not splitModes(value) then
     local parts={} for _,v in ipairs(value) do parts[#parts+1]=numText(v) end
     value=table.concat(parts,' / ')
    end
    local unit=row.unit or ''
    local display=renderValue(value,unit)
    if unit=='银狮' then display=currency('sl',value) elseif unit=='金鹰' then display=currency('ge',value) elseif unit=='研发点' then display=currency('rp',value) end
    add('<div class="game-unit_chars-block"><div class="game-unit_chars-line"><span class="game-unit_chars-header">',labelHtml(row.label),'</span><span class="game-unit_chars-value" title="',esc(row.source or ''),'">',display,'</span></div></div>')
   end
  end
  add('</div>')
 end
 local content=require('Module:WTJ/vehicle-content')
 add(content.render(frame,id,'basic-info'))

 local mods={}
 if type(data.modifications)=='table' then
  for _,m in ipairs(data.modifications) do
   if type(m)=='table' and text(m.name)~=nil and text(m.name)~='' then mods[#mods+1]=m end
  end
 end
 local warnings={}
 if type(data.warnings)=='table' then
  for _,w in ipairs(data.warnings) do if type(w)=='string' and w~='' then warnings[#warnings+1]=w end end
 end
 local function isEconomy(sid) return sid:find('econom',1,true)~=nil end

 local function sectionTitle(s,fallback)
  local stitle=text(s.title)
  if stitle==nil or stitle=='' then stitle=fallback end
  return stitle
 end

 -- Official-style continuous blocks --------------------------------------
 for _,s in ipairs(sections) do
  local sid=anchor(s.id)
  if not isEconomy(s.id) and s.id~='armaments' and s.id~='general' then
   add('<div class="wtv-block wtv-specification" id="',sid,'"><div class="wtv-block-header">',esc(sectionTitle(s,s.id)),'</div><div class="wtv-block-content">')
   if #(s.features or {})>0 then
    add('<div class="game-unit_features">')
    for _,feature in ipairs(s.features) do add('<span class="game-unit_feature">',esc(feature),'</span>') end
    add('</div>')
   end
   if s.id=='aircraft-general' then
    for _,group in ipairs({'main','weight','limits'}) do
     local rows={} for _,row in ipairs(s.rows) do if row.group==group then rows[#rows+1]=row end end
     if group~='main' then add('<h3 class="wtv-spec-subtitle">',group=='weight' and '重量' or '限制','</h3>') end
     rowsTable(rows)
    end
   else rowsTable(s.rows) end
   add('</div></div>')
  end
 end

 -- Sensor definitions and installation references stay inside this vehicle JSON.
 local sensorSystem=data.sensors or {}
 local function sensorText(v,depth)
  depth=depth or 0
  if v==nil then return '未提供' end
  if type(v)=='boolean' then return v and '✓' or '—' end
  if type(v)~='table' then return tostring(v) end
  if depth>2 then return '详见设备定义' end
  local labels={resolution='分辨率',colour='彩色',generation='代数',range_m='探测距离（m）',range_max_m='量程上限（m）',azimuth_deg='方位（°）',elevation_deg='俯仰（°）',period_s='周期（s）',band='波段',search='搜索',track='跟踪',tws='边扫边跟',iff='敌我识别'}
  local parts={}
  if #v>0 then for _,x in ipairs(v) do parts[#parts+1]=sensorText(x,depth+1) end
  else
   local keys={} for k in pairs(v) do if k~='source' and k~='generation_status' then keys[#keys+1]=k end end table.sort(keys)
   for _,k in ipairs(keys) do parts[#parts+1]=(labels[k] or k)..'：'..sensorText(v[k],depth+1) end
  end
  return table.concat(parts,' / ')
 end
 if #(sensorSystem.features or {})>0 then
  add('<div class="wtv-block" id="wtv-sensors"><div class="wtv-block-header">传感器与航电</div><div class="wtv-block-content"><div class="game-unit_features">')
  for i,feature in ipairs(sensorSystem.features) do
   add('<div class="game-unit_feature wtv-popover-trigger" role="button" tabindex="0" data-popup="sensor-',tostring(i),'">',esc(feature.label or feature.name),'</div>')
  end
  add('</div>')
  for i,feature in ipairs(sensorSystem.features) do
   add('<div class="wtv-popup-source" data-popup-id="sensor-',tostring(i),'"><span class="game-unit_weapon-title">',esc(feature.name or feature.label),'</span><div class="game-unit_chars">')
   local definition=(sensorSystem.definitions or {})[feature.definition_id] or {}
   local installation=nil for _,entry in ipairs(sensorSystem.installations or {}) do if entry.id==feature.installation_id then installation=entry end end
   if installation and installation.activation~='always' then add('<div class="game-unit_chars-line"><span>启用条件</span><span>',esc(installation.option or installation.requires_modification or installation.activation),'</span></div>') end
   for _,r in ipairs(feature.rows or {}) do
    add('<div class="game-unit_chars-line"><span>',esc(r.label),'</span><span title="',esc(r.source or definition.source),'">',esc(sensorText(r.value)),r.unit and (' '..esc(r.unit)) or '','</span></div>')
   end
   add('</div></div>')
  end
  add('</div></div>')
 end
 local ammoById={}
 for _,ammo in ipairs(data.ammunition or {}) do ammoById[ammo.id]=ammo end
 local function weaponAmmo(weapon)
  if #(weapon.belts or {})>0 then
   add('<div class="wtv-table-wrap"><table class="game-unit_belt-list"><thead><tr><th rowspan="2">弹链</th><th rowspan="2">弹链组成</th><th colspan="',tostring(#weapon.belt_distances),'">各距离穿深（mm）</th></tr><tr>')
   for _,distance in ipairs(weapon.belt_distances) do add('<th>',numText(distance),' m</th>') end
   add('</tr></thead><tbody>')
   for _,belt in ipairs(weapon.belts) do
    add('<tr><th scope="row"><span class="wtv-belt-label"><span class="wtv-belt-icon">')
    for _,file in ipairs(belt.icon_sequence or {}) do if isSafeFile(file) then add('<span>[[File:',file,'|32px|link=|alt=]]</span>') end end
    add('</span><span class="wtv-belt-name">',esc(belt.name),'</span></span></th><td>',esc(belt.filling),'</td>')
    for _,distance in ipairs(weapon.belt_distances) do add('<td>',numText(belt.penetration[tostring(distance)]),'</td>') end
    add('</tr>')
   end
   add('</tbody></table></div>')
   return
  end
  if #(weapon.ammunition_ids or {})==0 then return end
  add('<div class="wtv-table-wrap"><table class="game-unit_belt-list"><thead><tr><th>弹药</th><th>类型</th><th>口径<br/>mm</th><th>弹重<br/>kg</th><th>初速<br/>m/s</th><th>装药量 / TNT 当量<br/>kg</th></tr></thead><tbody>')
  for _,ammoId in ipairs(weapon.ammunition_ids) do
   local ammo=ammoById[ammoId]
   if ammo then
    local kind=(data.ammunition_types or {})[ammo.projectile_type or ''] or {}
    add('<tr><th scope="row">')
    if #(ammo.icon_layers or {})>0 then
     add('<span class="wtv-ammo-icon">')
     for i,layer in ipairs(ammo.icon_layers) do
      if isSafeFile(layer) then
       local ratio=(i==#ammo.icon_layers and isNumber(ammo.icon_base_aspect_ratio)) and ammo.icon_base_aspect_ratio or 1
       ratio=math.max(0.05,math.min(1,ratio))
       add('<span style="width:',tostring(32*ratio),'px;left:',tostring(16*(1-ratio)),'px">[[File:',layer,'|32px|link=|alt=]]</span>')
      end
     end
     add('</span>')
    end
    add(esc(ammo.name),'</th><td>',esc(kind.name or ammo.projectile_type or '—'),'</td>')
    for _,field in ipairs({'caliber_mm','mass_kg','muzzle_velocity_m_s'}) do add('<td>',ammo[field]~=nil and numText(ammo[field]) or '—','</td>') end
    add('<td>',ammo.explosive_mass_kg~=nil and numText(ammo.explosive_mass_kg) or '—')
    if ammo.tnt_equivalent_kg~=nil then add(' / ',numText(ammo.tnt_equivalent_kg),' TNT') end
    add('</td></tr>')
   end
  end
  add('</tbody></table></div>')
 end
 if type(data.weapons)=='table' and #data.weapons>0 then
  add('<div class="wtv-block wtv-armaments" id="wtv-armaments"><div class="wtv-block-header">武器装备</div><div class="wtv-block-content" id="wtv-ammunition">')
  for _,weapon in ipairs(data.weapons) do
   if weapon.slot==nil then
    add('<div class="game-unit_weapon"><span class="game-unit_weapon-title">',esc(weapon.name),weapon.role=='防御炮塔' and '（防御炮塔）' or '', '</span><div class="game-unit_features">')
    for _,feature in ipairs(weapon.features or {}) do add('<span class="game-unit_feature">',esc(feature),'</span>') end
    add('</div>') rowsTable(weapon.characteristics) weaponAmmo(weapon) add('</div>')
   end
  end
  add('</div></div>')
 end
 local loadouts=data.loadouts or {}
 if #(data.ordnance_pages or {})>0 then
  add(require('Module:WTJ/loadouts').render(loadouts,ordnance))
 elseif type(loadouts.slots)=='table' and #loadouts.slots>0 then
  add('<div class="wtv-block" id="wtv-loadouts"><div class="wtv-block-header">挂载</div><div class="wtv-block-content"><div class="wtv-table-wrap"><table class="game-unit_slot-list"><thead><tr><th>可选挂载</th>')
  local options={} local optionOrder={} local weaponNames={}
  for _,weapon in ipairs(data.weapons or {}) do weaponNames[weapon.id]=weapon.name end
  for _,slot in ipairs(loadouts.slots) do
   add('<th>',numText(slot.index),'</th>')
   for _,option in ipairs(slot.options or {}) do
    if not options[option.id] then options[option.id]={name=option.name,cells={}} optionOrder[#optionOrder+1]=option.id end
    local names={} for _,weaponId in ipairs(option.weapons or {}) do names[#names+1]=weaponNames[weaponId] or weaponId end
    options[option.id].cells[slot.index]=#names>0 and table.concat(names,' + ') or '—'
   end
  end
  add('</tr></thead><tbody>')
  for _,key in ipairs(optionOrder) do
   local option=options[key] add('<tr><th scope="row">',esc(option.name),'</th>')
   for _,slot in ipairs(loadouts.slots) do add('<td>',esc(option.cells[slot.index] or '—'),'</td>') end
   add('</tr>')
  end
  add('</tbody></table></div>')
  if #(loadouts.presets or {})>0 then
   add('<div class="wtv-loadout-presets"><h3>挂载方案</h3>')
   for _,preset in ipairs(loadouts.presets) do
    add('<div class="game-unit_weapon"><span class="game-unit_weapon-title">',esc(preset.name),'</span>')
    local rows={}
    for _,slot in ipairs(preset.slots or {}) do rows[#rows+1]={label='挂点 '..tostring(slot.slot or ''),value=slot.name,source=slot.source} end
    rowsTable(rows)
    add('</div>')
   end
   add('</div>')
  end
  for _,weapon in ipairs(data.weapons or {}) do
   if weapon.slot~=nil then
    add('<div class="game-unit_weapon"><span class="game-unit_weapon-title">',esc(weapon.name),'（挂点 ',numText(weapon.slot),'）</span>')
    rowsTable(weapon.characteristics) weaponAmmo(weapon) add('</div>')
   end
  end
  add('</div></div>')
 end

 -- Economy: rows copied from economy sections, never recomputed -------------
 local hasEconomy=false
 for _,s in ipairs(sections) do if isEconomy(s.id) then hasEconomy=true end end
 if hasEconomy then
  add('<div class="wtv-block wtv-economy" id="wtv-economy"><div class="wtv-block-header">经济</div><div class="wtv-block-content">')
  for _,s in ipairs(sections) do
   if isEconomy(s.id) then
     add('<div class="wtv-spec-block" id="',anchor(s.id),'">')
    rowsTable(s.rows)
    add('</div>')
   end
  end
  add('</div></div>')
 end

 -- Shared modification component ------------------------------------------
 add(require("Module:WTJ/modifications").render(data))

 add(content.render(frame,id,'player-content'))
 add('</div><div class="wtv-side"><div class="wtv-side-title">页面导航</div><a href="#wtv-general">基本信息</a>')
 if #(data.ordnance_pages or {})>0 then add('<a href="#wtv-sec-mobility">飞行性能</a><a href="#wtv-sec-aircraft-general">一般特征</a>') else add('<a href="#wtv-sec-survivability">生存能力与防护</a><a href="#wtv-sec-mobility">机动性</a>') end
 add('<a href="#wtv-sensors">传感器</a><a href="#wtv-armaments">武器装备</a><a href="#wtv-ammunition">弹药</a><a href="#wtv-loadouts">挂载</a><a href="#wtv-economy">经济</a><a href="#wtv-modifications">改装</a><a href="#wtv-player-content">玩家内容</a><div class="wtv-mode-switch" role="group" aria-label="数据模式">')
 for _,m in ipairs(modeOrder) do add('<span role="button" tabindex="0" class="wtv-mode-btn" data-wtv-mode="',m,'" aria-pressed="',(m==mode and 'true' or 'false'),'">',modes[m],'</span>') end
 add('</div></div></div><p class="wtv-back"><a href="#wtv-top">返回顶部</a></p></div>')
 return table.concat(out)
end

return p
