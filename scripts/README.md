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
| package.py | 打包本地部署产物，不上传 |
| production_export_request.py | 从 shop 生成 34 棵正式树及现有依赖的 Special:Export 标题列表与离线复制助手 |
| production.py | 读取用户导出的 XML、旧树只读渲染证据及拆包转换产物，生成正式科技树全量/固定切片 XML、原页回退包、链接核对表和部署助手 |
| browser-production-qa.cjs | 对正式包的 34 棵树进行桌面/手机宽度下的交互检查，不写入 Wiki |

## 数据与维护规则

- shop.blkx 决定商店分支、列、组和顺序；wpcost.blkx 提供经济等级、BR、价格和研发关系；unittags.blkx 提供角色和特殊模式标志。
- BR 使用 round_half_up(economicRankMODE / 3 + 1, 0.1)，顺序为 ab/rb/sb。
- 全局简化索引包含中文载具名、group、等级、三模式 BR 与类别；树 JSON 仅保存布局/关系/展示映射等本树内容。
- 共享改装定义保存描述和图标，载具本地只引用定义并保存费用和位置；当前武器弹药读取仅服务部分改装名称解析，不是完整武器弹药转换器。
- 生成输出改动必须回到 scripts/ 或 src/ 源码，不能仅修改 wiki/pages。
- 当前存在绑定游戏快照的断言。遇到新版本先核对差异，不能删除断言伪造通过。
- 当前 Wiki 加载方式为样式模板引用本站既有 ResourceLoader，再加载 MediaWiki:WTJTreeTesting.js；不需要个人 JS/CSS。导入权限、二进制图片上传和线上资源配额另行验收。
- 公开仓库不提交 evidence/、wiki/、work/、vendor/；不要 force add 真实游戏或第三方站点材料。未来自动测试优先使用自建合成夹具。

正常构建流程与所需输入在项目 README 中；当前 package.py 仍引用本地历史部署文档，此类文档不随公开仓库分发。解除本机材料及部署说明硬依赖属于可复现核心阶段，不能称为已完成。

## 当前正式科技树打包路径

在现有构建输出准备好后，用 `python scripts/production_export_request.py` 生成站内导出标题列表。用户从 Special:Export 保存当前修订 XML 后，运行 `python scripts/production.py --export-xml <主导出.xml> <补充导出.xml>`。路径参数需放在此选项后；源码和渲染快照分别保存到被 Git 忽略的 `evidence/production/`。可选 `--refresh-rendered` 从公开页面只读补充实际渲染链接；受站点防护影响时保留已有证据，不可宣称在线核对完成。

生产生成器使用游戏 shop 的全部非直升机分支，输出到 `wiki/production/`；只替换旧页面 Tree-Start 至 Tree-End 区域，保留其余源码。它不会迁移载具文章、修改 Tr 或替换 Common.js。实际渲染的旧目标优先于 Tr 查表，当前源码的手动指定链接优先；通过 API 核对页面存在性，未确认目标单独列入 `manifest.json` 和 `link-audit.csv`，不能将其描述为已验证可用。用户导出和只读快照均不得提交到公开仓库。

正式图片命名：待上传的载具/group 图使用 `<游戏代码>.png`，不加 WTJ 前缀；JSON `assets.file`、实际上传文件和 Lua 输出的 File 引用保持一致。五张背景复用本站 `Item own.png`、`Item prem.png`、`Item squad.png`、`Item group.png`、`Item group prem.png`，模块中的下划线写法与空格等价。`evidence/production/background-files-current.json` 是只读 imageinfo 缓存，首次缺失时生成器自动读取，部署包记录为 `existing-backgrounds.json`；站点重命名后应刷新该缓存并同步引用。正式包不依赖旧的 `WTJTreeTesting_folder*` 或 `WTJ_folder*` 图片；历史测试构建与其本地预览素材另行保留，不是正式上传清单。

随后运行 `node scripts/browser-production-qa.cjs`（沿用 `WTW_NODE_MODULES`）；检查使用正式 Lua 输出与正式 JS/CSS，但阻止远程图片请求以稳定验证交互，因此不替代线上图片/字体/加载器和 Scribunto 配额验收。全站加载兼容性报告来自用户导出的 Common.js 与 ResourceLoader 源码；当前使用已有加载路径加载 `MediaWiki:WTJ.js`，无需个人脚本。现有固定切片仅设置每片 15 页/1500000 源码 UTF-8 字节，未实现未来 GUI 可配置的最终 XML 文件大小阈值。
