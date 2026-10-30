"""Legacy (preset-only, no ``WeaponSlots``) aircraft loadouts - Pe-8 class.

``build_legacy_loadouts(model, root, localize)`` returns **the same schema as**
``aircraft_loadouts.build_loadouts`` so ``vehicle_page.py``, ``vehicle.lua`` and
``src/loadouts.lua`` consume it unchanged.  Deliberate differences:

* ``supported_custom`` is ``False`` (evidence in ``known_rules[custom_presets_unsupported]``);
* ``slots`` / ``display_slots`` / ``matrix_rows`` are empty - there is no
  player-selectable pylon;
* each entry of ``presets`` carries its own ``items`` / ``mass_kg`` /
  ``status`` / ``entity`` and ``fixed_preset=True``; ``assignments`` stays empty
  because a legacy preset blk names weapons, not ``{slot, preset}`` pairs (the
  shape ``build_loadouts`` expects, which would log "WeaponSlot does not exist"
  for every entry and return an empty catalog);
* ``turrets`` lists the fixed ``commonWeapons`` gunners with their ammunition.

Munition parsing reuses ``aircraft_loadouts`` (``_Data``, ``_Catalog``,
``_resolve_weapon``, ``_munition_of``); nothing here writes to the datamine.
"""
from __future__ import annotations

import json
from pathlib import Path

try:  # works as scripts.aircraft_legacy (package) and as a flat module
    from . import aircraft_loadouts as _al
except ImportError:  # pragma: no cover - executed as a top-level module
    import aircraft_loadouts as _al

_as_list = _al._as_list
_num = _al._num
_round = _al._round
_Data = _al._Data
_Catalog = _al._Catalog
_resolve_weapon = _al._resolve_weapon
_localize = _al._localize
_munition_of = _al._munition_of
TIER_ICON_PATH = _al.TIER_ICON_PATH

TURRET_TRIGGER_PREFIX = "gunner"


def has_weapon_slots(model) -> bool:
    """True when the unit blk exports a non-empty ``WeaponSlots.WeaponSlot``."""
    slots = model.get("WeaponSlots") if isinstance(model, dict) else None
    if not isinstance(slots, dict):
        return False
    return any(isinstance(s, dict) for s in _as_list(slots.get("WeaponSlot")))


def entity_record(root: Path, code: str | None) -> dict:
    """``wpcost.blkx[code]`` - only reads the file, never caches it globally."""
    if not code:
        return {}
    path = Path(root) / "char.vromfs.bin_u/config/wpcost.blkx"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    entry = data.get(code) if isinstance(data, dict) else None
    return entry if isinstance(entry, dict) else {}


def _turret_ammunition(data: _Data, mount: dict) -> dict:
    """Weapons blk of one turret mount -> every ``bullet`` sub block name."""
    ref = mount.get("blk")
    block, path = data.ref_json(ref)
    if not isinstance(block, dict):
        return {"resolved": None, "rounds": [], "class": None, "weapon_type": None,
                "block_bullets": None, "variant_round_blocks": {}, "unresolved": ["missing_blk"]}
    rounds = []
    for bullet in _as_list(block.get("bullet")):
        if not isinstance(bullet, dict):
            continue
        rounds.append({
            "bulletName": bullet.get("bulletName"),
            "bulletType": bullet.get("bulletType"),
            "caliber_mm": _round((_num(bullet.get("caliber")) or 0) * 1000, 2),
            "mass_kg": _num(bullet.get("mass")),
            "muzzle_velocity_m_s": _num(bullet.get("speed")),
            "explosive_type": bullet.get("explosiveType"),
            "explosive_mass_kg": _num(bullet.get("explosiveMass")),
        })
    variants = {name: len(_as_list(value.get("bullet"))) if isinstance(value, dict) else 0
                for name, value in block.items()
                if isinstance(value, dict) and name != "bullet" and "bullet" in value}
    return {"resolved": data.rel(path),
            "class": "cannon" if block.get("cannon") else "machine gun",
            "weapon_type": block.get("weaponType"),
            "block_bullets": block.get("bullets"),
            "rounds": rounds,
            "variant_round_blocks": variants,
            "unresolved": [] if rounds else ["no_bullet_block"]}


def build_legacy_loadouts(model, root, localize) -> dict:
    """Loadouts of a unit that only offers its ``weapon_presets`` list.

    ``model``    - parsed aircraft blk (``gamedata/flightmodels/<code>.blkx``).
    ``root``     - datamine root (``War-Thunder-Datamine``), opened read-only.
    ``localize`` - ``(candidates: list[str], fallback: str) -> str``.
    """
    root = Path(root)
    data = _Data(root)
    catalog = _Catalog(data)
    model = model if isinstance(model, dict) else {}
    code = model.get("model")
    entity = entity_record(root, code)
    entity_weapons = entity.get("weapons") if isinstance(entity.get("weapons"), dict) else {}
    slots_present = has_weapon_slots(model)

    unknown_mounts: list[dict] = []
    if slots_present:
        unknown_mounts.append({
            "id": "unit_exports_weapon_slots",
            "detail": ("model exports WeaponSlots; this builder is for preset-only units - "
                       "aircraft_loadouts.build_loadouts is the right parser"),
        })

    # -------------------------------------------------------------- turrets
    common = model.get("commonWeapons") if isinstance(model.get("commonWeapons"), dict) else {}
    mounts = [w for w in _as_list(common.get("Weapon")) if isinstance(w, dict)]
    turrets = []
    for position, mount in enumerate(mounts, start=1):
        trigger = str(mount.get("trigger") or "")
        if not trigger.startswith(TURRET_TRIGGER_PREFIX):
            unknown_mounts.append({"id": "fixed_mount_outside_gunner_trigger", "position": position,
                                   "trigger": mount.get("trigger"), "blk": mount.get("blk"),
                                   "detail": "not reported by vehicle_page.add_weapon as a turret gun"})
        ammunition = _turret_ammunition(data, mount)
        turrets.append({
            "position": position,
            "trigger": trigger,
            "blk": mount.get("blk"),
            "resolved": ammunition["resolved"],
            "turret": mount.get("turret"),
            "bullets": mount.get("bullets"),
            "limits": mount.get("limits"),
            "dm": mount.get("dm"),
            "gunnerDm": mount.get("gunnerDm"),
            "gunDm": mount.get("gunDm"),
            "class": ammunition.get("class"),
            "weapon_type": ammunition.get("weapon_type"),
            "block_bullets": ammunition.get("block_bullets"),
            "ammunition": ammunition["rounds"],
            "variant_round_blocks": ammunition.get("variant_round_blocks", {}),
            "unresolved": ammunition.get("unresolved", ["missing_blk"]),
        })

    # -------------------------------------------------------------- presets
    specs = []
    if isinstance(model.get("weapon_presets"), dict):
        specs = [p for p in _as_list(model["weapon_presets"].get("preset")) if isinstance(p, dict)]
    presets = []
    for spec in specs:
        name = str(spec.get("name") or "")
        block, path = data.ref_json(spec.get("blk"))
        entries = [w for w in _as_list((block or {}).get("Weapon")) if isinstance(w, dict)]
        weapons = [_resolve_weapon(data, catalog, localize, w) for w in entries]
        items: dict[str, int] = {}
        for weapon in weapons:
            for item in weapon["items"]:
                items[item["id"]] = items.get(item["id"], 0) + item["count"]
        mass_known = bool(weapons) and all(w["mass_kg"] is not None for w in weapons)
        mass = _round(sum(w["mass_kg"] for w in weapons)) if mass_known else None
        problems = []
        if block is None:
            problems.append({"blk": spec.get("blk"), "problem": "referenced preset blk not exported"})
        for weapon in weapons:
            for problem in weapon["unresolved"]:
                problems.append({"blk": weapon.get("blk"), "problem": problem})
        trig = {}
        for weapon in weapons:
            trig[str(weapon.get("trigger"))] = trig.get(str(weapon.get("trigger")), 0) + len(weapon["items"])
        icon_type = None
        config = spec.get("weaponConfig") if isinstance(spec.get("weaponConfig"), dict) else {}
        config_weapon = config.get("Weapon") if isinstance(config.get("Weapon"), dict) else {}
        if isinstance(config_weapon.get("iconType"), str):
            icon_type = config_weapon["iconType"]
        if not icon_type:
            for weapon in weapons:
                icon_type = next((catalog.items[i["id"]]["icon_type"] for i in weapon["items"]
                                  if catalog.items[i["id"]]["icon_type"]), None)
                if icon_type:
                    break
        entity_weapon = entity_weapons.get(name) if isinstance(entity_weapons.get(name), dict) else {}
        presets.append({
            "id": name,
            "name": _localize(localize, [name], name, data)[0],
            "preset_type": None,
            "is_default": ("default" in name) or bool((spec.get("tags") or {}).get("free")),
            "assignments": [],
            "problems": problems,
            "source": data.rel(path) or spec.get("blk"),
            "requires_modification": spec.get("reqModification") or entity_weapon.get("reqModification"),
            "items": [{"id": cid, "count": cnt} for cid, cnt in items.items()],
            "weapon_count": sum(len(w["items"]) for w in weapons),
            "mass_kg": mass,
            "mass_status": "known" if mass_known else "unknown",
            "triggers": trig,
            "icon_type": icon_type,
            "icon_path": TIER_ICON_PATH + icon_type if icon_type else None,
            "icon_source_file": data.icon_source_file(icon_type),
            "show_in_weapon_menu": True,
            "has_targeting_pod": False,
            "fixed_preset": True,
            "status": "ok" if mass_known and not problems else "unknown",
            "entity": {
                "source": ("char.vromfs.bin_u/config/wpcost.blkx:" + code + ".weapons." + name) if code else None,
                "totalBombRocketMass": entity_weapon.get("totalBombRocketMass"), "comparison_basis":"integer-truncated entity summary vs precise BLK sum",
                "totalBombCount": entity_weapon.get("totalBombCount"),
                "weaponDamage": entity_weapon.get("weaponDamage"),
                "value": entity_weapon.get("value"),
                "mass_matches_blk": ("unknown" if not entity_weapon or mass is None
                                     else entity_weapon.get("totalBombRocketMass") == int(mass)),
            },
            "weapons": weapons,
        })

    # ---------------------------------------------------------- matrix rows
    rows = []
    for cid in catalog.order:
        item = catalog.items[cid]
        holders = [p for p in presets if any(i["id"] == cid for i in p["items"])]
        rows.append({
            "catalog_id": cid,
            "name": item["name"],
            "type": item["type"],
            "icon_source_file": item["icon_source_file"],
            "counts_by_slot": {},
            "visual_left_to_right": [],
            "cells": {},  # keep aircraft_presentation.enrich_aircraft (L155) from KeyError
            "count": max((i["count"] for p in holders for i in p["items"] if i["id"] == cid), default=None),
            "mass_kg": item["mass_kg"],
            "mountable_slots": 0,
            "count_set": sorted({i["count"] for p in holders for i in p["items"] if i["id"] == cid}),
            "min_count": None,
            "max_count": None,
            "presets": [p["id"] for p in holders],
        })

    weapon_slots = model.get("WeaponSlots") if isinstance(model.get("WeaponSlots"), dict) else {}
    heaviest = max((p["mass_kg"] for p in presets if p["mass_kg"] is not None), default=None)
    limits = {
        "maxloadMass": weapon_slots.get("maxloadMass"),
        "maxloadMassLeftConsoles": weapon_slots.get("maxloadMassLeftConsoles"),
        "maxloadMassRightConsoles": weapon_slots.get("maxloadMassRightConsoles"),
        "maxDisbalance": weapon_slots.get("maxDisbalance"),
        "weaponsSlotCount": weapon_slots.get("weaponsSlotCount"),
        "tiers_count_used": 0,
        "unit": "kg",
        "source": "model.WeaponSlots (absent on this unit)",
        "apply_rule": "no console limits exist without WeaponSlots; heaviest preset reported instead",
        "heaviest_preset_kg": heaviest,
    }

    known_rules = [
        {"id": "custom_presets_unsupported",
         "rule": ("player custom mounts require wpcost[unit].hasWeaponSlots == true; this record has no such key "
                  "(default false) and the model exports no WeaponSlots, so the client only offers the presets "
                  "defined in weapon_presets"),
         "source": ("gui.vromfs.bin_u/scripts/unit/unit.nut:220 hasWeaponSlots = uWpCost?.hasWeaponSlots ?? false; "
                    "unit.nut:596-602 getWeapons(); unit/unitweaponrycustompresets.nut:81,183 getCustomPresetsConfig; "
                    "weaponry/weaponrypresetswnd.nut:180-182 custom_weapons_disabled_txt; "
                    "respawn/weaponselectorutils.nut:30-53 !hasWeaponSlots branch"),
         "evidence": {"unit": code,
                      "wpcost_key": ("char.vromfs.bin_u/config/wpcost.blkx:" + code) if code else None,
                      "wpcost_hasWeaponSlots": bool(entity.get("hasWeaponSlots")),
                      "model_weapon_slots": [] if not slots_present else "present"}},
        {"id": "preset_shape",
         "rule": ("a legacy preset blk holds Weapon[] = {trigger, blk, bullets, emitter, external}; "
                  "each entry is one mounted store and there is no slot/preset pair"),
         "source": "weaponrypresets.nut:167-182 getUnitWeapons (slots.len()==0 -> getPresetWeaponsByPath)",
         "presets": [p["id"] for p in presets],
         "blks": [p["source"] for p in presets]},
        {"id": "unit_count",
         "rule": "preset count = sum of Weapon[] entries; each entry resolved through getWeaponBlkParams (bullets/container levels)",
         "source": "weaponrypresets.nut:28-52"},
        {"id": "mass",
         "rule": "mass_kg = sum(munition.mass x bullets x container bullets) over all entries; no pylon mass exists on these blks",
         "source": "weaponrypresets.nut:getWeaponBlkParams; aircraft_loadouts option.mass"},
        {"id": "default_preset",
         "rule": "first preset whose name contains 'default' or that has tags.free is the free/default one",
         "source": "weaponrypresets.nut:252-257 getDefaultPresetId",
         "default": next((p["id"] for p in presets if p["is_default"]), None)},
        {"id": "entity_summary_crosscheck",
         "rule": "wpcost[unit].weapons[name].totalBombRocketMass is compared to the summed blk mass; it is not used as the mass",
         "source": "char.vromfs.bin_u/config/wpcost.blkx:<unit>.weapons",
         "mismatches": [p["id"] for p in presets if p["entity"]["mass_matches_blk"] is False]},
        {"id": "turrets",
         "rule": ("fixed commonWeapons gunners keep trigger gunnerN, turret.head/gun and mount.bullets; "
                  "rounds are the bullet blocks of gameData/Weapons/<blk>"),
         "source": "model.commonWeapons.Weapon; weapons/*.blk bullet blocks",
         "mounts": [{"position": t["position"], "trigger": t["trigger"], "blk": t["blk"],
                     "class": t["class"], "weapon_type": t["weapon_type"],
                     "bullets": t["bullets"], "turret": t["turret"],
                     "rounds": len(t["ammunition"]),
                     "round_types": [r["bulletType"] for r in t["ammunition"]],
                     "variant_round_blocks": t["variant_round_blocks"]} for t in turrets],
         "gunnersCount": entity.get("gunnersCount")},
        {"id": "modifications",
         "rule": "reqModification copied verbatim (weapon_presets first, wpcost fallback); ownership not evaluated",
         "source": "weapon_presets.preset[].reqModification; wpcost.weapons[].reqModification"},
    ]
    unknown_rules = unknown_mounts + [
        {"id": "mass_limits_not_evaluated",
         "detail": "this unit has no WeaponSlots limits, so nothing is enforced or displayed as a limit"},
        {"id": "turret_belt_composition",
         "detail": ("turret rounds are taken from the stock weapons blk; the belt_pack/new_gun modifications "
                    "(bulletMod shkas_turret_ap / shkas_turret_apit, weaponMod *_turret_new_gun) are not applied")},
        {"id": "custom_presets",
         "detail": "player custom presets are neither in the datamine nor possible for this unit"},
    ] + catalog.notes

    return {
        "schema": 2,
        "kind": "aircraft_loadouts",
        "model": code,
        "variant": "legacy_presets",
        "supported_custom": False,
        "custom_support_reason": ("no WeaponSlots and no wpcost.hasWeaponSlots: the game only lets the player pick "
                                  "one of the weapon_presets entries"),
        "slots": [],
        "display_slots": [],
        "excluded_slots": [],
        "presets": presets,
        "limits": limits,
        "catalog": [catalog.items[cid] for cid in catalog.order],
        "matrix_rows": rows,
        "turrets": turrets,
        "entity": {
            "source": ("char.vromfs.bin_u/config/wpcost.blkx:" + code) if code else None,
            "gunnersCount": entity.get("gunnersCount"),
            "crewTotalCount": entity.get("crewTotalCount"),
            "weaponmask": entity.get("weaponmask"),
            "weaponUpgrades": [entity.get("weaponUpgrade" + str(i)) for i in (1, 2, 3, 4)
                               if isinstance(entity.get("weaponUpgrade" + str(i)), str)],
        },
        "known_rules": known_rules,
        "unknown_rules": unknown_rules,
    }


def main(argv=None) -> int:
    """CLI: dump one legacy model (writes only the requested file)."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Build a legacy (preset-only) loadout JSON.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--root", default=None)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    root = Path(args.root) if args.root else Path(__file__).resolve().parents[1].parent / "War-Thunder-Datamine"
    path = root / "aces.vromfs.bin_u/gamedata/flightmodels" / (args.model + ".blkx")
    if not path.is_file():
        raise SystemExit("flight model not found: " + str(path))
    model = json.loads(path.read_text(encoding="utf-8-sig"))
    data = _Data(root)

    def localize(candidates, fallback):
        for candidate in candidates:
            text = data.localize_key(candidate)
            if text:
                return text
        return fallback

    result = build_legacy_loadouts(model, root, localize)
    result["source"] = data.rel(path)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print("wrote %s: %d presets, %d turrets, %d catalog" % (
        out, len(result["presets"]), len(result["turrets"]), len(result["catalog"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
