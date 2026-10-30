-- Aircraft stores matrix and static loadout editor, separate from article layout.
-- Static HTML only: the matrix, fixed presets and parameter text are readable
-- without JS; MediaWiki:WTJ-vehicle.js only enhances them.
local p={}

-- Text escaping. Every value that reaches the page goes through this, including
-- titles, attribute values and popover ids.
local function esc(s)
 s=tostring(s or '')
 s=s:gsub('&','&amp;'):gsub('<','&lt;'):gsub('>','&gt;'):gsub('"','&quot;'):gsub("'",'&#39;')
 s=s:gsub('{','&#123;'):gsub('}','&#125;'):gsub('%[','&#91;'):gsub('%]','&#93;'):gsub('|','&#124;')
 return s
end

local function isNumber(n) return type(n)=='number' and n==n and n~=math.huge and n~=-math.huge end
local function number(n) if not isNumber(n) then return '—' end return tostring(math.floor(n*100+0.5)/100):gsub('%.0$','') end
-- Mass text for attributes: a missing mass must never become "—" in data-mass.
local function attrNumber(n) if not isNumber(n) then return '' end return tostring(math.floor(n*100+0.5)/100):gsub('%.0$','') end

-- [[File:...]] is expanded by MediaWiki before the extension-tag sanitizer runs,
-- so the file name itself is the injection surface. Accept the site's own
-- uploads, which include Chinese names such as WTJ_弹药_x.png, and
-- mirrored game icons; reject anything that could break out of the file link.
local function isSafeFile(name)
 if type(name)~='string' or name=='' or #name>160 then return false end
 if name:find('%.%.',1,true) then return false end
 if name:find('[/\\:%c%[%]{}<>|#]') then return false end
 if not name:match('%.png$') then return false end
 if name=='' or name:find('%s%s') or name:match('^[_%s]') or name:match('[_%s]$') then return false end
 return true
end

local function image(file,size)
 size=size or '32px'
 if isSafeFile(file) then return '[[File:'..file..'|'..size..'|link=|alt=]]' end
 return ''
end

-- Store categories, in the game's order. row.category is written by the page
-- generator; the raw type string is only a fallback for older data.
local categories={
 {key='aam',label='空对空导弹'},
 {key='agm',label='空对地导弹'},
 {key='bomb',label='炸弹'},
 {key='guided_bomb',label='制导炸弹'},
 {key='rocket',label='火箭弹'},
 {key='torpedo',label='鱼雷'},
 {key='gun',label='火炮吊舱'},
 {key='fuel',label='副油箱'},
 {key='pod',label='设备吊舱'},
 {key='other',label='其他挂载'},
}
local categoryPosition={}
for position,category in ipairs(categories) do categoryPosition[category.key]=position end
local typeCategory={
 aam='aam',aim='aam',missile='aam',atam='aam',air_to_air='aam',
 agm='agm',atgm='agm',air_to_ground='agm',
 bomb='bomb',bombs='bomb',depth_charge='bomb',
 guided_bomb='guided_bomb',guidedbomb='guided_bomb',guided_bombs='guided_bomb',guidedbombs='guided_bomb',kab='guided_bomb',
 rocket='rocket',rockets='rocket',rocket_bomb='rocket',
 torpedo='torpedo',torpedoes='torpedo',
 gun='gun',gun_pod='gun',gunpod='gun',gun_pods='gun',cannon_pod='gun',
 fuel='fuel',fuel_tank='fuel',fuel_tanks='fuel',drop_tank='fuel',drop_tanks='fuel',
 pod='pod',pods='pod',targeting_pod='pod',targetingpod='pod',equipment='pod',container='pod',
}

local sideLabels={left='左侧',center='中心',right='右侧'}
local parameterFields={
 {'mass_kg','弹体 / 设备重量','kg'},
 {'caliber_mm','口径','mm'},
 {'explosive_mass_kg','装药量','kg'},
 {'tnt_equivalent_kg','TNT 当量','kg'},
}

function p.render(loadouts,catalog)
 loadouts=type(loadouts)=='table' and loadouts or {}
 catalog=type(catalog)=='table' and catalog or {}
 local out={}
 local function add(...) for i=1,select('#',...) do out[#out+1]=select(i,...) end end

 local limits=type(loadouts.limits)=='table' and loadouts.limits or {}
 local slots=type(loadouts.slots)=='table' and loadouts.slots or {}
 local matrixRows=type(loadouts.matrix_rows)=='table' and loadouts.matrix_rows or {}
 local itemIcons=type(loadouts.item_icons)=='table' and loadouts.item_icons or {}
 local displaySlots=type(loadouts.display_slots)=='table' and #loadouts.display_slots>0 and loadouts.display_slots or slots
 local columns=#displaySlots

 -- Hardpoint side. An explicit display_slots[].side wins. Otherwise the centre
 -- is the column holding a notUseforDisbalanceCalculation slot and the rest is
 -- split around it; columns without a known centre fall back to middle alignment.
 local sideOf={}
 local centrePosition=nil
 local flagged={}
 for _,slot in ipairs(slots) do
  local index=tonumber(slot.index)
  if index~=nil and slot.not_use_for_disbalance==true then flagged[index]=true end
 end
 for position,slot in ipairs(displaySlots) do
  local index=tonumber(slot.index)
  if index~=nil and flagged[index] then centrePosition=position end
 end
 for position,slot in ipairs(displaySlots) do
  local index=tonumber(slot.index)
  if index~=nil then
   local side=slot.side
   if side~='left' and side~='center' and side~='right' then
    if centrePosition then
     side=position<centrePosition and 'left' or position>centrePosition and 'right' or 'center'
    else
     local middle=math.floor((columns+1)/2)
     side=position<middle and 'left' or position>middle and 'right' or 'center'
    end
   end
   sideOf[index]=side
  end
 end
 -- Slots without a display column keep only an explicit side.
 local slotSide={}
 for _,slot in ipairs(slots) do
  local index=tonumber(slot.index)
  local side=index and sideOf[index]
  if side==nil and (slot.side=='left' or slot.side=='right' or slot.side=='center') then side=slot.side end
  slotSide[tostring(slot.index)]=side
 end

 -- Category grouping: one tbody per category, ordered as in the game.
 local groups={}
 for _,row in ipairs(matrixRows) do
  local item=catalog[row.catalog_id] or {}
  local key=row.category or item.category
  if categoryPosition[key]==nil then
   key=typeCategory[string.lower(tostring(row.type or item.type or ''))]
  end
  if categoryPosition[key]==nil then key='other' end
  if not groups[key] then groups[key]={rows={}} end
  local group=groups[key]
  group.rows[#group.rows+1]=row
 end

 -- 1. Limits and header. Each hardpoint header carries its side class.
 add('<div class="wtv-block" id="wtv-loadouts"><div class="wtv-block-header">外挂武器</div><div class="wtv-block-content"><div class="game-unit_chars">')
 for _,field in ipairs({{'maxloadMass','最大挂载重量'},{'maxloadMassLeftConsoles','左翼上限'},{'maxloadMassRightConsoles','右翼上限'},{'maxDisbalance','最大左右失衡'}}) do
  -- A missing limit renders no line at all rather than "— kg".
  if isNumber(limits[field[1]]) then add('<div class="game-unit_chars-line"><span>',field[2],'</span><span>',number(limits[field[1]]),' kg</span></div>') end
 end
 add('</div>')
 if #matrixRows>0 then
 add('<div class="wtv-table-wrap"><table class="game-unit_slot-list wtv-store-matrix"><thead><tr><th>挂载名称</th><th>重量</th>')
 for _,slot in ipairs(displaySlots) do
  local side=sideOf[tonumber(slot.index)]
  add('<th data-slot="',esc(slot.index),'"',side and (' class="wtv-hardpoint-'..side..'" title="'..sideLabels[side]..'"') or '','>',esc(slot.label or slot.display_index),'</th>')
 end
 add('</tr></thead>')

 -- 2. Matrix rows. Every body is a direct child of <table>, so each category
 --    is its own tbody and the existing tr[data-store] rows are unchanged.
 local function cellRow(row)
  local item=catalog[row.catalog_id] or {}
  local name=item.name or row.name or row.catalog_id
  add('<tr data-store="',esc(row.catalog_id),'"><th scope="row"><div role="button" tabindex="0" class="wtv-popover-trigger" data-popup="store-',esc(row.catalog_id),'">',row.count>1 and (tostring(row.count)..' × ') or '',esc(name),'</div></th><td>',isNumber(row.mass_kg) and (number(row.mass_kg)..' kg') or '—','</td>')
  for _,slot in ipairs(displaySlots) do
   local mount=(row.cells or {})[tostring(slot.index)]
   if mount then
    add('<td title="',esc(name),' × ',tostring(mount.count),'">',image(mount.icon_file or itemIcons[row.catalog_id]),mount.count>1 and ('<span class="wtv-slot-quantity">'..tostring(mount.count)..'</span>') or '','</td>')
   else
    add('<td></td>')
   end
  end
  add('</tr>')
 end
 -- Rows that carry no category of their own stay in a plain first tbody with
 -- no header row, so uncategorised data keeps its previous shape.
 for _,category in ipairs(categories) do
  local group=groups[category.key]
  if group then
   add('<tbody class="wtv-store-group" data-category="',category.key,'"><tr class="wtv-store-category"><th scope="colgroup" colspan="',tostring(2+columns),'">',category.label,'<span class="wtv-store-category-count">',tostring(#group.rows),'</span></th></tr>')
   for _,row in ipairs(group.rows) do cellRow(row) end
   add('</tbody>')
  end
 end
 add('</table></div>')
 end

 -- 3. Hidden parameter source per store. The name cells above point at these
 --    with data-popup="store-ID"; there is no separate ordnance accordion.
 add('<div class="wtv-popup-sources">')
 local described={}
 for _,item in pairs(catalog) do
  if item and item.id and not described[item.id] then
   described[item.id]=true
   add('<div class="wtv-popup-source" data-popup-id="store-',esc(item.id),'"><div class="game-unit_weapon"><span class="game-unit_weapon-title">',esc(item.name or item.id),'</span><div class="game-unit_chars">')
   if #(item.display_parameters or {})>0 then
    for _,param in ipairs(item.display_parameters) do add('<div class="game-unit_chars-line"><span>',esc(param.label),'</span><span title="',esc(param.source),'">',esc(param.value),'</span></div>') end
   else
    for _,field in ipairs(parameterFields) do
     if item[field[1]]~=nil then add('<div class="game-unit_chars-line"><span>',field[2],'</span><span>',number(item[field[1]]),' ',field[3],'</span></div>') end
    end
   end
   -- Extra values the catalog carries; printed only when they are real numbers.
   if isNumber(item.mach_limit) then add('<div class="game-unit_chars-line"><span>极限马赫数</span><span>',number(item.mach_limit),'</span></div>') end
   local guidance=type(item.guidance)=='table' and item.guidance.guidance
   if type(guidance)=='table' then
    for _,field in ipairs({{'lockDistance','锁定距离','m'},{'workTime','制导时间','秒'},{'warmUpTime','预热时间','秒'}}) do
     if isNumber(guidance[field[1]]) and not (field[1]=='workTime' and #(item.display_parameters or {})>0) then add('<div class="game-unit_chars-line"><span>',field[2],'</span><span>',number(guidance[field[1]]),' ',field[3],'</span></div>') end
    end
   end
   add('</div></div></div>')
  end
 end
 add('</div>')

 -- 4. Custom loadout editor. supported_custom==false never emits it.
 if loadouts.supported_custom~=false then
  add('<div class="wtv-loadout-editor" data-open="0" data-max-total="',attrNumber(limits.maxloadMass),'" data-max-left="',attrNumber(limits.maxloadMassLeftConsoles),'" data-max-right="',attrNumber(limits.maxloadMassRightConsoles),'" data-max-imbalance="',attrNumber(limits.maxDisbalance),'"><div class="wtv-loadout-toggle" role="button" tabindex="0">自定义挂载</div><div class="wtv-loadout-panel"><p>选择各挂点装备，查看重量、弹药数量和已解析规则的检查结果。</p><div class="wtv-loadout-choices">')
  local function optionMarkup(option,selected)
   local dependencies={} for _,d in ipairs(option.dependencies or {}) do dependencies[#dependencies+1]=tostring(d.slot)..':'..tostring(d.preset) end
   local blocking={} for _,d in ipairs(option.blocking or {}) do blocking[#blocking+1]=tostring(d.slot)..':'..tostring(d.preset) end
   local items={} for _,item in ipairs(option.items or {}) do items[#items+1]=tostring(item.id)..':'..tostring(item.count) end
   local name=option.name
   if type(name)~='string' or name=='' then
    local parts={}
    for _,item in ipairs(option.items or {}) do local entry=catalog[item.id] parts[#parts+1]=tostring(item.count)..' × '..tostring(entry and entry.name or item.id) end
    name=table.concat(parts,' + ')
   end
   if name=='' or name==nil then name=tostring(option.id or '') end
   -- These classes are also the CSS split of the option row (icon | text).
   -- They are not popover hooks: only .wtv-popover-trigger opens a popup.
   add('<div role="button" tabindex="0" class="wtv-store-choice wtv-slot-option" data-selected="',selected and '1' or '0','" data-option="',esc(option.id),'" data-mass="',attrNumber(option.mass_kg),'" data-dependencies="',esc(table.concat(dependencies,',')),'" data-blocking="',esc(table.concat(blocking,',')),'" data-items="',esc(table.concat(items,',')),'" data-modification="',esc(option.requires_modification),'"><span class="wtv-store-choice-icon">',image(option.icon_file,'32px'),'</span><span class="wtv-store-choice-text"><span class="wtv-store-choice-name">',esc(name),'</span>',isNumber(option.mass_kg) and ('<small class="wtv-store-choice-mass">'..number(option.mass_kg)..' kg</small>') or '','</span></div>')
  end
  for _,slot in ipairs(slots) do
   add('<div class="wtv-slot-choice" data-slot="',esc(slot.index),'" data-side="',esc(slotSide[tostring(slot.index)] or 'center'),'"><div class="wtv-slot-head"><strong>挂点 ',esc(slot.display_index or slot.index),'</strong></div><div role="button" tabindex="0" class="wtv-slot-trigger" data-slot="',esc(slot.index),'" aria-expanded="false"><span class="wtv-slot-trigger-icon">＋</span><span class="wtv-slot-trigger-name">空载</span><span class="wtv-slot-trigger-arrow" aria-hidden="true"></span></div><div class="wtv-slot-options">')
   -- Exactly one "empty" choice per slot, and every real option after it.
   local empty=nil
   for _,option in ipairs(slot.options or {}) do if (option.id==nil or option.id=='') and empty==nil then empty=option end end
   optionMarkup(empty or {id='',name='空载',mass_kg=0,items={}},true)
   for _,option in ipairs(slot.options or {}) do if option.id~=nil and option.id~='' then optionMarkup(option,false) end end
   add('</div></div>')
  end
  add('</div><div class="wtv-loadout-result" role="status"></div><p class="wtv-loadout-scope">检查挂点可用性、依赖、互斥、总重、两翼重量与失衡。按全部改装已解锁计算；不模拟燃油、阻力、极速和爬升率。</p></div></div>')
 else
  -- 5. Fixed presets: [{name, items:[{id,count}], mass_kg}], names via catalog.
  local presets=type(loadouts.presets)=='table' and loadouts.presets or {}
  if #presets>0 then
   add('<div class="wtv-loadout-fixed"><div class="wtv-loadout-fixed-title">固定挂载方案</div><table class="game-unit_slot-list wtv-fixed-presets"><thead><tr><th>挂载方案</th><th>重量</th></tr></thead><tbody>')
   for position,preset in ipairs(presets) do
    add('<tr class="wtv-preset" data-preset="',esc(preset.id or position),'"><th scope="row">')
    for _,item in ipairs(preset.items or {}) do
     local entry=catalog[item.id] or {}
     add('<div role="button" tabindex="0" class="wtv-popover-trigger" data-popup="store-',esc(item.id),'">',image(item.icon_file or itemIcons[item.id]),item.count and item.count>1 and (tostring(item.count)..' × ') or '',esc(entry.name or item.id),'</div>')
    end
    add('</th><td>',isNumber(preset.mass_kg) and number(preset.mass_kg)..' kg' or '—','</td></tr>')
   end
   add('</tbody></table><p class="wtv-loadout-scope">该载具的自定义挂载不可用，以上为游戏内固定方案。</p></div>')
  end
 end

 add('</div></div>')
 return table.concat(out)
end

return p
