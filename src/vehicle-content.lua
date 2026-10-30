-- Only these two fixed child pages are editor-owned. Regular builds ship this
-- module, never the child pages. All paths are constructed from a validated ID.
local p={}
function p.render(frame,id,kind)
 if type(id)~='string' or #id>96 or not id:match('^[a-z0-9_%-]+$') then return '' end
 if kind~='basic-info' and kind~='player-content' then return '' end
 local title=id..'/'..kind
 local label=kind=='basic-info' and '基本信息' or '玩家内容'
 local help=kind=='basic-info' and '在此编辑载具描述。' or '在此编辑使用心得、历史、媒体与参考资料。'
 local body=frame:preprocess('{{#ifexist:'..title..'|{{:'..title..'}}|<p class="wtv-content-empty">'..help..'</p>}}')
 return '<div class="wtv-block wtv-editor-content wtv-'..kind..'" id="wtv-'..(kind=='basic-info' and 'general' or 'player-content')..'">'
 ..'<div class="wtv-block-header">'..label..'<span class="wtv-content-edit">[[Special:EditPage/'..title..'|编辑]]</span></div>'
 ..'<div class="wtv-block-content" data-content-page="'..title..'">'..body..'</div></div>'
end
function p.page(frame)
 local args=frame.args or {}
 return p.render(frame,args.id,args.kind)
end
return p
