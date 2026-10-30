-- Shared JSON modification tree, used by vehicle articles and standalone embeds.
local p={}
local pendingText="待计算"
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
 if not name:match('^[A-Za-z0-9_%-%. ]+%.[A-Za-z0-9]+$') then return false end
 return true
end


local function renderValue(v) return v==nil and pending() or numText(v) end
function p.render(data)
 local mods=type(data.modifications)=="table" and data.modifications or {}
 local roman={"I","II","III","IV"}
 local out={}
 local function add(...) for i=1,select("#",...) do out[#out+1]=select(i,...) end end
 -- Modifications ----------------------------------------------------------
 if #mods>0 then
  local groups={}
  local labels={mobility='机动改装',protection='防御改装',firepower='武器改装',flight='飞行性能',lth='飞行性能',armor='生存能力',survivability='生存能力',weapon='武器改装',other='其他改装'}
  local byId={}
  local maxTier=1
  for _,m in ipairs(mods) do
   local tier=tonumber(m.tier) or 1
   local column=tonumber(m.column) or 1
   if tier>=1 and tier<=20 and column>=1 and column<=64 and tier==math.floor(tier) and column==math.floor(column) then
    local category=text(m.category) or 'other'
    if not groups[category] then groups[category]={columns=1,rows={}} end
    local g=groups[category]
    g.columns=math.max(g.columns,column)
    g.rows[tier]=g.rows[tier] or {}
    g.rows[tier][column]=m
    byId[m.id]=m
    maxTier=math.max(maxTier,tier)
   end
  end
  local order={}
  for _,category in ipairs({'lth','flight','mobility','protection','armor','survivability','firepower','weapon','other'}) do
   if groups[category] then order[#order+1]=category end
  end
  local extras={}
  for category in pairs(groups) do if not labels[category] then extras[#extras+1]=category end end
  table.sort(extras)
  for _,category in ipairs(extras) do order[#order+1]=category end
  local counts={}
  if type(data.modification_tier_requirements)=='table' then
   for _,r in ipairs(data.modification_tier_requirements) do if type(r)=='table' then counts[tonumber(r.tier) or 0]=r.count end end
  end
  local nameOverrides=type(data.modification_name_overrides)=='table' and data.modification_name_overrides or {}
  local function modName(m) return text(nameOverrides[m.id]) or text(m.name) or m.id end
  add('<div class="wtv-block" id="wtv-modifications"><div class="wtv-mod-accordion"><div class="wtv-block-header">改装</div><div class="wtv-mod-scroll" tabindex="0" role="region" aria-label="改装研发树，可横向滚动"><div class="wtv-mod-tree"><table class="wtv-mod-tiers"><thead><tr><th>层级</th></tr></thead><tbody>')
  for tier=1,maxTier do
   add('<tr><th scope="row"><strong>',esc(roman[tier] or tostring(tier)),'</strong>')
   if tier<maxTier then add('<span class="wtv-tier-gate">',renderValue(counts[tier]),'项</span><span class="wtv-tier-arrow" aria-hidden="true">↓</span>') end
   add('</th></tr>')
  end
  add('</tbody></table>')
  for _,category in ipairs(order) do
   local g=groups[category]
   add('<table class="wtv-mod-group"><thead><tr><th colspan="',tostring(g.columns),'">',esc(labels[category] or category),'</th></tr></thead><tbody>')
   for tier=1,maxTier do
    add('<tr>')
    for column=1,g.columns do
     add('<td>')
     local m=g.rows[tier] and g.rows[tier][column]
     if m then
      local parents={}
      if type(m.requires)=='table' then for _,v in ipairs(m.requires) do if type(v)=='string' and byId[v] then parents[#parents+1]=v end end end
      add('<div class="wtv-mod-node" data-mod="',esc(m.id),'" data-requires="',esc(table.concat(parents,',')),'"><div role="button" tabindex="0" aria-expanded="false" class="wtv-mod-card" title="',esc(modName(m)),'">')
      if isSafeFile(m.icon_file) then add('[[File:',m.icon_file,'|26px|link=|alt=]]') end
      add('<span>',esc(modName(m)),'</span></div><div class="wtv-mod-info"><strong>',esc(modName(m)),'</strong>')
      if text(m.description) then add('<p>',esc(m.description),'</p>') end
      add('<div><b>',currency('rp',m.rp),'</b></div><div><b>',currency('sl',m.sl),'</b></div>')
      if m.unlock_ge~=nil then add('<div><b>',currency('ge',m.unlock_ge),'</b></div>') end
      add('</div></div>')
     end
     add('</td>')
    end
    add('</tr>')
   end
   add('</tbody></table>')
  end
  add('</div></div></div></div>')
 end

 return table.concat(out)
end
function p.page(frame)
 local id=tostring(frame.args.id or "il_leopard_2a6_hel")
 if #id>96 or not id:match("^[a-z0-9_%-]+$") then error("E_ID") end
 local data=mw.loadJsonData("WTJ/data/vehicle/"..id..".json")
 if data.kind~="vehicle_page" or data.id~=id then error("E_SCHEMA") end
 return '<div class="wtv">'..p.render(data)..'</div>'
end
return p
