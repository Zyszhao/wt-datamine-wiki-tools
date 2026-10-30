# 公开源码仓库边界

Git 根目录为 wt-wiki，与相邻 War-Thunder-Datamine 原始仓库相互独立。这里的“Git 工作区”是工具项目的独立 Git 仓库，不是对原始拆包仓库创建 Git worktree。

跟踪 scripts/、src/、项目 README、AGENTS.md、目标文档、Git 配置。脚本含共用 Lua/CSS/JS 的生成和部署逻辑，因此这些源码属于转换工具的完整组成部分。

不跟踪 evidence/、wiki/、work/、vendor/、Python 缓存、依赖环境及历史部署记录。这些路径仍保留在本地；没有为公开仓库搬移或删除原始拆包，也没有上传游戏图片、生成的全游戏 JSON、Wiki 页面包或第三方站点快照。

发布当前源码不表示 GUI 或完整武器弹药转换已完成，也不表示第三方数据可重新分发。当前未指定开源许可证；公开可见不自动授予任意再分发或使用权限。后续选定许可证时应单独核查源码及第三方材料权利，不能给游戏资产套用项目许可证。

维护 Git 时用显式路径暂存，并先查看 git diff --cached --stat 和 git diff --cached。不要为了使构建成功而将被忽略的输入或产物强制加入版本库。需要测试输入时使用自建合成夹具，或记录从合法本地输入生成的验证方法。

2026-10-30 冻结补充：可公开的 CODE-AND-FORMATS.md、FREEZE-2026-10-30.md 与 TEST-PAGE-CLEANUP.md 现纳入源码提交；逐页站点修订、清理 API 响应、图片和本机路径配置仍仅本地保存。

冻结完整性复核补充：config/vehicle-examples.json 与 config/vehicle-content-migration.json 是源码自有的示例选择与章节迁移协议，必须随源码跟踪；不包含真实站点页面或游戏数据。
