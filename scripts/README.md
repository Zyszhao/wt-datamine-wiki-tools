2026-10-30：先读 [冻结记录](../docs/FREEZE-2026-10-30.md)。下列生成命令用于恢复开发时重建；冻结期间不覆盖 ImportPack。

# 转换工具维护入口

当前产品状态与输入准备见 [项目 README](../README.md)；目标与后续阶段见 [PROJECT-GOALS.md](../docs/PROJECT-GOALS.md)。

| 源文件 | 职责 |
|---|---|
| paths.py | 项目、只读拆包、输出目录；WTW_DATAMINE 环境变量 |
| prepare_assets.py | 从本地参考材料提取旧 Wiki 展示映射、官方底板与本地预览图 |
| fetch_tree_evidence.py | 可选只读网络证据采集；不准备全部所需输入 |
| build.py | 解析经济/商店/标签/本地化/部分武器定义，输出 JSON、页面、XML、manifest |
| tree_specs.py | 国家/军种标签、范围及测试部署选择 |
| tree_policy.py | 游戏分类及特殊模式排除策略 |
| tree_layout.py | 通用列布局、研发关系绘制位置、资产映射与兼容性报告 |
| install_helper.py | 生成站点链接、完整源码复制窗口与手动部署说明 |
| verify.py | 当前演示数据/引用/大小/Lua/XML 往返检查 |
| verify_trees.py | 全分支结构和通用 Lua 验证，输出示例 HTML |
| browser-qa.cjs | 美国陆战桌面/手机交互与容器宽度回归检查 |
| browser-trees-qa.cjs | 中国空军/德国近岸海军交互、固定卡片大小与字体继承检查 |
| helicopter_layout.py | 直升机 rankPosXY 布局、卡片避让折线与研发箭头方向 |
| browser-helicopters-qa.cjs | 十国直升机桌面/手机本地预览、横向/分叉箭头、连线遮挡和交互验证 |
| package.py | 打包本地部署产物，不上传 |
| production_export_request.py | 从 shop 生成 44 棵正式树（含 10 国直升机）及现有依赖的 Special:Export 标题列表与离线复制助手 |
| production.py | 读取用户导出的 XML、旧树只读渲染证据及拆包转换产物，生成正式科技树全量/固定切片 XML、原页回退包、链接核对表和部署助手 |
| vehicle_page.py | 按游戏代码生成隔离的 JSON 载具页原型、Lua/CSS/JS、图片和 XML；默认测试 `il_leopard_2a6_hel`，不写线上 Wiki |
| vehicle_pack.py / vehicle_demo_pack.py | 正式载具包：文章使用代码标题，共用资源使用 WTJ；复用站内图标，生成三片、只读回退备份、标题迁移映射及清理清单；后者命令行兼容入口转到前者 |
| vehicle_delivery.py | 将正式载具页面和全站缺图统一交付到 ImportPack，核验文件与哈希，刷新旧标题清理并备份现存旧页，生成 DELIVERY.md 与专项弃用/管理员删除入口 |
| vehicle_content_migration.py | 从旧页 Export XML 一次性抽取配置章节到独立 `/basic-info`（描述）与 `/player-content`（其余人工内容）子页；缺章或导出中已有目标时拒绝，输出限定在 `wiki/`，不查询或编辑线上 Wiki |

载具页 JSON 的 `modification_name_overrides` 可保存单车特殊改装名称，格式为 `{"改装代码":"显示名称"}`。Lua 优先使用此映射，其次使用解析后的 `modifications[].name`，最后使用稳定代码。重新生成同一输出目录时保留此映射；不会把代码占位自动当成已翻译名称。当前原型仍内嵌默认改装名称，尚未改成运行时加载共享总表。改装连线仅使用 `reqModification`，不使用 `prevModification`。货币图标复用用户导出模板中的 BWiki 图片地址。
| browser-production-qa.cjs | 对正式包的 44 棵树进行桌面/手机宽度下的交互检查，不写入 Wiki |

## 数据与维护规则

2026-10-29 新要求：停止擅自添加测试题头。每次生成导入列表必须同时生成历史测试页清理清单，备份并验收替代页后实际删除退休页，再核对删除结果。规则见 [TEST-PAGE-CLEANUP.md](../docs/TEST-PAGE-CLEANUP.md)。`testing_cleanup.py` 从历史 XML/manifest 和登记证据汇总精确标题，输出 CSV、JSON、导出备份列表及管理员删除入口；`--refresh-site` 只读补查站点，失败明确记录。此前错误命名的载具生成页和包全部弃用；当前正式包从源码和载具数据重建。旧载具演示生成器已移除，兼容命令转到正式入口，验证器拒绝旧演示包。旧 XML 仅作为历史清点和备份证据，不再导入。

- shop.blkx 决定商店分支、列、组和顺序；wpcost.blkx 提供经济等级、BR、价格和研发关系；unittags.blkx 提供角色和特殊模式标志。
- BR 使用 round_half_up(economicRankMODE / 3 + 1, 0.1)，原 br 数组顺序仍为 ab/rb/sb。飞机另导出 `br_ground_rb`：优先使用 economicRankTankHistorical，缺失时沿用 economicRankHistorical；对应界面“陆战历史”（grb），支持卡片显示与独立区间筛选。回退规则来自游戏 ranks_common_shared.nut 的 get_unit_blk_economic_rank_by_mode。
- 全局简化索引包含中文载具名、group、等级、三模式 BR 与类别；树 JSON 仅保存布局/关系/展示映射等本树内容。
- 共享改装定义保存描述和图标，载具本地只引用定义并保存费用和位置；当前武器弹药读取仅服务部分改装名称解析，不是完整武器弹药转换器。
- 生成输出改动必须回到 scripts/ 或 src/ 源码，不能仅修改 wiki/pages。
- 当前存在绑定游戏快照的断言。遇到新版本先核对差异，不能删除断言伪造通过。
- 正式 Wiki 加载方式为样式模板引用本站既有 ResourceLoader，再加载 MediaWiki:WTJ.js；旧离线回归包仍保留 MediaWiki:WTJTreeTesting.js；不需要个人 JS/CSS。导入权限、二进制图片上传和线上资源配额另行验收。
- 公开仓库不提交 evidence/、wiki/、work/、vendor/；不要 force add 真实游戏或第三方站点材料。未来自动测试优先使用自建合成夹具。

正常构建流程与所需输入在项目 README 中；当前 package.py 仍引用本地历史部署文档，此类文档不随公开仓库分发。解除本机材料及部署说明硬依赖属于可复现核心阶段，不能称为已完成。

## 直升机本地测试

依次运行 `prepare_assets.py` → `build.py` → `verify.py` → `verify_trees.py`，然后运行 `node scripts/browser-helicopters-qa.cjs`（沿用 `WTW_NODE_MODULES`）。本地入口为 `work/preview/helicopters.html`，含十国预览；浏览器报告为 `work/reports/helicopter-browser.json`。此路径不增加正式部署目标或修改既有测试导入包的页面数。

直升机以 `rankPosXY` 确定列及等级内行，保留空位和组层坐标；入口解锁条件从 `unlocks.blkx` 读取并展示为“或”关系说明条。研发边保留原始成员代码，布局计算避让卡片的折线，并分别处理同排行向和跨行向下箭头。`*_killstreak` 和 `ah_1f_event` 按用户指定排除出百科树，全局索引仍保留原始记录。当前 2.59.0.75 快照十国共 112 架；数量断言不能随意更改。预览图片使用本地拆包素材，文章链接是测试目标，正式站内链接/素材及线上验收另行处理。

## 当前正式科技树打包路径

## 本地陆战 SVG 箭头试验与官方图标调查

在正常构建后运行 `python scripts/ground_arrow_trial.py`，再运行 `node scripts/browser-ground-arrows-qa.cjs`。试验入口为 `work/preview/usa_army_svg_arrows.html`；它使用共用 `research_edges.py` 为美国陆战计算 SVG 路径，保持原节点布局与正式打包数据。报告为 `work/reports/ground-arrow-trial.json` 和 `ground-arrow-browser.json`。当前快照 154 辆、66 条主树边、17 条组内边。

`python scripts/fetch_official_rendering.py` 只读抓取官方 ground 页面、页面实际引用的 CSS/JS 和五类陆战 SVG；产物在 `work/research/official-svg/`。网络失败时应保留此前抓取，不把失败当作新证据。已有五类 SVG 后，运行 `python scripts/official_svg_sample.py` 生成离线 `verified-svg.html`。官方载具主体是 slots PNG，类别轮廓才是 SVG；SVG File 缩略图可能仍由 Wiki 栅格化，不能将上传 SVG 等同于浏览器直接矢量渲染。调查见 `work/reports/official-svg-rendering.md`。

## 官方列表类型小图标（更正）

用户指定的列表 svg/use 使用 `/static/class_icon/`；此前 `/static/class_svg/` 轮廓调查不对应本需求。运行 `node scripts/capture_type_symbols.cjs`（沿用 WTW_NODE_MODULES）只读采集五类列表，再运行 `python scripts/type_symbol_sample.py`，生成 `work/research/type-symbols/sample.html`。形状、颜色与类别语义独立保存，保留跨类别复用。产物不提交。

折叠组只绘制 layout.internal_edges，采用弹窗局部 SVG 坐标；陆战检查覆盖真实边身份、箭头间距和无依赖组零连线。

## 正式科技树包生成

在现有构建输出准备好后，用 `python scripts/production_export_request.py` 生成站内导出标题列表。用户从 Special:Export 保存当前修订 XML 后，运行 `python scripts/production.py --export-xml <主导出.xml> <补充导出.xml>`。路径参数需放在此选项后；源码和渲染快照分别保存到被 Git 忽略的 `evidence/production/`。可选 `--refresh-rendered` 从公开页面只读补充实际渲染链接；受站点防护影响时保留已有证据，不可宣称在线核对完成。

生产生成器使用游戏 shop 的全部 44 个分支（含直升机），输出到 `wiki/production/`；只替换旧页面 Tree-Start 至 Tree-End 区域，保留其余源码。它不会迁移载具文章、修改 Tr 或替换 Common.js。实际渲染的旧目标优先于 Tr 查表，当前源码的手动指定链接优先；通过 API 核对页面存在性，未确认目标单独列入 `manifest.json` 和 `link-audit.csv`，不能将其描述为已验证可用。用户导出和只读快照均不得提交到公开仓库。

正式图片命名：待上传的载具/group 图使用 `<游戏代码>.png`，不加 WTJ 前缀；JSON `assets.file`、实际上传文件和 Lua 输出的 File 引用保持一致。五张背景复用本站 `Item own.png`、`Item prem.png`、`Item squad.png`、`Item group.png`、`Item group prem.png`，模块中的下划线写法与空格等价。`evidence/production/background-files-current.json` 是只读 imageinfo 缓存，首次缺失时生成器自动读取，部署包记录为 `existing-backgrounds.json`；站点重命名后应刷新该缓存并同步引用。正式包不依赖旧的 `WTJTreeTesting_folder*` 或 `WTJ_folder*` 图片；历史测试构建与其本地预览素材另行保留，不是正式上传清单。

随后运行 `node scripts/browser-production-qa.cjs`（沿用 `WTW_NODE_MODULES`）；检查使用正式 Lua 输出与正式 JS/CSS，但阻止远程图片请求以稳定验证交互，因此不替代线上图片/字体/加载器和 Scribunto 配额验收。全站加载兼容性报告来自用户导出的 Common.js 与 ResourceLoader 源码；当前使用已有加载路径加载 `MediaWiki:WTJ.js`，无需个人脚本。现有固定切片仅设置每片 15 页/1500000 源码 UTF-8 字节，未实现未来 GUI 可配置的最终 XML 文件大小阈值。

正式交付统一为工作区 `ImportPack/`，每次生成清空重建，不生成 ZIP；根目录为待上传图像，`Full/` 为全量 XML，`Slices/` 为顺序导入切片，`Rollback/` 为回退 XML。报告和部署说明保留在 `wiki/production/`。新增导出 XML 与已保存导出合并，最新同名页优先，不将补充导出缺页当作站点不存在。

`Repair/WTJ-tree-sticky-offset.xml` 仅更新 MediaWiki:WTJ.js，适用于已导入吸顶工具栏、飞机陆战历史及 CSS 修复的站点。脚本读取站点可见固定导航栏的底边，动态设置整条工具栏的数值 top，避免权重模式按钮被站点导航遮挡；手机端隐藏导航时回到 top:0。滚动、窗口变化及导航栏尺寸/类变化时重新测量。导入后强制刷新脚本缓存。完整新部署使用 Full 或 Slices。

`production.py` 打包前调用 `verify_wiki_css.py`，将完整样式提交给本站只读 parse API，并解码 CSS 扩展实际返回的样式；任何拒绝、缺失或网络失败均停止打包。用含 var() 的负面对照复现整份样式被替换为 insecure input，报告为 `wiki/production/wiki-css-validation.json`。正式浏览器检查使用 `site-parsed-tree.css`，并核对报告与当前 CSS 源码哈希一致，避免原始 CSS 在浏览器正常但部署后失效。

运行 `python scripts/verify_wiki_markup.py` 可将实际生成的版本标签提交给本站只读 parse API，并以旧标签作负面对照；结果写入 `wiki/production/wiki-markup-validation.json`，网络失败不算通过。

## 改装研发树预览（2026-10-26）

`vehicle_page.py` 现在根据 `modifications.blkx` 的 `modClass` 和 `image`、载具 `wpcost` 的 `tier`、`reqModification`、`prevModification` 生成图标卡片树。保留游戏字段顺序，按类别和层级定位；跨层关系预留通道，费用通过卡片详情显示。图标直接复制本地拆包素材，图标的每车 override 优先于共享定义。名称缺失时保留原码；弹药包名优先从本车挂载武器的 bulletName 与中文本地化解析。

`modification_tier_requirements` 的 `{tier,next_tier,count,source}` 使用 `needBuyToOpenNextInTierN`，其语义由游戏 `scripts/weaponry/modstree.nut:getNextTierModsCount` 核实：在 tier N 已研发的改装项数量，不是跨层累计数量，也不是虚构玩家进度。`requires` 是前置要求（实线）；`previous` 对应研发树排列顺序（虚线），不是新增硬性解锁要求。当前连线是 JS 创建的 canvas；禁用 JS 时原生卡片详情仍显示前置文字。

载具主页面为薄壳，程序区与玩家内容区通过 `模板:WTJ/vehicle-page` 拼合。模板用 Lua `content_id` 白名单生成固定子页标题；常规构建绝不导出 `/user-content`，编辑者只更新对应子页。迁移包只导入一次；导入前需要在线确认目标子页不存在，离线工具不做该查询，也不写线上 Wiki。冻结的 `M1A2_SEPv3.wikitext` 用来验证六个章节的拆分；豹 2HEL 预览用本地 fixture 检查拼合位置，不会把 fixture 写进 XML。

本地生成与检查：

```text
python scripts/vehicle_page.py
python scripts/vehicle_page.py --unit mig_35 --out wiki/vehicle-prototype-mig35
node scripts/browser-vehicle-modifications-qa.cjs
```

可选环境变量 `WTW_NODE_MODULES` 指向含 playwright 的 node_modules，`WTW_BROWSER_PATH` 指向浏览器可执行文件。预览目录内 `index.html` 为整页，`modifications.html` 仅显示改装区。当前示例为豹 2HEL（18 件改装）与米格-35（28 件改装、8 条研发依赖），覆盖 1440/390px 图标、弹窗、内部滚动和页面溢出。米格-35 当前无同层横向依赖，不能单独作为横向连线验收案例。

## 米格-35 航空载具数据与挂载（2026-10-28）

`vehicle_official_reference.py` 用标准库 HTMLParser 读取用户保存的官方 MHTML；`aircraft_presentation.py` 将飞行性能、一般特征、重量和限制转换为中文显示。街机/历史、基础/完全体的结果来自具备哈希的官方快照，不能冒充从 BLK 完整重算的性能。弹链顺序由本机炮 BLK 的各 bullet 子块生成，官方参考补充穿深并逐项核对图标序列；Lua/CSS 将组成图标并排拼合。

`aircraft_loadouts.py` 递归解析容器到弹药，生成固定资源 ID 的共享参数与每车挂点配置。`vehicle_page.py` 导出四个 `data/ordnance/aircraft-N.json` 稳定哈希分片，载具页只保存所需分片引用；共享分片在同批构建/打包中合并，相同 ID 的事实冲突会报错。后续增加机型时必须把涉及的共享分片作为依赖一起导入，不能将单车子集覆盖成全局总表。全量游戏未来应将分片数做成版本化配置，目前仅验证米格-35。

`src/loadouts.lua` 是独立挂载组件，生成 46 行、11 列的矩阵、唯一弹药参数区和自定义挂载选择器。选择器计算总挂载、两翼重量、失衡和弹药数量，检查挂点选择、依赖与互斥；按全部改装已解锁计算，不提供玩家账号进度，也不模拟燃油、阻力、极速、爬升率或战斗效果。显示通过仅指已解析的静态规则，不能宣称与游戏所有运行时限制等价。引擎版本、特定赛事/任务与服务器限制仍需另行覆盖。

验证：`python scripts/verify_mig35_reference.py` 逐行比对 46 行质量、图标和全部挂点，与 5 种弹链序列、穿深核对；`node scripts/browser-mig35-loadouts-qa.cjs` 测试两种宽度、模式数值、T220 依赖、配对副油箱、失衡及侧重上限。`verify_vehicle_site.py` 通过只读 parse 核对当前 CSS、data 属性与控件标记；BWiki 不接受 details/summary，也会剥除初始 aria-pressed，所以使用 div + data-selected/data-open，由 JS 加入 ARIA 状态。仍需导入后线上验收。

## 航空挂载与传感器更新（2026-10-28，第二轮）

`aircraft_legacy.py` 补充 Pe-8 固定预设和防御炮塔兼容；`vehicle_sensors.py` 生成本车设备定义/安装引用/特征按钮；`vehicle_economy.py` 使用游戏资料卡公式重算维修与收益。`loadouts.lua` 按游戏触发分类输出矩阵，名称点击查看弹药，下拉列表选择挂载；无自定义支持时输出固定方案表。飞机头图分房权重有AB/RB/SB/GRB四列，其他分支仅AB/RB/SB；使用稳定的branch_id判断。性能模式按钮仍仅AB/RB。外挂表格带竖线，弹链图标与名称在两个固定区域分别居中对齐。

新增验证 `python scripts/verify_aircraft_system.py` 和 `node scripts/browser-aircraft-system-qa.cjs`。Pe-8 使用 `python scripts/vehicle_page.py --unit pe-8_m82 --out wiki/vehicle-prototype-pe8` 构建；官方只读HTML参考保存在 `work/research/pe8-official.html`。该参考不是通用自动抓取能力。当前交付说明见 `wiki/production/vehicle-pages/DELIVERY.md`。正式包有3辆车、19页、3片；发布仍需要只读站点parse、文件查询和浏览器验收全部成功。旧 `vehicle-demo` 输出移入 `work/history/retired-vehicle-demo-*` 留作历史证据，不能继续导入。

正式载具包使用 `python scripts/vehicle_pack.py`（旧 `vehicle_demo_pack.py` 命令转到此入口）。默认三辆文章标题为 `il_leopard_2a6_hel`、`mig_35`、`pe-8_m82`；共用模板、模块、数据和脚本使用 WTJ。两个人工子页直接位于 `<代码>/basic-info`、`<代码>/player-content`。旧→新标题映射、回退 XML、精确 create/update 清单与清理入口位于 `wiki/production/vehicle-pages/`，本地生成不表示线上已迁移或删除。

全站载具图片统一命名：科技树小图 `<代码>.png`；资料卡大图 `<代码>_资料卡.png`。`asset_naming.py` 是 Wiki 生成端规则；独立拆包软件 `wt-exporter/image_export.py` 使用同一规则并通过 GUI/CLI 导出。小图、改装及挂载保留拆包原名，大图仅增加固定后缀；所有图片保留原始字节，不去白底、不缩放、不覆盖小图。

全拆包图片补充：`python scripts/audit_game_images.py` 遍历全局及每车改装、全部 gamedata 的 `iconType` 和游戏回退规则、载具大小图，另列未发现当前引用的挂载同族 PNG。分别查询大小图的实际目标名及改装 Mods 别名，查询失败保留 unknown。输出 `wiki/production/game-image-audit/` 的清单、站内证据与逐图哈希。原始拆包变更后须重新生成 inventory；`--reuse-inventory` 仅用于原始输入未变，站内缓存最多六小时，`--refresh` 强制重查。`--publish` 拒绝保留测试标题的旧 XML，先备份再重建 ImportPack，并保留已核对的正式页面包；大小图可同时上传。根目录已有的同名同内容图片不重复复制。

正式交付顺序：构建与相关验证 → `vehicle_pack.py` → `browser-vehicle-demo-qa.cjs`（现检验正式目录）→ `verify_vehicle_site.py` → `vehicle_delivery.py --publish`。统一入口依次调用正式页面打包、图片补充及上传核验，再只读刷新历史清理，核对并备份现存错误命名页面。输出总说明 `wiki/production/vehicle-pages/DELIVERY.md`、精确上传清单 `UPLOAD-LIST.md`、专项 `Retired/RETIREMENT.md` 与管理员删除入口 `Retired/DELETE.html`。核对失败时停止，不将未知状态当作缺失。验证检查 XML、正式标题、无测试引用、原图哈希、MediaWiki 规范化后图片命名唯一与站内缺失证据；不进行线上写入。原始图片库存未变时统一入口使用 `--reuse-inventory`，拆包更新后须先重新运行完整图片审计。

旧生成页整页弃用，不迁移旧生成源码，也不依赖旧名重定向；人工内容子页单独保留迁移。旧页源码备份放在 `Retired/`，不进入 ImportPack，避免误导入后恢复错误标题。专项弃用只覆盖载具包对应的旧标题；通用 Cleanup 中其他功能的共享资源须另查依赖。管理员验收正式替代后执行删除并重新查询；本地弃用和 XML 导入均不等于线上删除。

`python scripts/verify_loadout_icon_scope.py` 使用A-26B和A2D同一枚AN-M64A1炸弹的不同真实挂点图标验证载具局部选择。矩阵cells、options、固定方案items与item_icons保存在载具JSON；共享弹药分片不包含图标字段，Lua不以共享弹药图标回退。共享参数去重仍对物理事实冲突报错。
