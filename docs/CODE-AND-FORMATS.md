# 代码与文件协议

本文件记录 2026-10-30 的实际协议，不能将未来目标解释为已实现。新文件采用 UTF-8、LF 和文件末尾换行；现有紧凑源码保持原样，不因冻结批量格式化。JSON 禁止 NaN/Infinity；外部游戏输入允许 UTF-8 BOM。EditorConfig 和 Git attributes 负责新编辑及文本换行，二进制图片不作转换。

## 目录与所有权

| 位置 | 内容和规则 |
|---|---|
| scripts/ | Python 转换、验证、打包及浏览器检查 |
| src/ | Lua、CSS、JS 源码；呈现修改从这里开始 |
| docs/ | 可公开的技术协议、目标和维护说明 |
| evidence/、Reference/ | 本机只读站点/人工参考输入，不发布 |
| wiki/、work/ | 生成输出与检查报告，不进入源码提交 |
| ImportPack/ | 用户手动导入的唯一交付目录；按约定核对路径后才可清空重建 |
| War-Thunder-Datamine/ | 独立的只读上游克隆，不写构建输出 |

Python 3.10+；Lua 检查依赖 scripts/requirements.txt。浏览器检查使用 Playwright 与 Edge，可配置 WTW_NODE_MODULES、WTW_BROWSER_PATH。WTW_DATAMINE 必须指向所需文件完整、版本一致的拆包；不依赖运行命令时的当前目录。

## Wiki 数据与标题

- 稳定实体 ID 使用游戏代码，文章标题使用载具代码，共用模块、模板、数据与脚本使用 WTJ。页面名、命名空间、内容模型、依赖和 create/update 在导入前列清。
- 旧 build.py 的 WTJTreeTesting 输出只用于离线回归；正式交付走 production.py / vehicle_pack.py，不再以测试包作为默认安装包。独立软件的 WTJExporterTesting 是另一份候选协议，尚未整合为正式 Wiki 部署。
- shop 决定分支、列、组与顺序；wpcost 决定经济、BR 与研发关系；unittags 提供角色/特殊模式标志。BR 按 ROUND_HALF_UP 计算至一位小数，数组顺序 AB/RB/SB；飞机 GRB 优先 economicRankTankHistorical，否则用 Historical。
- JSON 保存事实和稳定引用；树数据保存布局/关系/显示映射。当前航空弹药按稳定 ID 汇入 4 个哈希分片，冲突报错；只验证了有限机型，不能用单车子集覆盖全局共享表。
- 官方快照提供的性能必须记录来源及哈希，不能说成由 BLK 全量计算。缺失翻译、图片、运行时限制单列，不伪造完成。
- 程序页与人工 `/basic-info`、`/player-content` 分离。常规包不得覆盖人工内容；一次性迁移须有旧源备份与目标存在性核实。

MediaWiki 将下划线与空格等价处理，文件首字母按本站规则规范化；其余字符的大小写不能整体折叠。科技树小图 `<代码>.png`、资料卡 `<代码>_资料卡.png`；改装/挂载保留原名并优先复用站内别名。图片复制保留原字节，不缩放、去底或让大小图共用标题。

## XML、图片与部署

XML 为 MediaWiki export-0.11，JSON 页使用 json 内容模型，源码 UTF-8 字节数必须与声明一致。Full 与全部 Slices 应具有相同标题/内容集合，切片按顺序导入，不同时重复导入总包。现有 Wiki 固定阈值为每片 15 页、1,500,000 源码字节；不能称为完整 XML 文件大小限制。

ImportPack 根目录放当前页面必要且确认缺失/需更新的图片，Full、Slices、Rollback、Repair 分目录；SupplementalImages 放全站补图。报告、清单与管理员清理入口位于 wiki/production，不混进上传图片目录。不生成 ZIP。用户旧导出按新同名修订优先合并；导出缺页不能证明线上不存在，Rollback 必须保存真实旧源码。

Lua 输出应符合本站 MediaWiki 实际允许的 HTML/CSS；本机浏览器正常不能代替站点只读 parse。已知 details/summary 和部分初始 ARIA 属性会被处理，交互以经站点验证的标记与 JS 为准。检查报告须与当前源码哈希一致。网络失败记录为未核对，不能冒充成功。

## 独立软件协议

GUI/CLI 共用 config_store、core、extractor、directory_state；同一 state 禁止并发写入。正常 stdout 为单个 JSON，日志 stderr；退出码 0 成功、2 错误、3 版本警告、130 取消。全局 --state-dir / --config 位于子命令前。

catalog 为 schema:1、kind:vehicle_index、records 按代码索引，并记录 _meta.sources 的 SHA-256。配置前缀当前受限 WTJExporterTesting/；批次包括 catalog、pages、Slices、manifest 和 INSTALL。软件另支持 max_pages / max_text_bytes / max_xml_bytes 三个阈值，不能与 Wiki 生成器的两项固定阈值混淆。

baseline 只表示已导入并人工验收的 catalog；扫描历史、最近目录缓存与 baseline 分开。图片导出读取已有完整拆包；char/lang build 不会提取图片。外部 wt_ext_cli 独立下载部署，保留 LICENSE/README/NOTICE（如存在）、URL、版本和哈希，不嵌入本软件源码或发布包。
