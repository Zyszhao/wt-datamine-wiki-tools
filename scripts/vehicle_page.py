"""Build one code-keyed vehicle article prototype as JSON + Lua + scoped assets.

The command reads the datamine without changing it and writes local candidates.
Articles use vehicle codes, shared resources use WTJ, and large card images use
the site-wide _资料卡 suffix. Wiki deployment remains manual.
"""
from __future__ import annotations

import argparse
import binascii
import csv
import email
import html
import hashlib
import json
import math
import re
import shutil
import sys
import struct
import zlib
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from xml.etree import ElementTree as ET

from paths import ROOT, REPO, WIKI, WORK
from asset_naming import vehicle_image_name, bind_namespace

ID_RE = re.compile(r"^[a-z0-9_-]{1,96}$")
PREFIX_RE = re.compile(r"^WTJ$")
XML_NS = "http://www.mediawiki.org/xml/export-0.11/"
ET.register_namespace("", XML_NS)
MAX_PAGE_BYTES = 2 * 1024 * 1024
COUNTRIES = {
    "country_usa": "美国", "country_germany": "德国", "country_ussr": "苏联",
    "country_britain": "英国", "country_japan": "日本", "country_china": "中国",
    "country_italy": "意大利", "country_france": "法国", "country_sweden": "瑞典",
    "country_israel": "以色列", "country_greece": "希腊",
    "country_greece_modern": "希腊",
}
BRANCHES = {"army": "陆军", "aviation": "空军", "helicopters": "直升机",
            "boats": "近岸海军", "ships": "远洋海军"}
GROUND_TYPES = {
    "type_light_tank": "轻型坦克", "type_medium_tank": "中型坦克",
    "type_heavy_tank": "重型坦克", "type_tank_destroyer": "坦克歼击车",
    "type_spaa": "自行防空炮",
}


def dumps(value: object, pretty: bool = False) -> str:
    return json.dumps(value, ensure_ascii=False,
                      indent=2 if pretty else None,
                      separators=None if pretty else (",", ":"),
                      allow_nan=False) + "\n"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (struct.pack(">I", len(payload)) + kind + payload +
            struct.pack(">I", binascii.crc32(kind + payload) & 0xffffffff))


def transparent_vehicle_png(source: Path, target: Path) -> None:
    """Remove the pure white matte from the datamine RGBA preview image.

    The source export is a 8-bit RGBA PNG with a white studio background. A
    small local decoder keeps the datamine untouched and makes the same asset
    render correctly on the official dark-blue hero background.
    """
    raw = source.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        shutil.copyfile(source, target)
        return
    pos = 8
    ihdr = None
    idat = bytearray()
    chunks: list[tuple[bytes, bytes]] = []
    while pos < len(raw):
        length = struct.unpack(">I", raw[pos:pos + 4])[0]
        kind = raw[pos + 4:pos + 8]
        payload = raw[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            ihdr = payload
        elif kind == b"IDAT":
            idat.extend(payload)
        elif kind in (b"PLTE", b"tRNS"):
            chunks.append((kind, payload))
        elif kind == b"IEND":
            break
    if not ihdr:
        shutil.copyfile(source, target)
        return
    width, height, depth, color_type, compression, filtering, interlace = struct.unpack(">IIBBBBB", ihdr)
    if (depth, color_type, compression, filtering, interlace) != (8, 6, 0, 0, 0):
        shutil.copyfile(source, target)
        return
    decoded = zlib.decompress(bytes(idat))
    stride = width * 4
    rows: list[bytearray] = []
    cursor = 0
    previous = bytearray(stride)
    for _ in range(height):
        filter_type = decoded[cursor]
        cursor += 1
        current = bytearray(decoded[cursor:cursor + stride])
        cursor += stride
        for i in range(stride):
            left = current[i - 4] if i >= 4 else 0
            up = previous[i]
            up_left = previous[i - 4] if i >= 4 else 0
            if filter_type == 1:
                current[i] = (current[i] + left) & 255
            elif filter_type == 2:
                current[i] = (current[i] + up) & 255
            elif filter_type == 3:
                current[i] = (current[i] + ((left + up) // 2)) & 255
            elif filter_type == 4:
                estimate = left + up - up_left
                pa, pb, pc = abs(estimate - left), abs(estimate - up), abs(estimate - up_left)
                predictor = left if pa <= pb and pa <= pc else up if pb <= pc else up_left
                current[i] = (current[i] + predictor) & 255
            elif filter_type != 0:
                raise ValueError(f"unsupported PNG filter: {filter_type}")
        rows.append(current)
        previous = current
    output = bytearray()
    for row in rows:
        output.append(0)
        for i in range(0, stride, 4):
            r, g, b, a = row[i:i + 4]
            whiteness = min(r, g, b)
            if whiteness >= 248:
                a = 0
            elif whiteness > 220:
                a = min(a, max(0, (248 - whiteness) * 9))
            row[i + 3] = a
        output.extend(row)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", ihdr) +
                       b"".join(_png_chunk(k, v) for k, v in chunks) +
                       _png_chunk(b"IDAT", zlib.compress(bytes(output), 9)) + _png_chunk(b"IEND", b""))


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_language(root: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    for name in ("units.csv", "units_modifications.csv", "units_weaponry.csv", "menu.csv"):
        path = root / "lang.vromfs.bin_u" / "lang" / name
        if not path.is_file():
            continue
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream, delimiter=";"):
                key = row.get("<ID|readonly|noverify>")
                if key:
                    rows[key.casefold()] = row
    return rows


def localized(rows: dict, key: str) -> tuple[str | None, str | None]:
    row = rows.get(key.casefold(), {})
    zh = (row.get("<Chinese>") or "").replace("\u200b", "").replace("\ufeff", "").strip()
    en = (row.get("<English>") or "").replace("\u200b", "").replace("\ufeff", "").strip()
    return zh or None, en or None


def as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def source_name(path: Path | None, suffix: str = "", base: Path | None = None) -> str:
    if not path:
        return "模型数据缺失" + suffix
    try:
        value = path.relative_to(base) if base else path.name
    except ValueError:
        value = path.name
    return str(value).replace("\\", "/") + suffix


def localized_or_code(lang: dict, candidates: list[str], fallback: str) -> str:
    for key in candidates:
        zh, en = localized(lang, key)
        if zh or en:
            return clean_vehicle_name(zh or en or fallback, fallback)
    return fallback


def clean_vehicle_name(value: str, fallback: str) -> str:
    # Leading shop/status glyphs are game UI metadata, not part of the article name.
    value = value.replace("\u200b", "").replace("\ufeff", "").strip()
    value = re.sub(r"^[◐◑◓◒▂▃▅▆▇▀▄◢◣◤◥]+\s*", "", value)
    return value or fallback


def locate_vehicle(shop: dict, code: str) -> tuple[str, str] | None:
    """Return the actual country/branch placement, including nested folder entries."""
    for country, branches in shop.items():
        if not isinstance(branches, dict):
            continue
        for branch, config in branches.items():
            if not isinstance(config, dict):
                continue
            for column in config.get("range", []):
                if not isinstance(column, dict):
                    continue
                for key, value in column.items():
                    if key == code:
                        return country, branch
                    if isinstance(value, dict) and code in value:
                        return country, branch
    return None


def official_reference(code: str) -> dict:
    """Read saved official HTML only; derived game results are not inferred from BLK."""
    reference = ROOT.parent / "Reference"
    for path in sorted(reference.glob("*.mhtml")):
        message = email.message_from_bytes(path.read_bytes())
        for part in message.walk():
            if part.get_content_type() != "text/html":
                continue
            location = part.get("Content-Location", "")
            if location.rstrip("/") != "https://wiki.warthunder.com/unit/" + code:
                continue
            raw = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")
            source = "Reference/" + path.name + "; " + location
            result = {"source": source, "sha256": sha256(path.read_bytes()), "snapshot": True}
            for label, key in [("Engine power", "engine_power_hp"), ("Forward", "forward_km_h"), ("Backward", "reverse_km_h")]:
                match = re.search(r"<span>" + label + r"</span>(.*?)</div>", raw, re.S)
                if not match:
                    continue
                values = {}
                for classes, number in re.findall(r'<span class="([^"]+)">([0-9,.]+)</span>', match[1]):
                    value = float(number.replace(",", ""))
                    for mode in ("rb", "ab"):
                        if "show-char-" + mode in classes:
                            state = "stock" if "mod-basic" in classes else "upgraded"
                            values.setdefault(mode, {})[state] = value
                if values:
                    result[key] = values
            match = re.search(r'Talisman cost</span>\s*<span[^>]*>\s*([0-9,]+)', raw)
            if match:
                result["talisman_ge"] = int(match[1].replace(",", ""))
            icons = {}
            for block in re.findall(r'<div class="game-unit_b-icon">(.*?)</button>', raw, re.S):
                name = html.unescape(re.sub(r'<[^>]+>', '', block)).strip()
                layers = re.findall(r'<img src="https://static\.encyclopedia\.warthunder\.com/gui_skin/([a-z0-9_]+\.png)"', block)
                if name and layers:
                    icons[name] = layers
            result["ammunition_icon_layers"] = icons
            return result
    return {}


def one_vehicle(code: str, root: Path, *, include_files: bool = True) -> tuple[dict, dict[str, Path]]:
    if not ID_RE.fullmatch(code):
        raise ValueError("载具代码只允许小写字母、数字、下划线和连字符。")
    def source_name(path: Path | None, suffix: str = "") -> str:
        if not path:
            return "模型数据缺失" + suffix
        try:
            value = path.relative_to(root)
        except ValueError:
            value = path.name
        return value.as_posix() + suffix

    economy_all = load_json(root / "char.vromfs.bin_u/config/wpcost.blkx")
    tags_all = load_json(root / "char.vromfs.bin_u/config/unittags.blkx")
    shop = load_json(root / "char.vromfs.bin_u/config/shop.blkx")
    entry = economy_all.get(code)
    if not isinstance(entry, dict):
        raise KeyError(f"wpcost.blkx 中找不到载具：{code}")
    placement = locate_vehicle(shop, code)
    if not placement:
        raise ValueError(f"shop.blkx 中找不到载具的商店分支：{code}")
    country_id, branch_id = placement
    branch = BRANCHES.get(branch_id)
    country = COUNTRIES.get(country_id)
    if not branch or not country:
        raise ValueError(f"当前站点配置不认识国家/分支：{country_id}/{branch_id}")

    lang = read_language(root)
    raw_name = localized(lang, code + "_shop")[0] or localized(lang, code + "_shop")[1] or code
    name = clean_vehicle_name(raw_name, code)
    tag = tags_all.get(code, {}).get("tags", {})
    category = next((label for key, label in GROUND_TYPES.items() if tag.get(key)), None)
    if not category:
        category = entry.get("unitClass", "未知类别").replace("exp_", "")

    def br(key: str):
        value = entry.get("economicRank" + key)
        if value is None:
            return None
        return float((Decimal(str(value)) / 3 + 1).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))

    version_path = root / "version"
    version = version_path.read_text(encoding="utf-8-sig").strip()
    source_map = {
        "name": "lang.vromfs.bin_u/lang/units.csv:" + code + "_shop/<Chinese>",
        "placement": "char.vromfs.bin_u/config/shop.blkx",
        "classification": "char.vromfs.bin_u/config/unittags.blkx + wpcost.blkx",
        "economy": "char.vromfs.bin_u/config/wpcost.blkx:" + code,
        "br": "wpcost.blkx economicRank*; BR = round_half_up(rank/3+1, 0.1)",
    }

    model_path = None
    model_dirs = {
        "army": ("aces.vromfs.bin_u/gamedata/units/tankmodels",),
        "boats": ("aces.vromfs.bin_u/gamedata/units/boats", "aces.vromfs.bin_u/gamedata/units/ships"),
        "ships": ("aces.vromfs.bin_u/gamedata/units/ships",),
        "aviation": ("aces.vromfs.bin_u/gamedata/flightmodels",),
        "helicopters": ("aces.vromfs.bin_u/gamedata/flightmodels",),
    }
    for directory in model_dirs.get(branch_id, ()):
        candidate = root / directory / (code + ".blkx")
        if candidate.is_file():
            model_path = candidate
            break
    model = load_json(model_path) if model_path else {}
    model_source = str(model_path.relative_to(root)).replace("\\", "/") if model_path else None
    if model_source:
        source_map["model"] = model_source

    def row(label, value, source, unit=None, status=None):
        obj = {"label": label, "value": value, "source": source}
        if unit:
            obj["unit"] = unit
        if status:
            obj["status"] = status
        elif value is None:
            obj["status"] = "uncomputed"
        return obj

    operator = COUNTRIES.get(tags_all.get(code, {}).get("operatorCountry"))
    sections = [
        {"id": "general", "title": "基本信息", "rows": [
            row("载具等级", entry.get("rank"), source_map["economy"] + ".rank"),
            row("乘员", entry.get("crewTotalCount"), source_map["economy"] + ".crewTotalCount", "人"),
            row("物理配置战斗重量", model.get('VehiclePhys', {}).get('Mass', {}).get('TakeOff'), (model_source + '.VehiclePhys.Mass.TakeOff') if model_source else '模型数据缺失', 'kg'),
        ]},
        {"id": "survivability", "title": "生存能力与防护", "rows": [
            row("装甲厚度与分区", None, "当前转换器尚未解析装甲防护区域。", status="uncomputed"),
            row("载具特性", None, "当前转换器尚未归一化此载具的特性标签。", status="uncomputed"),
        ]},
        {"id": "mobility", "title": "机动性", "rows": [
            row("模型前进极速", model.get("maxFwdSpeed"), (model_source + ".maxFwdSpeed") if model_source else "模型数据缺失", "km/h"),
            row("模型倒车极速", model.get("maxRevSpeed"), (model_source + ".maxRevSpeed") if model_source else "模型数据缺失", "km/h"),
            row("模型加速度参数", model.get("maxAccel"), (model_source + ".maxAccel") if model_source else "模型数据缺失", "m/s²"),
        ]},
        {"id": "optics", "title": "观瞄", "rows": [
            row("光学设备", None, "当前转换器尚未解析观瞄设备。", status="uncomputed"),
            row("夜视/热成像", None, "当前转换器尚未解析夜视与热成像设备。", status="uncomputed"),
        ]},
        {"id": "armaments", "title": "武器装备", "rows": [
            row("主武器与弹药", None, "当前原型没有计算武器弹药与弹道数据。", status="uncomputed"),
        ]},
    ]

    def fmt(value):
        return "待计算" if value is None else f"{value:,}"

    sections.append({
        "id": "economy", "title": "经济", "rows": [
            *[row(label + "维修费用（基础 → 完全体）",
                  f"{fmt(entry.get('repairCost' + suffix))} → {fmt(entry.get('repairCostFullUpgraded' + suffix))}",
                  "wpcost.blkx repairCost* / repairCostFullUpgraded*", "银狮")
              for label, suffix in [("街机", "Arcade"), ("历史", "Historical")]],
            row("乘员组培训", entry.get("trainCost"), "wpcost.blkx.trainCost", "银狮"),
            row("专家", entry.get("train2Cost"), "wpcost.blkx.train2Cost", "银狮"),
            row("王牌", entry.get("train3Cost_gold"), "wpcost.blkx.train3Cost_gold", "金鹰"),
            row("王牌研发", entry.get("train3Cost_exp"), "wpcost.blkx.train3Cost_exp", "研发点"),
            row("收益系数", {
                "ab": entry.get("rewardMulArcade"),
                "rb": entry.get("rewardMulHistorical"),
            }, "wpcost.blkx rewardMulArcade / rewardMulHistorical"),
            row("研发费用", entry.get("reqExp"), "wpcost.blkx.reqExp", "研发点"),
            row("购买费用", entry.get('value'), 'wpcost.blkx.value', '银狮'),
        ],
    })

    # Match the official grouping: crew belongs to survivability, mass to mobility.
    general_rows = sections[0]["rows"]
    next(s for s in sections if s["id"] == "survivability")["rows"].append(general_rows[1])
    next(s for s in sections if s["id"] == "mobility")["rows"].append(general_rows[2])
    armour_card = {}
    shop_tags = tags_all.get(code, {}).get("Shop", {})
    protection = next(s for s in sections if s["id"] == "survivability")
    for key, label in [("armorThicknessHull", "车体装甲（前 / 侧 / 后）"), ("armorThicknessTurret", "炮塔装甲（前 / 侧 / 后）")]:
        values = shop_tags.get(key)
        if isinstance(values, list) and len(values) == 3:
            source = source_map["classification"] + ".Shop." + key
            display_values = [values[0], values[2], values[1]]
            armour_card[key] = {"values_mm": display_values, "order": ["front", "side", "rear"],
                                "raw_values_mm": values, "source": source, "kind": "stat_card_nominal_not_equivalent"}
            protection["rows"].append(row(label, " / ".join(f"{v:g}" for v in display_values), source, "mm"))
    if armour_card:
        protection["rows"] = [r for r in protection["rows"] if r["label"] != "装甲厚度与分区"]
    reference_data = official_reference(code)

    definitions = load_json(root / "char.vromfs.bin_u/config/modifications.blkx").get("modifications", {})
    mod_images: dict[str, Path] = {}
    gui_config = load_json(root / "aces.vromfs.bin_u/config/gui.blkx")
    ammo_names: dict[str, set[str]] = {}
    weapons: list[dict] = []
    ammunition: list[dict] = []
    sensors: list[dict] = []
    weapon_index: dict[tuple[str, str, str], str] = {}
    ammunition_index: dict[tuple[str, str], str] = {}
    explosive_types = load_json(root / "aces.vromfs.bin_u/gamedata/damage_model/explosive.blkx").get("explosiveTypes", {})
    ammunition_types: dict[str, dict] = {}
    ammo_stowages = []
    for storage_id, storage in model.get("ammoStowages", {}).items():
        if not isinstance(storage, dict):
            continue
        groups = []
        for group in as_list(storage.get("shells")):
            if isinstance(group, dict):
                groups.append({"first_stage": bool(group.get("firstStage")),
                               "count": sum(part.get("count", 0) for part in group.values() if isinstance(part, dict)),
                               "reload_time_multiplier": group.get("reloadTimeMult")})
        ammo_stowages.append({"id": storage_id, "trigger": storage.get("weaponTrigger"),
                              "groups": groups, "ready_count": sum(g["count"] for g in groups if g["first_stage"]),
                              "total_count": sum(g["count"] for g in groups),
                              "source": source_name(model_path, ".ammoStowages." + storage_id)})

    def referenced_blk(ref):
        if not isinstance(ref, str) or not ref:
            return None
        candidate = root / "aces.vromfs.bin_u" / ref.lower().replace(".blk", ".blkx")
        return candidate if candidate.is_file() else None

    def role_for(trigger, group=None):
        if branch_id == 'aviation' and str(trigger).startswith('gunner'):
            return '防御炮塔'
        if group == "coaxial":
            return "并列机枪"
        return {"gunner0": "主武器", "gunner1": "机枪", "gunner2": "机枪",
                "cannon": "航炮", "aam": "空对空武器", "agm": "空对地武器",
                "bomb": "炸弹", "rocket": "火箭弹", "countermeasures": "反制措施"}.get(trigger, trigger or "武器")

    def add_weapon(mount, context="", slot=None):
        if not isinstance(mount, dict):
            return None
        ref = mount.get("blk")
        if not isinstance(ref, str) or "dummy_weapon" in ref:
            return None
        weapon_file = referenced_blk(ref)
        weapon_def = load_json(weapon_file) if weapon_file else {}
        weapon_code = Path(ref).stem
        trigger = str(mount.get("trigger") or "")
        trigger_group = str(mount.get("triggerGroup") or "")
        weapon_key = (ref.casefold(), trigger, str(slot if slot is not None else context))
        weapon_id = weapon_index.get(weapon_key)
        if weapon_id is None:
            weapon_id = f"{weapon_code}:{trigger or 'weapon'}:{slot if slot is not None else context or 'fixed'}"
            weapon_index[weapon_key] = weapon_id
            name = localized_or_code(lang, ["weapons/" + weapon_code, weapon_code + "/name", weapon_code], weapon_code)
            bullet_defs = as_list(weapon_def.get("bullet"))
            bullet_variants = {}
            for ammo_variant, variant in weapon_def.items():
                if isinstance(variant, dict):
                    extra_bullets = as_list(variant.get("bullet"))
                    bullet_defs.extend(extra_bullets)
                    for variant_bullet in extra_bullets:
                        bullet_variants[id(variant_bullet)] = ammo_variant
            ammo_ids = []
            enabled_variants = set()
            for mod_id in entry.get("modifications", {}):
                effects = {**definitions.get(mod_id, {}).get("effects", {}), **model.get("modifications", {}).get(mod_id, {}).get("effects", {})}
                enabled_variants.update(v for k, v in effects.items() if k in ("additiveBulletMod", "bulletMod") and isinstance(v, str))
            enabled_names = {b.get("bulletName") for b in bullet_defs if isinstance(b, dict) and bullet_variants.get(id(b)) in enabled_variants}
            bullet_defs = [b for b in bullet_defs if not isinstance(b, dict) or not b.get("bulletName")
                           or b["bulletName"] not in enabled_names or bullet_variants.get(id(b)) in enabled_variants]
            for bullet_index, bullet in enumerate(bullet_defs):
                if not isinstance(bullet, dict):
                    continue
                ammo_code = bullet.get("bulletName") or f"{weapon_code}_round_{bullet_index + 1}"
                ammo_key = (ref.casefold(), str(ammo_code).casefold())
                ammo_id = ammunition_index.get(ammo_key)
                if ammo_id is None:
                    ammo_id = f"{weapon_code}:{ammo_code}"
                    ammunition_index[ammo_key] = ammo_id
                    armor_power = bullet.get("armorpower") or bullet.get("armorPower")
                    projectile_type = bullet.get("bulletType")
                    if projectile_type and projectile_type not in ammunition_types:
                        key = projectile_type + "/name"
                        ammunition_types[projectile_type] = {"name": localized_or_code(lang, [key, projectile_type], projectile_type),
                            "source": "lang.vromfs.bin_u/lang/units_weaponry.csv:" + key}
                    equivalent = explosive_types.get(bullet.get("explosiveType"), {}).get("strengthEquivalent")
                    explosive_mass = bullet.get("explosiveMass")
                    ammo_name = localized_or_code(lang, [ammo_code + "/name/short", ammo_code + "/name", ammo_code], ammo_code)
                    icon_layers = []
                    icon_source = "gui.blkx:bullet_icons / bullets_features_icons; weaponsinfoexporter.nut:makeBulletIconOverlays"
                    variant_name = bullet_variants.get(id(bullet))
                    icon_param = entry.get("bulletsIconParams", {}).get(weapon_code.lower(), 0) if not variant_name else 0
                    for mod_id, local_mod in entry.get("modifications", {}).items():
                        effects = {**definitions.get(mod_id, {}).get("effects", {}), **model.get("modifications", {}).get(mod_id, {}).get("effects", {})}
                        if variant_name and variant_name in (effects.get("additiveBulletMod"), effects.get("bulletMod")):
                            icon_param = local_mod.get("bulletsIconParam", 0)
                    if weapon_def.get("isBulletBelt") is False and projectile_type != "napalm_tank":
                        for feature, index in [("damage", icon_param // 10 - 1), ("armor", icon_param % 10 - 1)]:
                            choices = gui_config.get("bullets_features_icons", {}).get(feature, [])
                            if 0 <= index < len(choices) and choices[index]:
                                icon_layers.append(choices[index].split("#")[-1].replace(".avif", ".png"))
                    icon_id = bullet.get("guiCustomIcon") or projectile_type
                    icon = gui_config.get("bullet_icons", {}).get(icon_id)
                    if isinstance(icon, str):
                        icon_layers.append(icon.split("#")[-1].replace(".avif", "").replace(".png", "") + ".png")
                    icon_files = []
                    for layer in icon_layers:
                        source = root / "atlases.vromfs.bin_u/gameuiskin" / layer
                        if source.is_file():
                            filename = layer
                            mod_images[filename] = source
                            icon_files.append(filename)
                    ammunition.append({
                        "id": ammo_id, "code": ammo_code,
                        "name": ammo_name if bullet.get("bulletName") else ammunition_types.get(projectile_type, {}).get("name", ammo_name),
                        "icon_layers": icon_files, "icon_source": icon_source,
                        "icon_base_aspect_ratio": gui_config.get("bullet_icon_aspect_ratio", {}).get(icon, 1),
                        "weapon_code": weapon_code,
                        "projectile_type": bullet.get("bulletType"),
                        "caliber_mm": float(bullet["caliber"]) * 1000 if isinstance(bullet.get("caliber"), (int, float)) else None,
                        "mass_kg": bullet.get("mass"),
                        "muzzle_velocity_m_s": bullet.get("speed"),
                        "max_distance_m": bullet.get("maxDistance"),
                        "explosive_type": bullet.get("explosiveType"),
                        "explosive_mass_kg": bullet.get("explosiveMass"),
                        "tnt_equivalent_kg": explosive_mass * equivalent if isinstance(explosive_mass, (int, float)) and isinstance(equivalent, (int, float)) else None,
                        "tnt_strength_equivalent": equivalent,
                        "tnt_equivalent_source": "explosive.blkx:explosiveTypes.strengthEquivalent; dmgmodel.nut:explosiveMass * strengthEquivalent",
                        "fuse_delay_m": bullet.get("fuseDelayDist"),
                        "fuse_delay_s": bullet.get("fuseDelay"),
                        "armor_power_source_values": armor_power,
                        "belt_count": bullet.get("bulletCount"),
                        "source": source_name(weapon_file) + ".bullet[" + str(bullet_index + 1) + "]",
                    })
                ammo_ids.append(ammo_id)
            limits = mount.get("limits") if isinstance(mount.get("limits"), dict) else {}
            characteristics = []
            for key, label, unit in (("pitch", "垂直射界", "°"), ("yaw", "水平射界", "°")):
                value = limits.get(key)
                if isinstance(value, list) and len(value) == 2:
                    characteristics.append({"label": label, "value": ' ～ '.join(str(v) for v in value), "unit": unit,
                                            "source": source_name(model_path, ".commonWeapons." + key)})
            for key, label, unit in (("bullets", "备弹量", "发"), ("bulletsCartridge", "弹链容量", "发"),
                                     ("reloadTime", "弹链装填时间", "秒"),
                                     ("speedYaw", "水平转速（原始值）", ""), ("speedPitch", "垂直转速（原始值）", "")):
                if mount.get(key) is not None:
                    characteristics.append({"label": label, "value": mount[key], "unit": unit,
                                            "source": source_name(model_path, ".commonWeapons." + key)})
            stabilizer = mount.get("gunStabilizer") if isinstance(mount.get("gunStabilizer"), dict) else {}
            frequency = mount.get("shotFreq", weapon_def.get("shotFreq"))
            reload_time = entry.get("reloadTime_cannon") if branch_id == "army" and trigger == "gunner0" else None
            reload_source = "wpcost.blkx.reloadTime_cannon" if reload_time is not None else source_name(weapon_file, "; 1 / shotFreq")
            if reload_time is None and isinstance(frequency, (int, float)) and frequency > 0:
                reload_time = 1 / frequency
            if reload_time is not None:
                characteristics.append(row("单发装填时间（基准）" if branch_id == "army" and trigger == "gunner0" else "单发射击间隔", reload_time, reload_source, "秒/发"))
            for storage in ammo_stowages:
                if slot is None and storage["trigger"] == trigger and storage["ready_count"]:
                    characteristics.append(row("待发弹药架", storage["ready_count"], storage["source"], "发"))
            features = []
            if stabilizer.get("hasHorizontal") and stabilizer.get("hasVertical"):
                features.append("双向稳定器")
            weapons.append({
                "id": weapon_id, "code": weapon_code, "name": name,
                "role": role_for(trigger, trigger_group), "trigger": trigger,
                "trigger_group": trigger_group or None, "slot": slot, "turret": mount.get("turret"),
                "external": bool(mount.get("external")), "separate": bool(mount.get("separate")),
                "features": features, "characteristics": characteristics,
                "ammunition_ids": list(dict.fromkeys(ammo_ids)),
                "source": source_name(model_path, "." + (context or "commonWeapons")),
                "weapon_source": source_name(weapon_file),
            })
        return weapon_id

    # Fixed guns and vehicle-mounted weapons.
    mounts = as_list(model.get("commonWeapons", {}).get("Weapon", [])) if isinstance(model.get("commonWeapons"), dict) else []
    resolved_mounts = []
    for mount in mounts:
        if isinstance(mount, dict) and mount.get('preset') and mount.get('slot') is not None:
            for slot in as_list(model.get('WeaponSlots', {}).get('WeaponSlot')):
                if slot.get('index') != mount['slot']:
                    continue
                for preset in as_list(slot.get('WeaponPreset')):
                    if preset.get('name') == mount['preset']:
                        resolved_mounts.extend(as_list(preset.get('Weapon')))
        else:
            resolved_mounts.append(mount)
    mounts = resolved_mounts
    for mount_index, mount in enumerate(as_list(mounts)):
        add_weapon(mount, f"commonWeapons.Weapon[{mount_index + 1}]")

    # Aircraft pylons list every selectable option and embedded weapon. These
    # option records are kept inside this vehicle JSON rather than a global table.
    weapon_slots = model.get("WeaponSlots", {}) if isinstance(model.get("WeaponSlots"), dict) else {}
    slots_out = []
    slot_options: dict[tuple[int, str], dict] = {}
    slot_values = as_list(weapon_slots.get("WeaponSlot"))
    if branch_id == 'aviation':
        slot_values = []  # Dedicated recursive resolver handles aircraft stores.
    for slot_record in slot_values:
        if not isinstance(slot_record, dict):
            continue
        slot_index = int(slot_record.get("index", 0))
        options_out = []
        for option in as_list(slot_record.get("WeaponPreset")):
            if not isinstance(option, dict):
                continue
            option_name = str(option.get("name") or "")
            option_weapons = []
            for mount_index, mount in enumerate(as_list(option.get("Weapon"))):
                weapon_id = add_weapon(mount, f"WeaponSlots[{slot_index}].{option_name}.Weapon[{mount_index + 1}]", slot_index)
                if weapon_id:
                    option_weapons.append(weapon_id)
            option_out = {"id": option_name,
                          "name": localized_or_code(lang, ["weapon_preset/" + option_name, option_name + "/name", option_name], option_name),
                          "requires_modification": option.get("reqModification"),
                          "pylon_nodes": as_list(option.get("ShowNodes", {}).get("node")) if isinstance(option.get("ShowNodes"), dict) else [],
                          "weapons": option_weapons,
                          "source": source_name(model_path, f".WeaponSlots.WeaponSlot[{slot_index}].WeaponPreset")}
            options_out.append(option_out)
            slot_options[(slot_index, option_name)] = option_out
        slots_out.append({"index": slot_index, "tier": slot_record.get("tier"), "order": slot_record.get("order"),
                          "options": options_out, "source": source_name(model_path, ".WeaponSlots.WeaponSlot")})

    loadouts = []
    preset_data = model.get("weapon_presets", {}).get("preset", []) if isinstance(model.get("weapon_presets"), dict) else []
    for preset in as_list(preset_data):
        if not isinstance(preset, dict):
            continue
        ref = preset.get("blk")
        preset_file = referenced_blk(ref)
        preset_def = load_json(preset_file) if preset_file else {}
        assignment_rows = []
        for assignment in as_list(preset_def.get("Weapon")):
            if not isinstance(assignment, dict):
                continue
            slot_index = assignment.get("slot")
            option_id = assignment.get("preset")
            option = slot_options.get((int(slot_index), str(option_id))) if slot_index is not None else None
            assignment_rows.append({"slot": slot_index, "option": option_id,
                                    "name": option.get("name") if option else option_id,
                                    "weapons": option.get("weapons", []) if option else [],
                                    "source": source_name(preset_file, ".Weapon")})
        preset_id = str(preset.get("name") or (Path(ref).stem if ref else "preset"))
        loadouts.append({"id": preset_id,
                         "name": localized_or_code(lang, ["weapon_preset/" + preset_id, preset_id + "/name", preset_id], preset_id),
                         "slots": assignment_rows, "source": source_name(model_path, ".weapon_presets.preset")})

    mounts_value = model.get("commonWeapons", {}).get("Weapon", []) if isinstance(model.get("commonWeapons"), dict) else []
    for mount in as_list(mounts_value):
        ref = mount.get("blk") if isinstance(mount, dict) else None
        weapon_ref = Path(ref).stem if isinstance(ref, str) else None
        if not weapon_ref:
            continue
        weapon_path = referenced_blk(ref)
        if not weapon_path:
            continue
        for ammo, value in load_json(weapon_path).items():
            if not isinstance(value, dict):
                continue
            bullets = as_list(value.get("bullet"))
            for bullet in bullets:
                if isinstance(bullet, dict) and isinstance(bullet.get("bulletName"), str):
                    key = bullet["bulletName"]
                    label = localized(lang, key + "/name/short")[0] or localized(lang, key + "/name")[0] or localized(lang, key)[0]
                    if label:
                        ammo_names.setdefault(ammo.casefold(), set()).add(label)

    loadout_data = {
        "maximum_load_mass_kg": weapon_slots.get("maxloadMass"),
        "maximum_left_consoles_mass_kg": weapon_slots.get("maxloadMassLeftConsoles"),
        "maximum_right_consoles_mass_kg": weapon_slots.get("maxloadMassRightConsoles"),
        "maximum_disbalance_kg": weapon_slots.get("maxDisbalance"),
        "slots": slots_out, "presets": loadouts,
        "source": source_name(model_path, ".WeaponSlots / .weapon_presets"),
    }
    aircraft_catalog = None
    if branch_id == 'aviation':
        from aircraft_loadouts import build_loadouts
        from aircraft_legacy import build_legacy_loadouts
        builder = build_loadouts if model.get('WeaponSlots',{}).get('WeaponSlot') else build_legacy_loadouts
        loadout_data = builder({**model, "model":code}, root, lambda keys, fallback: localized_or_code(lang, keys, fallback))
        loadout_data['supported_custom'] = bool(entry.get('hasWeaponSlots'))
        aircraft_catalog = {item['id']: item for item in loadout_data.pop('catalog')}
        from aircraft_presentation import enrich_aircraft
        enrich_aircraft(code, root, model, sections, weapons, reference_data, mod_images, loadout_data, aircraft_catalog, lang)
    if branch_id == 'army' and model_source:
        optics = next(s for s in sections if s['id'] == 'optics')
        optics['rows'] = []
        for station, label in [('cockpit', '炮手'), ('commanderView', '车长')]:
            view = model.get(station, {})
            for key, suffix in [('zoomOutFov', '广角视场'), ('zoomInFov', '放大视场')]:
                optics['rows'].append(row(label + suffix, view.get(key), model_source + '.' + station + '.' + key, '°'))
        night_vision = []
        for configuration, devices in [("基础", model.get("nightVision", {})),
                ("夜视改装", model.get("modifications", {}).get("night_vision_system", {}).get("effects", {}).get("nightVision", {}))]:
            for device_id, device in devices.items():
                if not isinstance(device, dict) or not isinstance(device.get("resolution"), list):
                    continue
                label = {"driverIr": "驾驶员夜视仪", "gunnerThermal": "炮手热成像", "commanderViewThermal": "车长热成像"}.get(device_id, device_id)
                source = source_name(model_path, "." + ("nightVision" if configuration == "基础" else "modifications.night_vision_system.effects.nightVision") + "." + device_id)
                night_vision.append({"id": device_id, "configuration": configuration, "resolution": device["resolution"], "generation": None, "source": source})
                optics["rows"].append(row(label + "（" + configuration + "）", " × ".join(str(n) for n in device["resolution"]), source, "像素"))
        engine = model.get('VehiclePhys', {}).get('engine', {})
        mobility = next(s for s in sections if s['id'] == 'mobility')
        mobility['rows'].extend([
            row('发动机额定功率', engine.get('horsePowers'), model_source + '.VehiclePhys.engine.horsePowers', 'hp'),
            row('发动机额定转速', engine.get('maxRPM'), model_source + '.VehiclePhys.engine.maxRPM', 'rpm'),
        ])
        if reference_data:
            mapping = [("forward_km_h", "前进极速", "km/h"), ("reverse_km_h", "倒车极速", "km/h"), ("engine_power_hp", "发动机功率（基础 → 完全体）", "hp")]
            replaced = set()
            for key, label, unit in mapping:
                if key not in reference_data:
                    continue
                values = {}
                for mode, states in reference_data[key].items():
                    values[mode] = (f"{states['stock']:,.0f} → {states['upgraded']:,.0f}" if "stock" in states else states.get("upgraded"))
                mobility["rows"].append(row(label, values, reference_data["source"], unit, "official_reference_snapshot"))
                replaced.add(key)
            labels = {"forward_km_h": "模型前进极速", "reverse_km_h": "模型倒车极速", "engine_power_hp": "发动机额定功率"}
            mobility["rows"] = [r for r in mobility["rows"] if r["label"] not in {labels[k] for k in replaced}]
        legacy_weapon_rows = []
        for mount in mounts:
            ref = mount.get('blk', '')
            if not ref or 'dummy_weapon' in ref:
                continue
            key = Path(ref).stem
            label = localized(lang, 'weapons/' + key)[0] or localized(lang, key + '/name')[0] or localized(lang, key)[0] or key
            label = clean_vehicle_name(label, key)
            legacy_weapon_rows.append(row('武器', label, model_source + '.commonWeapons.Weapon.blk'))
            legacy_weapon_rows.append(row('备弹', mount.get('bullets'), model_source + '.commonWeapons.Weapon.bullets', '发'))
            limits = mount.get('limits', {}).get('pitch')
            if limits and mount.get('trigger') == 'gunner0':
                legacy_weapon_rows.append(row('主炮俯仰范围', str(limits[0]) + ' ～ ' + str(limits[1]), model_source + '.commonWeapons.Weapon.limits.pitch', '°'))
                stabilizer = mount.get('gunStabilizer', {})
                legacy_weapon_rows.append(row('主炮稳定器', '双向稳定' if stabilizer.get('hasHorizontal') and stabilizer.get('hasVertical') else None, model_source + '.commonWeapons.Weapon.gunStabilizer'))
        if legacy_weapon_rows:
            next(s for s in sections if s['id'] == 'armaments')['rows'] = legacy_weapon_rows
    for mount in mounts:
        weapon_ref = mount.get("blk") if isinstance(mount, dict) else None
        if not isinstance(weapon_ref, str):
            continue
        weapon_path = root / "aces.vromfs.bin_u" / weapon_ref.lower().replace(".blk", ".blkx")
        if not weapon_path.is_file():
            continue
        for ammo, value in load_json(weapon_path).items():
            if not isinstance(value, dict):
                continue
            bullets = value.get("bullet", [])
            if isinstance(bullets, dict):
                bullets = [bullets]
            for bullet in bullets:
                if isinstance(bullet, dict) and isinstance(bullet.get("bulletName"), str):
                    key = bullet["bulletName"]
                    label = localized(lang, key + "/name/short")[0] or localized(lang, key + "/name")[0] or localized(lang, key)[0]
                    if label:
                        ammo_names.setdefault(ammo.casefold(), set()).add(label)
    talisman_cost = entry.get("modifications", {}).get("premExpMul", {}).get("costGold")
    if talisman_cost is not None:
        next(s for s in sections if s["id"] == "economy")["rows"].append(row("护身符费用", talisman_cost, "wpcost.blkx.modifications.premExpMul.costGold", "金鹰"))
    mods = []
    untranslated = []
    for mod_id, mod in (entry.get("modifications") or {}).items():
        if not isinstance(mod, dict) or int(mod.get("tier") or 0) <= 0:
            continue
        definition = {**definitions.get(mod_id, {}), **mod}
        if definition.get("isHidden"):
            continue
        candidates = ["modification/" + mod_id, "modification/" + mod_id + "_expendable",
                      "modification/" + mod_id + "/name"]
        mod_name = None
        for key in candidates:
            mod_name = localized(lang, key)[0]
            if mod_name:
                break
        if not mod_name and mod_id.endswith("_ammo_pack"):
            names = ammo_names.get(mod_id.removesuffix("_ammo_pack").casefold(), set())
            if names:
                mod_name = " / ".join(sorted(names))
        if not mod_name:
            mod_name = mod_id
            untranslated.append(mod_id)
        else:
            mod_name = clean_vehicle_name(mod_name, mod_id)
        image_ref = definition.get("image", "")
        match = re.search(r'#ui/gameuiskin#([^/]+)$', image_ref)
        icon = root / "atlases.vromfs.bin_u/gameuiskin" / (Path(match[1]).stem + ".png") if match else None
        icon_file = None
        if include_files and icon and icon.is_file():
            icon_file = icon.name
            mod_images[icon_file] = icon
        requires = definition.get("reqModification", [])
        if isinstance(requires, str):
            requires = [requires] if requires else []
        mods.append({"id": mod_id, "name": mod_name, "tier": mod.get("tier"),
                     "category": definition.get("modClass", "other"), "icon_file": icon_file,
                     "description": localized(lang, "modification/" + mod_id + "/desc")[0],
                     "requires": requires,
                     "unlock_ge": mod.get("openCostGold"),
                     "rp": mod.get("reqExp"), "sl": mod.get("value"),
                     "source": "wpcost.blkx modifications." + mod_id})
    # Preserve game definition order within each tier, including empty cells.
    occupied: set[tuple[str, int, int]] = set()
    placed: dict[str, dict] = {}
    mod_by_id = {m["id"]: m for m in mods}
    def first_parent(item):
        return item["requires"][0] if item["requires"] else None
    def descendants(item, visited=None):
        visited = set() if visited is None else visited
        if item["id"] in visited:
            raise ValueError("改装前置关系存在循环。")
        visited = visited | {item["id"]}
        result = [item]
        for child in mods:
            if first_parent(child) == item["id"] and child["category"] == item["category"]:
                result.extend(descendants(child, visited))
        return result
    # Reserve the gaps in a dependency chain so unrelated cards cannot sit on
    # its connector (e.g. AIM-9H -> AIM-9L skips tier II).
    reservations: dict[tuple[str, int, int], str] = {}
    def root_id(item):
        seen = set()
        while first_parent(item) in mod_by_id:
            if item["id"] in seen:
                raise ValueError("改装前置关系存在循环。")
            seen.add(item["id"])
            parent = mod_by_id[first_parent(item)]
            if parent["category"] != item["category"]:
                break
            item = parent
        return item["id"]
    pending_mods = list(mods)
    while pending_mods:
        progress = False
        for item in list(pending_mods):
            parent = first_parent(item)
            if parent and parent in {m["id"] for m in pending_mods}:
                continue
            column = placed[parent]["column"] if parent in placed and placed[parent]["category"] == item["category"] else 1
            chain = root_id(item)
            chain_end = max(m["tier"] for m in descendants(item))
            while any((item["category"], t, column) in occupied or
                      reservations.get((item["category"], t, column), chain) != chain
                      for t in range(item["tier"], chain_end + 1)):
                column += 1
            item["column"] = column
            occupied.add((item["category"], item["tier"], column))
            for t in range(item["tier"], chain_end + 1):
                reservations[(item["category"], t, column)] = chain
            placed[item["id"]] = item
            pending_mods.remove(item)
            progress = True
        if not progress:
            raise ValueError("改装前置关系存在循环。")

    image_sources: dict[str, Path] = dict(mod_images)
    candidates = {
        "army": (root / "tex.vromfs.bin_u/tanks" / (code + ".png"),
                 root / "atlases.vromfs.bin_u/units" / (code + ".png")),
        "aviation": (root / "tex.vromfs.bin_u/aircrafts" / (code + ".png"), root / "atlases.vromfs.bin_u/units" / (code + ".png")),
        "helicopters": (root / "tex.vromfs.bin_u/aircrafts" / (code + ".png"), root / "atlases.vromfs.bin_u/units" / (code + ".png")),
        "boats": (root / "tex.vromfs.bin_u/ships" / (code + ".png"), root / "atlases.vromfs.bin_u/units" / (code + ".png")),
        "ships": (root / "tex.vromfs.bin_u/ships" / (code + ".png"), root / "atlases.vromfs.bin_u/units" / (code + ".png")),
    }.get(branch_id, ())
    image = next((path for path in candidates if path.is_file()), None) if include_files else None
    image_file = None
    if image:
        image_file = vehicle_image_name(code + ".png", large="tex.vromfs.bin_u" in image.parts)
        image_sources[image_file] = image
        source_map["image"] = str(image.relative_to(root)).replace("\\", "/")

    warnings = [
        "本页是结构与部署链路原型；未知或未转换字段显示为“待计算”，不根据其他车辆推算。",
        "改装列表按当前 wpcost.blkx 的研发层级生成；改装名称使用游戏中文本地化，缺少翻译时保留稳定代码。",
    ]
    if untranslated:
        warnings.append("未找到游戏中文名的改装项：" + ", ".join(untranslated))
    if not model:
        warnings.append("未找到此分支对应的模型 BLKX 文件；模型参数保留为待计算。")
    from vehicle_sensors import build_sensors
    sensor_system = build_sensors(model, root)
    from vehicle_economy import build_economy, EconomySource
    economy_section, economy_audit = build_economy(entry, definitions, model, EconomySource.from_root(root))
    sections[:] = [s for s in sections if s['id'] != 'economy'] + [economy_section]
    data = {
        "schema": 1, "kind": "vehicle_page", "id": code, "name": name,
        "country": country, "branch": branch, "branch_id": branch_id, "category": category,
        "rank": entry.get("rank"), "br": {"ab": br("Arcade"), "rb": br("Historical"), "sb": br("Simulation"), **({"grb": br("TankHistorical") if entry.get('economicRankTankHistorical') is not None else br("Historical")} if branch_id == 'aviation' else {})},
        "operator": operator, "research_cost": fmt(entry.get("reqExp")), "purchase_cost": fmt(entry.get('value')),
        "game_version": version, "image_file": image_file,
        "intro": f"{name} 的载具参数页原型。页面以游戏内代码 {code} 作为稳定标识，中文名称取自当前本地化数据。",
        "sections": sections, "modifications": mods, "warnings": warnings,
        "sensors": sensor_system, "weapons": weapons, "ammunition": ammunition,
        "economy_audit": {k:economy_audit[k] for k in ('version','inputs','repair','rewards','talisman')},
        "ammunition_types": ammunition_types, "ammo_stowages": ammo_stowages,
        "night_vision": night_vision if branch_id == "army" and model_source else [],
        "armour_card": armour_card, "official_reference": reference_data,
        "mode_physics": {"arcade_power_multiplier": model.get("arcadePowerMult"),
                         "difficulty_settings": load_json(root / "aces.vromfs.bin_u/config/gameparams.blkx").get("difficulty_settings", {}).get("noArcadeBoost", {}),
                         "difficulty_source": "aces.vromfs.bin_u/config/gameparams.blkx:difficulty_settings.noArcadeBoost; unitinfotype.nut:addToExportTankDataBlockValues",
                         "base_engine_hp": model.get("VehiclePhys", {}).get("engine", {}).get("horsePowers"),
                         "source": source_name(model_path),
                         "status": "raw_parameters_not_a_complete_stat_card_formula"},
        "loadouts": loadout_data,
        "aircraft_catalog": aircraft_catalog,
        "modification_name_overrides": {},
        "modification_tier_requirements": [
            {"tier": tier, "next_tier": tier + 1,
             "count": entry.get(f"needBuyToOpenNextInTier{tier}"),
             "source": f"wpcost.blkx.needBuyToOpenNextInTier{tier}"}
            for tier in range(1, max((m["tier"] for m in mods), default=1))],
        "sources": source_map,
    }
    return data, image_sources


def make_pages(data: dict, source: Path, namespace: str) -> list[dict]:
    code = data["id"]
    exported = dict(data)
    catalog = exported.pop('aircraft_catalog', None)
    shared_pages = []
    if catalog:
        buckets = {}
        for key, item in catalog.items():
            bucket = int(hashlib.sha256(key.encode()).hexdigest()[0], 16) % 4
            buckets.setdefault(bucket, {})[key] = {k:v for k,v in item.items() if k not in ('icon_file', 'icon_type', 'icon_source_file')}
        exported['ordnance_pages'] = []
        for bucket, items in sorted(buckets.items()):
            suffix = 'data/ordnance/aircraft-' + str(bucket) + '.json'
            title = namespace + '/' + suffix
            exported['ordnance_pages'].append(title)
            shared_pages.append({'title':title,'model':'json','content':dumps({'schema':1,'kind':'aircraft_ordnance','items':items}),'file':suffix})
    module = source.read_text(encoding="utf-8")
    css = (ROOT / "src/vehicle.css").read_text(encoding="utf-8")
    js = (ROOT / "src/vehicle.js").read_text(encoding="utf-8")
    css_title = f"模板:{namespace}/vehicle-styles"
    js_title = f"MediaWiki:{namespace}-vehicle.js"
    data_title = f"{namespace}/data/vehicle/{code}.json"
    page_title = code
    style = ("<includeonly>{{ResourceLoader|" + namespace + "-vehicle}}\n"
             "{{#css:\n" + re.sub(r"/\*.*?\*/", "", css, flags=re.S).lstrip().replace("}}", "} }") + "\n}}\n</includeonly>")
    article = "__NOTOC__\n{{" + namespace + "/vehicle-page|id=" + code + "}}\n"
    vehicle_page_template = (
        "<includeonly>\n{{" + namespace + "/vehicle-styles}}\n"
        "<div class=\"wtv-article-shell\">\n"
        "{{#invoke:" + namespace + "/vehicle|page|id={{{id|il_leopard_2a6_hel}}}}}\n"
        "</div>\n</includeonly>"
    )
    pages = [
        {"title": data_title, "model": "json", "content": dumps(exported), "file": "data/vehicle/" + code + ".json"},
        {"title": "模块:" + namespace + "/vehicle", "model": "Scribunto", "content": module, "file": "vehicle.lua"},
        {"title": "模块:" + namespace + "/modifications", "model": "Scribunto", "content": (ROOT / 'src/modifications.lua').read_text(encoding='utf-8'), "file": "modifications.lua"},
        {"title": "模板:" + namespace + "/modifications", "model": "wikitext", "content": '<includeonly>{{' + namespace + '/vehicle-styles}}{{#invoke:' + namespace + '/modifications|page|id={{{id|il_leopard_2a6_hel}}}}}</includeonly>', "file": "modifications.wiki"},
        {"title": "模块:" + namespace + "/vehicle-content", "model": "Scribunto", "content": (ROOT / 'src/vehicle-content.lua').read_text(encoding='utf-8'), "file": "vehicle-content.lua"},
        {"title": "模板:" + namespace + "/vehicle-content", "model": "wikitext", "content": '<includeonly>{{#invoke:' + namespace + '/vehicle-content|page|id={{{id|}}}|kind={{{kind|basic-info}}}}}</includeonly>', "file": "vehicle-content.wiki"},
        {"title": css_title, "model": "wikitext", "content": style, "file": "vehicle-styles.wiki"},
        {"title": "模板:" + namespace + "/vehicle-page", "model": "wikitext", "content": vehicle_page_template, "file": "vehicle-page.wiki"},
        {"title": js_title, "model": "javascript", "content": js, "file": namespace + "-vehicle.js"},
        {"title": page_title, "model": "wikitext", "content": article, "file": "vehicle.wiki"},
    ]
    pages[1:1] = shared_pages
    pages.insert(-1, {'title':'模块:' + namespace + '/loadouts','model':'Scribunto','content':(ROOT / 'src/loadouts.lua').read_text(encoding='utf-8'),'file':'loadouts.lua'})
    for page in pages:
        page["content"] = bind_namespace(page["content"], namespace)
        page["owner"] = "generated"
        page["bytes"] = len(page["content"].encode("utf-8"))
        if page["model"] == "json" and page["bytes"] >= MAX_PAGE_BYTES:
            raise ValueError(f"JSON 数据页超过 2 MiB：{page['title']}")
    pages[-1]["composition"] = {
        "generated_module": "模块:" + namespace + "/vehicle",
        "generated_data": data_title,
        "manual_content": [code + "/basic-info", code + "/player-content"],
        "manual_content_policy": "referenced only; excluded from recurring generator output",
    }
    return pages


def merge_ordnance_pages(first: str, second: str) -> str:
    """Union independently generated shared shards; conflicting facts fail closed."""
    a, b = json.loads(first), json.loads(second)
    if a.get('kind') != 'aircraft_ordnance' or b.get('kind') != 'aircraft_ordnance' or a.get('schema') != b.get('schema'):
        raise ValueError('Only matching aircraft ordnance schemas may be merged')
    merged = dict(a['items'])
    def facts(value):
        if isinstance(value, dict): return {k:facts(v) for k,v in value.items() if k!='source'}
        if isinstance(value, list): return [facts(v) for v in value]
        return value
    for key, value in b['items'].items():
        if key in merged and facts(merged[key]) != facts(value):
            raise ValueError('Conflicting shared ordnance definition: ' + key)
        if key not in merged: merged[key] = value
    return dumps({**a, 'items':dict(sorted(merged.items()))})


def xml_export(pages: list[dict], target: Path) -> None:
    root = ET.Element("{" + XML_NS + "}mediawiki", {"version": "0.11"})
    site = ET.SubElement(root, "{" + XML_NS + "}siteinfo")
    for key, value in [("sitename", "War Thunder BWiki vehicle page prototype"),
                       ("dbname", "warthunder"),
                       ("base", "https://wiki.biligame.com/warthunder/"),
                       ("generator", "WTJ vehicle-page prototype"), ("case", "first-letter")]:
        ET.SubElement(site, "{" + XML_NS + "}" + key).text = value
    spaces = ET.SubElement(site, "{" + XML_NS + "}namespaces")
    for number, name in [(0, ""), (6, "文件"), (8, "MediaWiki"), (10, "模板"), (828, "模块")]:
        ET.SubElement(spaces, "{" + XML_NS + "}namespace", {"key": str(number), "case": "first-letter"}).text = name
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    formats = {"json": "application/json", "Scribunto": "text/plain", "wikitext": "text/x-wiki", "javascript": "text/javascript"}
    for page in pages:
        item = ET.SubElement(root, "{" + XML_NS + "}page")
        ET.SubElement(item, "{" + XML_NS + "}title").text = page["title"]
        ns = 828 if page["model"] == "Scribunto" else 10 if page["title"].startswith("模板:") else 8 if page["title"].startswith("MediaWiki:") else 0
        ET.SubElement(item, "{" + XML_NS + "}ns").text = str(ns)
        revision = ET.SubElement(item, "{" + XML_NS + "}revision")
        ET.SubElement(revision, "{" + XML_NS + "}timestamp").text = stamp
        ET.SubElement(revision, "{" + XML_NS + "}model").text = page["model"]
        ET.SubElement(revision, "{" + XML_NS + "}format").text = formats[page["model"]]
        ET.SubElement(revision, "{" + XML_NS + "}text", {"bytes": str(page["bytes"]), "{" + "http://www.w3.org/XML/1998/namespace" + "}space": "preserve"}).text = page["content"]
    target.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(target, encoding="utf-8", xml_declaration=True)


def make_preview(rendered: str, css: str, js: str, image_file: str | None, out: Path) -> None:
    import html
    out.mkdir(parents=True, exist_ok=True)
    site_report = WIKI / 'vehicle-prototype/site-parse-validation.json'
    if site_report.is_file():
        report = load_json(site_report)
        if report.get('passed') and report.get('css_sha256') == sha256(css.encode('utf-8')):
            css = '\n'.join(report['cases']['css']['decoded_css'])
    if image_file:
        rendered = rendered.replace(f"[[File:{image_file}|center|600px|link=]]",
                                    '<img class="wtv-preview-image" src="../uploads/' + html.escape(image_file, quote=True) + '" alt="游戏载具展示图">')
    rendered = re.sub(r'\[\[File:([A-Za-z0-9_. -]+)\|(26|32)px\|link=\|alt=\]\]',
                      lambda m: '<img src="../uploads/' + html.escape(m[1], quote=True) + '" width="' + m[2] + '" height="' + m[2] + '" alt="">', rendered)
    currency_urls = {
        "Lion": "8/84/ds93ojbxfow4tpepredf70l09710rto.png",
        "Eagle": "4/42/8ur48pgt2hn0r3yoexk4urqk0v658n2.png",
        "Exp": "8/8b/1idvsork6p6ag847uccutfhhk0la2wx.png",
    }
    rendered = re.sub(r'\[\[File:Specs-Card-(Lion|Eagle|Exp)\.png\|14px\|link=\|alt=([^]]+)\]\]',
                      lambda m: '<img src="https://patchwiki.biligame.com/images/warthunder/' + currency_urls[m[1]] + '" width="14" height="14" alt="' + m[2] + '">', rendered)
    for mode, label in (("ab", "街机"), ("rb", "历史")):
        rendered = rendered.replace(f'<span class="wtv-mode-tag">{label}</span>', f'<span class="wtv-mode-tag">{label}</span>')
    rendered = re.sub(r'\[\[Special:EditPage/([^|]+)\|编辑\]\]', lambda m: '<a href="https://wiki.biligame.com/warthunder/Special:EditPage/' + m[1] + '">编辑</a>', rendered)
    # Reuse the image already saved in the user's MHTML reference for offline QA.
    background = ''
    reference = REPO.parent / 'Reference' / 'M1A2 SEPv3 - 战争雷霆中文Wiki.mhtml'
    if reference.is_file():
        import email
        message = email.message_from_bytes(reference.read_bytes())
        for part in message.walk():
            if 'tn56nnxzezo04oztgpufpoq4x9dz64c.jpg' in str(part.get('Content-Location', '')):
                (out / 'bwiki-background.jpg').write_bytes(part.get_payload(decode=True))
                background = '<img src="bwiki-background.jpg" alt="">'
                break
    rendered = re.sub(r'\[\[File:载具图鉴-[^|]+\|1200px\|link=\]\]', background, rendered)
    player_shell = '<div class="wtv-article-shell">' + rendered + '</div>'
    document = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                '<title>JSON 载具页面原型</title><style>body{font:14px/1.6 system-ui,sans-serif;margin:0;padding:16px;background:#fff}'
                + css + '</style><main>' + player_shell + '</main><script>' + js + '</script></html>')
    (out / "index.html").write_text(document, encoding="utf-8")
    modifications = re.search(r'<div class="wtv-block" id="wtv-modifications">(.*?)</div></div></div></div>', rendered, re.S)
    if modifications:
        standalone = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
                      '<meta name="viewport" content="width=device-width,initial-scale=1">'
                      '<title>改装研发树预览</title><style>body{font:14px/1.6 system-ui,sans-serif;margin:0;padding:16px;background:#f0f1f2}'
                      + css + '</style><div class="wtv" data-mode="rb">' + modifications[0]
                      + '</div><script>' + js + '</script></html>')
        (out / "modifications.html").write_text(standalone, encoding="utf-8")


def verify_lua(data: dict, source: Path, pages: list[dict], preview: Path) -> tuple[str, dict]:
    try:
        from lupa import LuaRuntime
    except ImportError:
        sys.path.insert(0, str(ROOT / "vendor/python/packages"))
        from lupa import LuaRuntime
    lua = LuaRuntime(unpack_returned_tuples=True)
    def as_lua(value):
        if isinstance(value, dict):
            return lua.table_from({k: as_lua(v) for k, v in value.items()})
        if isinstance(value, list):
            return lua.table_from([as_lua(v) for v in value])
        return value
    by_title = {p["title"]: p["content"] for p in pages}
    namespace = next(p["title"].split("/data/", 1)[0] for p in pages if p["model"] == "json")
    page_title = data["id"]
    article = by_title[page_title]
    template = by_title[f"模板:{namespace}/vehicle-page"]
    assert "{{" + namespace + "/vehicle-page|id=" + data["id"] + "}}" in article
    assert "{{{id|il_leopard_2a6_hel}}}" in template
    assert "wtv-article-shell" in template
    content_source = by_title['模块:' + namespace + '/vehicle-content']
    assert '#ifexist:' in content_source and "'basic-info'" in content_source and "'player-content'" in content_source
    assert article == "__NOTOC__\n{{" + namespace + "/vehicle-page|id=" + data["id"] + "}}\n"
    assert not any(p["title"].endswith(("/user-content", "/basic-info", "/player-content")) for p in pages)
    for field in ('sensors', 'weapons', 'ammunition', 'loadouts'):
        assert field in data
    weapon_ids = {w['id'] for w in data['weapons']}
    ammo_ids = {a['id'] for a in data['ammunition']}
    assert all(set(w['ammunition_ids']) <= ammo_ids for w in data['weapons'])
    if not data.get('aircraft_catalog'):
        assert all(set(o['weapons']) <= weapon_ids for slot in data['loadouts']['slots'] for o in slot['options'])
    else:
        assert all(i['id'] in data['aircraft_catalog'] for slot in data['loadouts']['slots'] for o in slot['options'] for i in o['items'])
    data_title = namespace + '/data/vehicle/' + data['id'] + '.json'
    loaded = []
    datasets = {p['title']: json.loads(p['content']) for p in pages if p['model']=='json'}
    lua.globals().load_vehicle = lambda title: (loaded.append(title), as_lua(datasets[title]))[1]
    lua.execute("mw={loadJsonData=function(title) return load_vehicle(title) end}")
    shared = lua.execute(by_title['模块:' + namespace + '/modifications'])
    lua.globals().shared_modifications = shared
    lua.execute("package.loaded['Module:" + namespace + "/modifications']=shared_modifications")
    lua.globals().shared_content = lua.execute(content_source)
    lua.execute("package.loaded['Module:" + namespace + "/vehicle-content']=shared_content")
    lua.globals().shared_loadouts = lua.execute(by_title['模块:' + namespace + '/loadouts'])
    lua.execute("package.loaded['Module:" + namespace + "/loadouts']=shared_loadouts")
    def preview_content(_frame, expression):
        kind = 'basic-info' if '/basic-info' in expression else 'player-content'
        label = '载具描述子页拼合测试' if kind == 'basic-info' else '玩家内容区拼合测试'
        return '<section data-' + ('basic-info' if kind == 'basic-info' else 'player-content') + '="preview-fixture"><p>' + label + '</p></section>'
    def page_frame(values):
        return lua.table_from({'args': lua.table_from(values), 'preprocess': preview_content})
    module = lua.execute(by_title["模块:" + namespace + "/vehicle"])
    id_frame = lambda value=None: lua.table_from({"args": lua.table_from({} if value is None else {"id": value})})
    assert module.content_id(id_frame()) == "il_leopard_2a6_hel"
    assert module.content_id(id_frame(data["id"])) == data["id"]
    assert module.content_id(id_frame("../invalid")) == ""
    assert module.content_id(id_frame("bad|title")) == ""
    rendered = module.page(page_frame({"id": data["id"]}))
    assert isinstance(rendered, str) and 'class="wtv"' in rendered and 'wtv-error' not in rendered
    assert loaded == [data_title] + datasets[data_title].get('ordnance_pages', []), loaded
    assert data["name"] in rendered
    if data.get("image_file"):
        assert "[[File:" + data["image_file"] + "|center|600px|link=]]" in rendered
    for mode in ("ab", "rb"):
        body = module.page(page_frame({"id": data["id"], "mode": mode}))
        assert f'data-mode="{mode}"' in body
        assert f'data-wtv-mode="{mode}" aria-pressed="true"' in body
    bad_id = module.page(lua.table_from({"args": lua.table_from({"id": "../bad"})}))
    bad_mode = module.page(lua.table_from({"args": lua.table_from({"id": data["id"], "mode": "xx"})}))
    assert "wtv-error" in bad_id and "wtv-error" in bad_mode
    rendered_ab = module.page(page_frame({"id": data["id"], "mode": "ab"}))
    assert rendered_ab.count('data-wtv-mode=') == 2
    assert 'data-wtv-mode="sb"' not in rendered_ab

    # Check escaped plain text and never interpret caller-controlled values as wikitext.
    hostile = json.loads(dumps(data))
    hostile["name"] = '<img src=x onerror="alert(1)">[[File:x|1px]]{{bad}}'
    lua.globals().load_vehicle = lambda title: as_lua(hostile if title == data_title else datasets[title])
    escaped = module.page(page_frame({"id": data["id"]}))
    assert "<img src=x" not in escaped and "[[File:x" not in escaped and "{{bad}}" not in escaped
    assert "&lt;img" in escaped
    css = (ROOT / "src/vehicle.css").read_text(encoding="utf-8")
    js = (ROOT / "src/vehicle.js").read_text(encoding="utf-8")
    make_preview(rendered, css, js, data.get("image_file"), preview)
    return rendered, {"lua_module": "passed", "two_modes": "passed", "invalid_inputs": "passed",
                     "plain_text_escape": "passed", "json_page_reads": loaded,
                     "editor_content_slots": "basic-info + player-content; separate edit targets; excluded from generated pages",
                     "embedded_vehicle_data": {field: len(data[field]) for field in ("sensors", "weapons", "ammunition")},
                     "page_render_bytes": len(rendered.encode("utf-8"))}


def write_output(code: str, namespace: str, out: Path, datamine: Path) -> dict:
    data, images = one_vehicle(code, datamine)
    # Keep manually curated per-vehicle names across regeneration. A future app
    # can edit this same JSON field without maintaining a global exception list.
    existing = out / 'pages' / 'data' / 'vehicle' / (code + '.json')
    if existing.is_file():
        overrides = load_json(existing).get('modification_name_overrides', {})
        if not isinstance(overrides, dict) or any(
                not isinstance(k, str) or not isinstance(v, str) or not v.strip()
                for k, v in overrides.items()):
            raise ValueError('modification_name_overrides 必须为改装代码到非空名称的映射。')
        data['modification_name_overrides'] = overrides
    pages = make_pages(data, ROOT / "src/vehicle.lua", namespace)
    if out.exists() and out.resolve() in (WIKI / "production").resolve().parents:
        raise ValueError("禁止将原型导出到既有正式交付目录。")
    out.mkdir(parents=True, exist_ok=True)
    (out / "uploads").mkdir(exist_ok=True)
    for page in pages:
        target = out / "pages" / page["file"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page["content"], encoding="utf-8")
        page["sha256"] = sha256(page["content"].encode("utf-8"))
    for filename, source in images.items():
        shutil.copyfile(source, out / "uploads" / filename)
    rendered, checks = verify_lua(data, ROOT / "src/vehicle.lua", pages, out / "preview")
    xml = out / f"{namespace}-vehicle-page.xml"
    xml_export(pages, xml)
    ns = {"m": XML_NS}
    imported = ET.parse(xml).findall("m:page", ns)
    assert len(imported) == len(pages)
    roundtrip = {p.findtext("m:title", namespaces=ns): p.findtext("m:revision/m:text", default="", namespaces=ns) for p in imported}
    expected = {p["title"]: p["content"] for p in pages}
    assert roundtrip == expected
    assert len({p["title"] for p in pages}) == len(pages)
    report = {
        "kind": "vehicle_page_prototype", "schema": 1, "game_version": data["game_version"],
        "vehicle_id": code, "vehicle_name": data["name"], "title": code,
        "live_wiki_written": False, "pages": pages,
        "uploads": {name: {"source": str(src), "sha256": sha256((out / "uploads" / name).read_bytes())} for name, src in images.items()},
        "xml": {"path": xml.name, "bytes": xml.stat().st_size, "sha256": sha256(xml.read_bytes()), "pages": len(imported), "roundtrip": "passed"},
        "validation": checks,
        "external_deploy": {"attempted": False, "reason": "本工具生成正式标题的本地候选包；BWiki Special:Import 需维护者手动导入并验收。"},
    }
    (out / "manifest.json").write_text(dumps(report, pretty=True), encoding="utf-8")
    from testing_cleanup import write_cleanup
    write_cleanup(out / 'Cleanup', [p['title'] for p in pages] + ['文件:' + name for name in images],
                  active_contents=[p['content'] for p in pages])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit", default="il_leopard_2a6_hel", help="载具游戏代码")
    parser.add_argument("--namespace", default="WTJ", help="正式共用资源命名空间 WTJ；文章标题使用载具代码")
    parser.add_argument("--out", type=Path, default=WIKI / "vehicle-prototype", help="本地输出目录")
    parser.add_argument("--datamine", type=Path, default=REPO, help="只读 datamine 根目录")
    args = parser.parse_args()
    if not PREFIX_RE.fullmatch(args.namespace):
        parser.error("当前正式资源命名空间为 WTJ。")
    report = write_output(args.unit, args.namespace, args.out.resolve(), args.datamine.resolve())
    print(dumps({"vehicle_id": report["vehicle_id"], "title": report["title"],
                 "pages": len(report["pages"]), "xml": report["xml"],
                 "validation": report["validation"], "live_wiki_written": False}, pretty=True))


if __name__ == "__main__":
    main()
