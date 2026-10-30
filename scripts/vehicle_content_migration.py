"""Create a one-time XML package that splits hand-written article sections into two protected subpages."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from paths import ROOT, WIKI

XML_NS = "http://www.mediawiki.org/xml/export-0.11/"
ET.register_namespace("", XML_NS)
HEADING = re.compile(r"(?m)^(?P<marks>={2,6})[ \t]*(?P<title>.*?)[ \t]*(?P=marks)[ \t]*\r?$")
BLOCK_TAG = re.compile(r"<(nowiki|pre|source|syntaxhighlight|code)\b[^>]*>", re.IGNORECASE)
MAX_CONTENT_BYTES = 256 * 1024
BASIC_INFO_PAGE = "basic-info"
PLAYER_CONTENT_PAGE = "player-content"
DESCRIPTION_SECTION = "描述"


def heading_matches(wikitext: str) -> list[tuple[int, int, str]]:
    """Find real heading lines while ignoring headings in comments/code tags."""
    result: list[tuple[int, int, str]] = []
    offset = 0
    comment = False
    protected: str | None = None
    for line in wikitext.splitlines(keepends=True):
        visible: list[str] = []
        cursor = 0
        while cursor < len(line):
            if comment:
                end = line.find("-->", cursor)
                if end < 0:
                    cursor = len(line)
                    break
                cursor = end + 3
                comment = False
                continue
            if protected:
                close = re.search(r"</" + re.escape(protected) + r"\s*>", line[cursor:], re.IGNORECASE)
                if not close:
                    cursor = len(line)
                    break
                cursor += close.end()
                protected = None
                continue
            comment_at = line.find("<!--", cursor)
            tag = BLOCK_TAG.search(line, cursor)
            tag_at = tag.start() if tag else -1
            if comment_at >= 0 and (tag_at < 0 or comment_at < tag_at):
                visible.append(line[cursor:comment_at])
                comment = True
                cursor = comment_at + 4
                continue
            if tag:
                visible.append(line[cursor:tag.start()])
                name = tag.group(1)
                if line[tag.start():tag.end()].rstrip().endswith("/>"):
                    visible.append(tag.group(0))
                    cursor = tag.end()
                    continue
                close = re.search(r"</" + re.escape(name) + r"\s*>", line[tag.end():], re.IGNORECASE)
                if close:
                    cursor = tag.end() + close.end()
                else:
                    protected = name
                    cursor = len(line)
                continue
            visible.append(line[cursor:])
            cursor = len(line)
        candidate = "".join(visible)
        match = HEADING.fullmatch(candidate.rstrip("\r\n"))
        if match:
            result.append((offset, len(match.group("marks")), match.group("title").strip()))
        offset += len(line)
    return result


def strip_own_heading(block: str) -> str:
    """Drop the section's own level-2 heading line; later levels and all body text are kept."""
    head, _, rest = block.partition("\n")
    if not HEADING.fullmatch(head.rstrip("\r")):
        raise ValueError("待拆分章节缺少可去除的一级标题行：" + head[:40])
    return rest.replace("\r\n", "\n").strip("\n").rstrip() if rest else ""


def sections_to_migrate(wikitext: str, wanted: set[str]) -> tuple[str, str, list[str]]:
    """Split wanted level-2 sections into the basic-info and player-content wikitext blocks.

    The 描述 (description) section goes to basic-info with its own level-2 heading removed;
    every other wanted section goes to player-content with its heading intact.
    Returns (basic_info, player_content, missing), where missing lists configured sections
    that the source page does not contain.
    """
    headings = heading_matches(wikitext)
    blocks: dict[str, str] = {}
    for i, (start, level, title) in enumerate(headings):
        end = len(wikitext)
        for following_start, following_level, _ in headings[i + 1:]:
            if following_level <= level:
                end = following_start
                break
        if level == 2 and title in wanted:
            if title in blocks:
                raise ValueError("源页面的迁移章节重复，无法安全拆分：" + title)
            blocks[title] = wikitext[start:end].rstrip()
    missing = sorted(wanted - set(blocks))
    description = blocks.get(DESCRIPTION_SECTION)
    basic_info = strip_own_heading(description) if description is not None else ""
    player = [body for title, body in blocks.items() if title != DESCRIPTION_SECTION]
    return basic_info, "\n\n".join(player) + "\n" if player else "", missing


def read_export(path: Path) -> tuple[dict[str, tuple[str, str, str]], str]:
    root = ET.parse(path).getroot()
    if root.tag != "{" + XML_NS + "}mediawiki":
        raise ValueError("输入文件不是 MediaWiki Export XML。")
    ns = {"m": XML_NS}
    pages = {}
    for page in root.findall("m:page", ns):
        title = page.findtext("m:title", namespaces=ns)
        revisions = page.findall("m:revision", ns)
        if not revisions:
            raise ValueError("导出页面没有 revision：" + str(title))
        revision = max(revisions, key=lambda item: item.findtext("m:timestamp", default="", namespaces=ns))
        text = revision.findtext("m:text", default="", namespaces=ns)
        model = revision.findtext("m:model", default="wikitext", namespaces=ns)
        timestamp = revision.findtext("m:timestamp", default="", namespaces=ns)
        if title:
            if title in pages:
                raise ValueError("导出 XML 中源标题重复，无法确定应迁移的修订：" + title)
            pages[title] = (model, text, timestamp)
    return pages, ns["m"]


def target_titles(namespace: str, code: str) -> tuple[str, str]:
    base = code + "/"
    return base + BASIC_INFO_PAGE, base + PLAYER_CONTENT_PAGE


def build_migration(export_xml: Path, mappings: list[str], out: Path,
                    *, allow_missing: bool = False,
                    acknowledge_live_target_check: bool = False) -> dict:
    config = json.loads((ROOT / "config/vehicle-content-migration.json").read_text(encoding="utf-8"))
    namespace = config["namespace"]
    if namespace != "WTJ":
        raise ValueError("当前迁移使用正式资源命名空间 WTJ，目标为载具代码下的固定子页。")
    player_sections = set(config["player_sections"])
    basic_sections = set(config["basic_info_sections"])
    if player_sections & basic_sections:
        raise ValueError("配置错误：basic-info 与 player-content 章节不得重叠：" +
                         "、".join(sorted(player_sections & basic_sections)))
    if DESCRIPTION_SECTION not in basic_sections:
        raise ValueError("配置错误：basic-info 必须包含“" + DESCRIPTION_SECTION + "”章节。")
    pages, _ = read_export(export_xml)
    export_titles = {title.casefold() for title in pages}
    if not mappings:
        raise ValueError("请用 --page '现有页面标题=载具代码' 指定至少一个迁移源。")
    if not acknowledge_live_target_check:
        raise ValueError("离线导出无法证明两个目标子页目前都不存在。请在导入前自行核对线上目标，并显式传入 --acknowledge-live-target-check。")
    try:
        out.resolve().relative_to(WIKI.resolve())
    except ValueError as exc:
        raise ValueError("一次性迁移包只能写入仓库的 wiki/ 输出目录。") from exc
    seen_ids: set[str] = set()
    outputs = []
    for mapping in mappings:
        if "=" not in mapping:
            raise ValueError("--page 格式应为 源页面标题=载具代码。")
        source_title, code = (part.strip() for part in mapping.split("=", 1))
        if not source_title or not re.fullmatch(r"[a-z0-9_-]{1,96}", code):
            raise ValueError("源页面标题或载具代码无效：" + mapping)
        if code in seen_ids:
            raise ValueError("同一载具在单次迁移中只能出现一次：" + code)
        seen_ids.add(code)
        if source_title not in pages:
            raise ValueError("导出 XML 中没有源页面：" + source_title)
        model, source_text, source_timestamp = pages[source_title]
        if model != "wikitext":
            raise ValueError("源页面不是 wikitext 内容模型：" + source_title)
        basic_target, player_target = target_titles(namespace, code)
        existing = [title for title in (basic_target, player_target) if title.casefold() in export_titles]
        if existing:
            raise ValueError("任一目标子页已存在；拒绝重新迁移或覆盖整个载具的拆分：" + "、".join(existing))
        basic_content, player_content, missing = sections_to_migrate(source_text, player_sections | basic_sections)
        if missing and not allow_missing:
            raise ValueError("源页面缺少配置要求迁移的章节；为避免静默丢失内容已停止：" +
                             source_title + "（缺少：" + "、".join(missing) + "）。"
                             "如已人工确认缺失章节不存在，可显式传入 --allow-missing。")
        source_sha256 = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        source_headings = heading_titles(source_text)
        for target, content, sections in (
            (basic_target, basic_content, sorted(basic_sections & set(source_headings))),
            (player_target, player_content,
             [title for title in source_headings if title in player_sections]),
        ):
            if len(content.encode("utf-8")) > MAX_CONTENT_BYTES:
                raise ValueError("迁移子页超过 256 KiB 限制：" + target)
            outputs.append({"title": target, "model": "wikitext", "content": content,
                            "source_title": source_title, "migrated_sections": sections,
                            "missing_sections": missing,
                            "source_timestamp": source_timestamp,
                            "source_sha256": source_sha256,
                            "owner": "manual_after_import"})
    manifest_path = out.with_suffix(".manifest.json")
    if out.exists() or manifest_path.exists():
        raise FileExistsError("迁移包或清单已存在，为避免重复导入而拒绝覆盖：" + str(out))
    out.parent.mkdir(parents=True, exist_ok=True)
    root = ET.Element("{" + XML_NS + "}mediawiki", {"version": "0.11"})
    site = ET.SubElement(root, "{" + XML_NS + "}siteinfo")
    for key, value in [("sitename", "WTJ one-time vehicle content migration"),
                       ("dbname", "warthunder"),
                       ("base", "https://wiki.biligame.com/warthunder/"),
                       ("generator", "WTJ one-time migration; do not re-import"),
                       ("case", "first-letter")]:
        ET.SubElement(site, "{" + XML_NS + "}" + key).text = value
    spaces = ET.SubElement(site, "{" + XML_NS + "}namespaces")
    for number, name in [(0, ""), (6, "文件"), (10, "模板"), (828, "模块")]:
        ET.SubElement(spaces, "{" + XML_NS + "}namespace", {"key": str(number), "case": "first-letter"}).text = name
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for item in outputs:
        page = ET.SubElement(root, "{" + XML_NS + "}page")
        ET.SubElement(page, "{" + XML_NS + "}title").text = item["title"]
        ET.SubElement(page, "{" + XML_NS + "}ns").text = "0"
        revision = ET.SubElement(page, "{" + XML_NS + "}revision")
        ET.SubElement(revision, "{" + XML_NS + "}timestamp").text = stamp
        ET.SubElement(revision, "{" + XML_NS + "}model").text = "wikitext"
        ET.SubElement(revision, "{" + XML_NS + "}format").text = "text/x-wiki"
        ET.SubElement(revision, "{" + XML_NS + "}text", {
            "bytes": str(len(item["content"].encode("utf-8"))),
            "{" + "http://www.w3.org/XML/1998/namespace" + "}space": "preserve",
        }).text = item["content"]
    ET.ElementTree(root).write(out, encoding="utf-8", xml_declaration=True)
    report = {
        "kind": "one_time_vehicle_content_migration",
        "repeat_import": False,
        "live_wiki_written": False,
        "split_pages": {"basic_info": BASIC_INFO_PAGE, "player_content": PLAYER_CONTENT_PAGE},
        "basic_info_sections": sorted(basic_sections),
        "player_sections": sorted(player_sections),
        "allow_missing_sections": allow_missing,
        "live_target_absence_verified_by_generator": False,
        "import_precondition": "导入前必须再次在目标 Wiki 确认两个子页（basic-info 与 player-content）都不存在；离线导出不构成在线不存在证明。任一目标已存在时必须整体放弃，不要只导出一页。导入后此包不得重放。",
        "input_xml": str(export_xml),
        "output_xml": str(out),
        "pages": outputs,
        "sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
        "instruction": "离线导出不证明目标子页面在线不存在。请在导入前再次在线核对，并只导入一次；以后所有常规构建均排除这些标题。",
    }
    manifest_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def heading_titles(wikitext: str) -> list[str]:
    """Titles of real (comment/code-safe) headings, in source order."""
    return [title for _, _, title in heading_matches(wikitext)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-xml", required=True, type=Path, help="现有 BWiki 页面 Special:Export XML")
    parser.add_argument("--page", action="append", default=[], help="源标题=游戏载具代码；可重复指定")
    parser.add_argument("--out", type=Path, default=WIKI / "vehicle-content-migration-once.xml")
    parser.add_argument("--allow-missing", action="store_true",
                        help="人工确认缺失章节确实不存在后，允许输出不完整的迁移包")
    parser.add_argument("--acknowledge-live-target-check", action="store_true",
                        help="确认已阅读导入前须在线核对两个目标子页都不存在的前置条件；工具不会执行在线查询")
    args = parser.parse_args()
    try:
        report = build_migration(args.export_xml.resolve(), args.page, args.out.resolve(),
                                 allow_missing=args.allow_missing,
                                 acknowledge_live_target_check=args.acknowledge_live_target_check)
    except (ValueError, FileExistsError, ET.ParseError) as exc:
        parser.error(str(exc))
    from testing_cleanup import write_cleanup
    write_cleanup(args.out.resolve().parent / 'Cleanup', [p['title'] for p in report['pages']],
                  active_contents=[p['content'] for p in report['pages']])
    print(json.dumps({"output_xml": report["output_xml"], "pages": [p["title"] for p in report["pages"]],
                      "migrated_sections": {p["title"]: p["migrated_sections"] for p in report["pages"]},
                      "repeat_import": False, "live_wiki_written": False}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
