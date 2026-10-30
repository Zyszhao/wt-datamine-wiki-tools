"""Regression checks for the destructive boundary of one-time article migration.

The one-time migration used to write a single /user-content subpage. It now splits the
source article into two independently edited subpages: /basic-info (description only,
without its level-2 heading) and /player-content (everything else hand-written).
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vehicle_content_migration import (  # noqa: E402
    XML_NS, WIKI, build_migration, heading_titles, read_export, sections_to_migrate,
)

CONFIG = json.loads((WIKI.parent / "config/vehicle-content-migration.json").read_text(encoding="utf-8"))
BASIC_SECTIONS = set(CONFIG["basic_info_sections"])
PLAYER_SECTIONS = set(CONFIG["player_sections"])
SECTIONS = BASIC_SECTIONS | PLAYER_SECTIONS
CODE = "test_vehicle"
BASIC_TARGET = f"{CODE}/basic-info"
PLAYER_TARGET = f"{CODE}/player-content"


def export_xml(path: Path, pages: list[tuple[str, str]]) -> None:
    root = ET.Element("{" + XML_NS + "}mediawiki", {"version": "0.11"})
    for title, content in pages:
        page = ET.SubElement(root, "{" + XML_NS + "}page")
        ET.SubElement(page, "{" + XML_NS + "}title").text = title
        revision = ET.SubElement(page, "{" + XML_NS + "}revision")
        ET.SubElement(revision, "{" + XML_NS + "}timestamp").text = "2026-10-27T00:00:00Z"
        ET.SubElement(revision, "{" + XML_NS + "}model").text = "wikitext"
        ET.SubElement(revision, "{" + XML_NS + "}text").text = content
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def full_source(omit: str | None = None) -> str:
    body = [f"== {title} ==\n{title}正文" for title in
            ["基本信息", "描述", "载具点评", "历史", "另见", "媒体", "参考", "程序区"]]
    return "\n".join(line for line in body if omit is None or not line.startswith(f"== {omit} =="))


class VehicleContentMigrationTests(unittest.TestCase):
    def test_config_splits_sections_without_overlap(self):
        self.assertEqual(BASIC_SECTIONS, {"描述"})
        self.assertEqual(PLAYER_SECTIONS, {"载具点评", "历史", "另见", "媒体", "参考"})
        self.assertFalse(BASIC_SECTIONS & PLAYER_SECTIONS)
        self.assertEqual(CONFIG["namespace"], "WTJ")

    def test_split_pages_and_description_heading_removed(self):
        source = (
            "{{载具图鉴|载具ID =test_vehicle}}\n\n"
            "== 描述 ==\n描述正文第一段。\n\n描述正文第二段。\n"
            "== 载具点评 ==\n=== 优缺点 ===\n优点正文\n"
            "== 历史 ==\n历史正文\n== 另见 ==\n相关条目\n"
            "== 媒体 ==\n媒体正文\n== 参考 ==\n参考正文\n"
            "== 基本信息 ==\n程序区正文\n"
        )
        basic, player, missing = sections_to_migrate(source, SECTIONS)
        self.assertEqual(missing, [])
        # basic-info keeps only the description body, without its own level-2 heading.
        self.assertNotIn("== 描述 ==", basic)
        self.assertEqual(basic, "描述正文第一段。\n\n描述正文第二段。")
        # player-content keeps every other hand-written section with its heading.
        for title in sorted(PLAYER_SECTIONS):
            self.assertIn(f"== {title} ==", player)
        self.assertIn("=== 优缺点 ===\n优点正文", player)
        self.assertIn("相关条目", player)
        self.assertNotIn("描述正文", player)
        self.assertNotIn("== 基本信息 ==", player)
        self.assertNotIn("程序区正文", player)
        self.assertTrue(player.endswith("\n"))

    def test_nested_sections_are_preserved_and_fake_headings_ignored(self):
        source = (
            "== 描述 ==\n描述正文\n<!--\n== 历史 ==\n-->\n"
            "<nowiki>\n== 参考 ==\n</nowiki>\n"
            "== 载具点评 ==\n=== 优点 ===\n优点正文\n"
            "== 历史 ==\n历史正文\n== 另见 ==\n相关条目\n"
            "== 媒体 ==\n媒体正文\n== 参考 ==\n参考正文\n"
            "== 基本信息 ==\n程序区正文\n"
        )
        basic, player, missing = sections_to_migrate(source, SECTIONS)
        self.assertEqual(missing, [])
        self.assertTrue(basic.startswith("描述正文\n"))
        self.assertIn("=== 优点 ===\n优点正文", player)
        self.assertIn("<!--\n== 历史 ==\n-->", basic)
        self.assertIn("<nowiki>\n== 参考 ==\n</nowiki>", basic)
        self.assertNotIn("== 基本信息 ==", player)
        # Fake headings inside comments/nowiki are not counted as real sections.
        self.assertNotIn("程序区", heading_titles(source))

    def test_missing_required_section_is_reported(self):
        source = "\n".join(f"== {title} ==\n正文" for title in sorted(SECTIONS - {"历史"}))
        _, _, missing = sections_to_migrate(source, SECTIONS)
        self.assertEqual(missing, ["历史"])

    def test_export_package_contains_both_split_pages(self):
        source = full_source()
        with tempfile.TemporaryDirectory(dir=WIKI) as temp_dir:
            folder = Path(temp_dir)
            input_xml, output_xml = folder / "source.xml", folder / "migration.xml"
            export_xml(input_xml, [("Frozen vehicle", source)])
            report = build_migration(
                input_xml, [f"Frozen vehicle={CODE}"], output_xml,
                acknowledge_live_target_check=True,
            )
            self.assertFalse(report["live_wiki_written"])
            self.assertFalse(report["live_target_absence_verified_by_generator"])
            self.assertFalse(report["repeat_import"])
            self.assertEqual([page["title"] for page in report["pages"]], [BASIC_TARGET, PLAYER_TARGET])
            self.assertEqual(report["split_pages"], {"basic_info": "basic-info", "player_content": "player-content"})
            source_sha = hashlib.sha256(source.encode()).hexdigest()
            for page in report["pages"]:
                self.assertEqual(page["source_sha256"], source_sha)
                self.assertEqual(page["source_timestamp"], "2026-10-27T00:00:00Z")
                self.assertEqual(page["owner"], "manual_after_import")
            basic_page, player_page = report["pages"]
            self.assertEqual(set(basic_page["migrated_sections"]), BASIC_SECTIONS)
            self.assertEqual(set(player_page["migrated_sections"]), PLAYER_SECTIONS)
            self.assertNotIn("== 描述 ==", basic_page["content"])
            self.assertIn("描述正文", basic_page["content"])
            self.assertNotIn("历史正文", basic_page["content"])
            for title in sorted(PLAYER_SECTIONS):
                self.assertIn(f"== {title} ==", player_page["content"])
            self.assertNotIn("描述正文", player_page["content"])
            # Roundtrip: the package really holds two pages with correct content.
            parsed, _ = read_export(output_xml)
            self.assertEqual(set(parsed), {BASIC_TARGET, PLAYER_TARGET})
            self.assertEqual(parsed[BASIC_TARGET][0], "wikitext")
            self.assertEqual(parsed[BASIC_TARGET][1], basic_page["content"])
            self.assertEqual(parsed[PLAYER_TARGET][1], player_page["content"])
            self.assertEqual(report["sha256"], hashlib.sha256(output_xml.read_bytes()).hexdigest())
            manifest = output_xml.with_suffix(".manifest.json")
            self.assertTrue(manifest.exists())
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["pages"], report["pages"])
            # No legacy single page is emitted any more.
            self.assertFalse(any(page["title"].endswith("/user-content") for page in report["pages"]))
            # One-time only: rerunning the same output is refused.
            with self.assertRaises(FileExistsError):
                build_migration(input_xml, [f"Frozen vehicle={CODE}"], output_xml,
                                acknowledge_live_target_check=True)

    def test_missing_sections_stop_before_package_creation(self):
        source = full_source(omit="历史")
        with tempfile.TemporaryDirectory(dir=WIKI) as temp_dir:
            folder = Path(temp_dir)
            input_xml, output_xml = folder / "source.xml", folder / "migration.xml"
            export_xml(input_xml, [("Frozen vehicle", source)])
            with self.assertRaisesRegex(ValueError, "缺少：历史"):
                build_migration(input_xml, [f"Frozen vehicle={CODE}"], output_xml,
                                acknowledge_live_target_check=True)
            self.assertFalse(output_xml.exists())
            self.assertFalse(output_xml.with_suffix(".manifest.json").exists())

    def test_missing_description_stops_before_package_creation(self):
        source = full_source(omit="描述")
        with tempfile.TemporaryDirectory(dir=WIKI) as temp_dir:
            folder = Path(temp_dir)
            input_xml, output_xml = folder / "source.xml", folder / "migration.xml"
            export_xml(input_xml, [("Frozen vehicle", source)])
            with self.assertRaisesRegex(ValueError, "缺少：描述"):
                build_migration(input_xml, [f"Frozen vehicle={CODE}"], output_xml,
                                acknowledge_live_target_check=True)
            self.assertFalse(output_xml.exists())

    def test_second_page_in_export_rejects_whole_task(self):
        # The player-content page already exists, so even a fresh basic-info page must not be written.
        source = full_source()
        with tempfile.TemporaryDirectory(dir=WIKI) as temp_dir:
            folder = Path(temp_dir)
            input_xml, output_xml = folder / "source.xml", folder / "migration.xml"
            export_xml(input_xml, [("Frozen vehicle", source), (PLAYER_TARGET, "已有玩家内容")])
            with self.assertRaisesRegex(ValueError, "任一目标子页已存在"):
                build_migration(input_xml, [f"Frozen vehicle={CODE}"], output_xml,
                                acknowledge_live_target_check=True)
            self.assertFalse(output_xml.exists())
            self.assertFalse(output_xml.with_suffix(".manifest.json").exists())

    def test_basic_info_page_in_export_rejects_whole_task(self):
        source = full_source()
        with tempfile.TemporaryDirectory(dir=WIKI) as temp_dir:
            folder = Path(temp_dir)
            input_xml, output_xml = folder / "source.xml", folder / "migration.xml"
            export_xml(input_xml, [("Frozen vehicle", source), (BASIC_TARGET, "已有描述内容")])
            with self.assertRaisesRegex(ValueError, "任一目标子页已存在"):
                build_migration(input_xml, [f"Frozen vehicle={CODE}"], output_xml,
                                acknowledge_live_target_check=True)
            self.assertFalse(output_xml.exists())

    def test_conflicting_pages_are_reported_both(self):
        source = full_source()
        with tempfile.TemporaryDirectory(dir=WIKI) as temp_dir:
            folder = Path(temp_dir)
            input_xml, output_xml = folder / "source.xml", folder / "migration.xml"
            export_xml(input_xml, [("Frozen vehicle", source), (BASIC_TARGET, "a"), (PLAYER_TARGET, "b")])
            with self.assertRaises(ValueError) as caught:
                build_migration(input_xml, [f"Frozen vehicle={CODE}"], output_xml,
                                acknowledge_live_target_check=True)
            message = str(caught.exception)
            self.assertIn(BASIC_TARGET, message)
            self.assertIn(PLAYER_TARGET, message)

    def test_live_target_check_acknowledgement_is_required(self):
        source = full_source()
        with tempfile.TemporaryDirectory(dir=WIKI) as temp_dir:
            folder = Path(temp_dir)
            input_xml, output_xml = folder / "source.xml", folder / "migration.xml"
            export_xml(input_xml, [("Frozen vehicle", source)])
            with self.assertRaisesRegex(ValueError, "acknowledge-live-target-check"):
                build_migration(input_xml, [f"Frozen vehicle={CODE}"], output_xml)
            self.assertFalse(output_xml.exists())

    def test_output_outside_wiki_is_rejected(self):
        source = full_source()
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            input_xml = folder / "source.xml"
            export_xml(input_xml, [("Frozen vehicle", source)])
            with self.assertRaisesRegex(ValueError, "wiki/"):
                build_migration(input_xml, [f"Frozen vehicle={CODE}"], folder / "migration.xml",
                                acknowledge_live_target_check=True)
            self.assertFalse((folder / "migration.xml").exists())


if __name__ == "__main__":
    unittest.main()
