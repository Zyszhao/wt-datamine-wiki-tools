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
