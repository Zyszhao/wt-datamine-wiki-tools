# War Thunder Datamine → Wiki Tools

将合法取得的本地 War Thunder datamine 转换为 MediaWiki JSON 数据页、Scribunto Lua 模块所需数据及手动导入 XML 的工具原型。当前采用 JSON + Lua，SMW 路线已停用。

## 项目目标

构建有 GUI 的本地维护工具：一键 diff、一键导出 JSON、一键生成全量／增量／分块 XML 导入包；支持全部数据或指定载具及其依赖的更新，并提供离线部署助手。维护者更新本地 datamine 后即可批量重新生成数据，避免逐页手工替换。默认不依赖 BWiki 机器人，导入由用户手动执行。

完整路线、数据模型、部署约束及验收标准见 [项目目标](docs/PROJECT-GOALS.md)。

## 当前状态

已有 Python 命令行转换、全局载具/group 简化索引、共享改装定义、通用科技树布局、共用 Lua/CSS/JS、离线预览检查、页面 XML 与 ZIP 打包。当前快照对全部 44 个 shop 国家／军种分支完成本地结构和 Lua 验证，演示部署为美国陆战、中国空军、德国近岸海军及 M1A2 改装。

**GUI、跨版本 diff、通用稳定分片、完整载具物理参数及武器弹药转换尚未实现。** 当前代码依赖本地 evidence 站点参考材料，不是仅克隆即可运行的完整应用；解除这些依赖是第一阶段目标。已有快照计数断言不等于任意新版本均可直接通过。

## 仓库范围

- `scripts/`：输入解析、转换、布局、验证、安装助手和打包工具。
- `src/`：共用 Lua、CSS、JavaScript 源码。
- `docs/PROJECT-GOALS.md`：未来产品目标和验收标准。
- `docs/PUBLIC-REPOSITORY.md`：公开发布边界。
- `AGENTS.md`：维护约定。

原始 datamine 不在本仓库。游戏图片、全游戏生成 JSON、站点快照、Wiki 生成页面/XML、离线报告和第三方依赖不提交；它们留在本地并被 `.gitignore` 排除。详情见[发布边界](docs/PUBLIC-REPOSITORY.md)。

## 本地配置与重建

Python 3.10+；Lua 验证需要 `pip install -r scripts/requirements.txt`。使用环境变量 `WTW_DATAMINE` 指定本地拆包根目录，默认相邻 `../War-Thunder-Datamine`。工具只读原始拆包。

当前还需自行提供 `evidence/bwiki-usa.json`、`bwiki-china-aviation.json`、`bwiki-germany-boats.json`（MediaWiki parse API 返回，包含 text），以及 `evidence/official-app.css`（现有资产提取器要求的官方 CSS 快照）。仓库不会分发这些第三方输入。`fetch_tree_evidence.py` 是可选只读采集辅助，不能自动准备全部材料，网络或网站版本变化可能导致失败。

准备输入后顺序运行：

```text
python scripts/prepare_assets.py
python scripts/build.py
python scripts/verify.py
python scripts/verify_trees.py
node scripts/browser-qa.cjs
node scripts/browser-trees-qa.cjs
python scripts/package.py
```

浏览器检查需本机 Playwright 与 Edge；可通过 `WTW_NODE_MODULES` 指向安装 Playwright 的 node_modules。生成结果分别位于 `wiki/`、`work/`，两者均不提交 Git。`tree_specs.py` 的 `DEPLOY_TREES` 控制打包的测试分支；其他树导出到 `work/exports/trees`。

当前已有本地验证，不代表生产 Wiki 导入、Scribunto 配额或全游戏与官方数据的一致性已认证。不会自动登录、修改或上传到 Wiki。

## 许可证

当前未指定源码许可证。公开仓库不自动授予开源许可证权限，正式分发许可需后续明确；任何游戏或第三方站点材料的权利不因本项目公开而改变。
