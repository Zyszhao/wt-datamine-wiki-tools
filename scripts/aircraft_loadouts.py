"""Build one aircraft's weapon-slot loadout matrix from the read-only datamine.

Self-contained module: it does not import the vehicle page renderer and it never
writes into the datamine.  ``build_loadouts(model, root, localize)`` walks

    model.WeaponSlots.WeaponSlot[i].WeaponPreset[j].Weapon[k]

recursively through every ``container`` block until it reaches an end munition
(``bullet`` / ``rocket`` / ``bomb`` / ``torpedo``, or the ``payload`` carrier used
by fuel tanks, pods and boosters) and returns

* ``slots``      - purchasable pylons, tier descending == visual left to right;
* ``presets``    - ``weapon_presets.preset[]`` resolved through their referenced blk;
* ``limits``     - raw ``WeaponSlots`` mass limits;
* ``catalog``    - deduplicated munitions keyed by a stable id;
* ``matrix_rows``- per catalog entry, how many can be mounted per slot.

Everything that is computed follows a rule quoted from the client Lua and listed
in ``known_rules``; everything that would need a guess is listed in
``unknown_rules`` instead.  Command line (writes only the given output file)::

    python scripts/aircraft_loadouts.py --model mig_35 --out work/research/mig35-loadouts-v2.json
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

# Game constants read literally from the client Lua.
MIN_TIERS_COUNT = 13                  # weaponrypresets.nut: const MIN_TIERS_COUNT = 13
TIER_ICON_PATH = "#ui/gameuiskin#"    # weaponrypresetsparams.nut: getTierIcon() path

# Sub-blocks holding an end munition.  ``payload`` is the carrier of fuel tanks,
# pods and boosters (unitinfotype.nut:getWeaponParams -> weaponDataBlk?.payload).
MUNITION_BLOCKS = ("bullet", "rocket", "bomb", "torpedo", "payload")
MAX_CONTAINER_DEPTH = 6


def _as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _num(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _round(value, digits=3):
    return None if value is None else round(value + 0.0, digits)


def _slug(value) -> str:
    """Stable, loc-key safe id fragment."""
    out = []
    for char in str(value):
        if char.isascii() and char.isalnum():
            out.append(char.lower())
        elif char in "\\/: -.":
            out.append("_")
    return "".join(out).strip("_") or "unknown"


def _strip_markup(text: str) -> str:
    """Drop the UI colour markup that CSV unit names carry (<col=..>, <img>, tags)."""
    out = []
    depth = 0
    for char in text:
        if char == "<":
            depth += 1
        elif char == ">" and depth:
            depth -= 1
        elif not depth:
            out.append(char)
    return "".join(out).strip()


class _Data:
    """Read-only cached access to the datamine tree."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self._json: dict[Path, object] = {}

        self._lang: dict[str, dict] = {}
        self._gui = None
        self._explosive = None

    # -- blocks -----------------------------------------------------------
    def ref_json(self, ref, prefix: str = ""):
        """Resolve a ``gameData/...blk`` reference to its exported ``.blkx``."""
        if not isinstance(ref, str) or not ref.strip():
            return None, None
        rel = prefix + ref if prefix and not ref.lower().startswith("gamedata/") else ref
        candidate = self.root / "aces.vromfs.bin_u" / rel.lower().replace(".blk", ".blkx")
        if not candidate.is_file():
            return None, candidate
        if candidate not in self._json:
            try:
                parsed = json.loads(candidate.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                parsed = None
            self._json[candidate] = parsed if isinstance(parsed, dict) else None
        return self._json[candidate], candidate

    def rel(self, path: Path | None) -> str | None:
        if path is None:
            return None
        try:
            return path.resolve().relative_to(self.root.resolve()).as_posix()
        except (ValueError, OSError):
            return path.name

    # -- shared tables ----------------------------------------------------
    @property
    def gui(self) -> dict:
        if self._gui is None:
            path = self.root / "aces.vromfs.bin_u/config/gui.blkx"
            try:
                self._gui = json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                self._gui = {}
        return self._gui

    @property
    def explosive_types(self) -> dict:
        if self._explosive is None:
            path = self.root / "aces.vromfs.bin_u/gamedata/damage_model/explosive.blkx"
            try:
                self._explosive = json.loads(path.read_text(encoding="utf-8-sig")).get("explosiveTypes", {})
            except (OSError, ValueError):
                self._explosive = {}
        return self._explosive

    def lang(self, table: str) -> dict[str, dict]:
        if table not in self._lang:
            rows: dict[str, dict] = {}
            path = self.root / "lang.vromfs.bin_u/lang" / (table + ".csv")
            if path.is_file():
                with path.open(encoding="utf-8-sig", newline="") as stream:
                    for row in csv.DictReader(stream, delimiter=";"):
                        key = row.get("<ID|readonly|noverify>")
                        if key:
                            rows[key.casefold()] = row
            self._lang[table] = rows
        return self._lang[table]

    def locid_exists(self, key: str, table: str | None = None) -> bool:
        tables = (table,) if table else ("units_weaponry", "units_modifications", "units", "menu")
        return any(str(key).casefold() in self.lang(name) for name in tables)

    def localize_key(self, key: str, table: str | None = None) -> str | None:
        """Game's own Chinese row (English fallback) for one key."""
        tables = (table,) if table else ("units_weaponry", "units_modifications", "units", "menu")
        for name in tables:
            row = self.lang(name).get(str(key).casefold())
            if not row:
                continue
            text = (row.get("<Chinese>") or row.get("<English>") or "")
            text = _strip_markup(text.replace("\u200b", "").replace("\ufeff", ""))
            if text:
                return text
        return None

    def icon_source_file(self, icon_type: str | None) -> str:
        """``#ui/gameuiskin#X`` or ``X`` -> exported PNG below atlases.vromfs.bin_u."""
        if not icon_type:
            return ""
        name = str(icon_type).split("#")[-1].replace(".avif", "").replace(".png", "")
        if not name:
            return ""
        for suffix in ("png", "avif"):
            path = self.root / "atlases.vromfs.bin_u/gameuiskin" / (name + "." + suffix)
            if path.is_file():
                return self.rel(path)
        return ""


def _localize(localize, candidates: list[str], fallback: str,
              data: _Data | None = None) -> tuple[str, str | None]:
    """Resolve a display name and report which locid produced it.

    1. the caller's resolver, which is the single source of truth;
    2. when it only echoes the code, the game's own CSV rows (so a stub resolver
       still yields real names);
    3. the code itself.
    """
    if not callable(localize):
        value = None
    else:
        try:
            value = localize(list(candidates), fallback)
        except Exception:  # noqa: BLE001 - a broken callback must not abort the build
            value = None
    if isinstance(value, str) and value.strip() and value.strip() != fallback:
        text = _strip_markup(value)
        key = next((c for c in candidates if data is not None and data.locid_exists(c)), candidates[0]
                   if candidates else None)
        return text, key
    if data is not None:
        for candidate in candidates:
            text = data.localize_key(candidate)
            if text:
                return text, candidate
    return fallback, None


# ---------------------------------------------------------------------------
# Munition helpers
# ---------------------------------------------------------------------------
def _munition_of(block: dict) -> tuple[str | None, dict | None]:
    for key in MUNITION_BLOCKS:
        value = block.get(key)
        if isinstance(value, dict):
            return key, value
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return key, value[0]
    return None, None


def _explosive(munition: dict, data: _Data) -> dict:
    ex_type = munition.get("explosiveType")
    ex_mass = _num(munition.get("explosiveMass"))
    result = {"explosive_type": ex_type, "explosive_mass_kg": ex_mass,
              "tnt_equivalent_kg": None, "tnt_strength_equivalent": None,
              "tnt_equivalent_source": "dmgmodel.nut:getTntEquivalentDmg = explosiveMass * explosiveTypes[type].strengthEquivalent",
              "tnt_equivalent_note": None}
    if not ex_type or ex_mass is None:
        result["tnt_equivalent_note"] = "block has no explosiveType/explosiveMass (game returns 0)"
        return result
    strength = _num(data.explosive_types.get(ex_type, {}).get("strengthEquivalent"))
    result["tnt_strength_equivalent"] = strength
    if ex_type == "tnt":
        # dmgmodel.nut returns 0 for "tnt" and prints nothing; show the raw mass
        # rather than an invented zero and note the deviation.
        result["tnt_equivalent_kg"] = _round(ex_mass)
        result["tnt_equivalent_note"] = ('explosiveType is "tnt": game getTntEquivalentDmg() returns 0 and prints no '
                                         "TNT text; value shown is the raw explosiveMass")
    elif strength is not None:
        result["tnt_equivalent_kg"] = _round(ex_mass * strength)
    else:
        result["tnt_equivalent_note"] = "explosiveTypes[%s].strengthEquivalent missing" % ex_type
    return result


def _guidance(munition: dict) -> dict:
    """Raw guidance fields, nothing derived."""
    return {
        "guidanceType": munition.get("guidanceType"),
        "guidance": munition.get("guidance"),
        "hasProximityFuse": munition.get("hasProximityFuse"),
        "proximityFuse": munition.get("proximityFuse"),
        "distanceFuse": munition.get("distanceFuse"),
        "isHasLaserChannel": munition.get("isHasLaserChannel"),
        "guided_present": munition.get("guidance") is not None or munition.get("guidanceType") is not None,
    }


class _Catalog:
    def __init__(self, data: _Data):
        self.data = data
        self.items: dict[str, dict] = {}
        self.order: list[str] = []
        self.notes: list[dict] = []

    def _stable_id(self, kind: str, munition: dict, weapon_file: Path | None) -> tuple[str, str]:
        name = munition.get("bulletName")
        if isinstance(name, str) and name.strip():
            base = _slug(name)
            return (base if base.startswith(kind + "_") else kind + "_" + base), "bulletName"
        # weaponsinfoexporter.nut:makeBulletFingerprint fallback
        caliber = _num(munition.get("caliber")) or 0
        mass = _num(munition.get("mass")) or 0
        speed = _num(munition.get("speed")) or 0
        partes = [_slug(munition.get("bulletType") or ""),
                  "%gmm" % round(caliber * 1000, 3),
                  "%gg" % round(mass * 1000, 3),
                  "%gmps" % round(speed, 3),
                  _slug(weapon_file.stem if weapon_file else "weapon")]
        return _slug(kind + "_" + "_".join(partes)), "fingerprint"

    def add(self, kind: str, munition: dict, weapon_file: Path | None,
            weapon_block: dict, localize) -> str:
        cid, basis = self._stable_id(kind, munition, weapon_file)
        if cid in self.items:
            self.items[cid]["used_by_blk"].append(self.data.rel(weapon_file))
            return cid
        stem = weapon_file.stem if weapon_file else cid
        # unitinfotype.nut:getWeaponParamsTable: iconType = blk.iconType,
        # mass/amountPerTier/guidanceType come from the munition block itself.
        icon_type = munition.get("iconType") or weapon_block.get("iconType")
        name_candidates = [stem + "/name/short", stem + "/name", "weapons/" + stem,
                           "weapons/" + stem + "/short", stem]
        name, name_key = _localize(localize, name_candidates, stem, self.data)
        if name_key is None:
            self.notes.append({"id": "munition_name_without_locid", "catalog_id": cid, "fallback": stem})
        caliber = _num(munition.get("caliber"))
        explosive = _explosive(munition, self.data)
        self.items[cid] = {
            "id": cid,
            "name": name,
            "name_locid": name_key,
            "mass_kg": _num(munition.get("mass")),
            "caliber_mm": _round(caliber * 1000, 2) if caliber is not None else None,
            "explosive_mass_kg": explosive["explosive_mass_kg"],
            "tnt_equivalent_kg": explosive["tnt_equivalent_kg"],
            "explosive_type": explosive["explosive_type"],
            "tnt_strength_equivalent": explosive["tnt_strength_equivalent"],
            "tnt_equivalent_source": explosive["tnt_equivalent_source"],
            "tnt_equivalent_note": explosive["tnt_equivalent_note"],
            "guidance": _guidance(munition),
            "source": self.data.rel(weapon_file),
            "source_block": "%s.%s" % (stem, kind),
            "icon_type": icon_type,
            "icon_source_file": self.data.icon_source_file(icon_type),
            "type": kind,
            "bullet_type": munition.get("bulletType"),
            "id_basis": basis,
            "used_by_blk": [],
        }
        if self.items[cid]["mass_kg"] is None:
            self.notes.append({"id": "munition_without_mass", "catalog_id": cid,
                               "source": self.data.rel(weapon_file),
                               "detail": "munition block has no 'mass'; dependent option/item mass becomes unknown"})
        self.order.append(cid)
        return cid


# ---------------------------------------------------------------------------
# Weapon mount resolution (recursive containers)
# ---------------------------------------------------------------------------
def _resolve_mount(data: _Data, catalog: _Catalog, ref, localize, *, depth=0,
                   containers=(), container_mass=0.0, count=1) -> dict:
    """Follow ``blk`` to end munitions.

    Count arithmetic is weaponrypresets.nut:getWeaponBlkParams:
    ``bulletsCount = bulletsCount * (weaponBlk?.bullets ?? 1)`` at every level and
    ``containersCount = weaponBlk?.bullets ?? 1``; containerMassKg accumulates
    ``(weaponBlk?.mass ?? 0) * containersCount``.  One Weapon[] entry carries
    amountPerTier 1 (unitinfotype.nut:422).
    """
    if depth > MAX_CONTAINER_DEPTH:
        return {"items": [], "container_mass_kg": container_mass,
                "branches": [{"blk": ref, "containers": list(containers),
                              "unresolved": "container nesting exceeds %d levels" % MAX_CONTAINER_DEPTH}],
                "has_container": bool(containers), "unresolved": ["container_depth"]}
    block, path = data.ref_json(ref)
    branch = {"blk": ref, "resolved": data.rel(path) if path else None,
              "containers": list(containers), "count": count, "depth": depth}
    if block is None:
        branch["unresolved"] = "referenced blk not exported in datamine"
        return {"items": [], "container_mass_kg": container_mass, "branches": [branch],
                "has_container": bool(containers), "unresolved": ["missing_blk"]}

    if block.get("container") and isinstance(block.get("blk"), str):
        inner_bullets = _num(block.get("bullets"))
        inner_bullets = int(inner_bullets) if inner_bullets is not None else 1
        inner_mass = _num(block.get("mass")) or 0.0
        branch.update({"container": True, "container_bullets": inner_bullets,
                       "container_mass_kg": inner_mass})
        # getWeaponBlkParams recurses with containerParams continuing from the
        # outer (already multiplied) values.
        inner = _resolve_mount(data, catalog, block.get("blk"), localize,
                               depth=depth + 1,
                               containers=containers + (path.stem if path else str(block.get("blk")),),
                               container_mass=container_mass + inner_mass * count,
                               count=count * inner_bullets)
        branch["unresolved"] = inner["unresolved"]
        return {"items": inner["items"], "container_mass_kg": inner["container_mass_kg"],
                "branches": [branch] + inner["branches"],
                "has_container": True, "unresolved": inner["unresolved"]}

    kind, munition = _munition_of(block)
    if kind is None:
        branch["unresolved"] = "no bullet/rocket/bomb/torpedo/payload sub-block"
        return {"items": [], "container_mass_kg": container_mass, "branches": [branch],
                "has_container": bool(containers), "unresolved": ["no_munition"]}
    cid = catalog.add(kind, munition, path, block, localize)
    branch["catalog_id"] = cid
    return {"items": [{"id": cid, "count": int(count)}],
            "container_mass_kg": container_mass, "branches": [branch],
            "has_container": bool(containers), "unresolved": []}


def _resolve_weapon(data, catalog, localize, weapon) -> dict:
    weapon = weapon if isinstance(weapon, dict) else {}
    resolved = _resolve_mount(data, catalog, weapon.get("blk"), localize)
    items: dict[str, int] = {}
    for item in resolved["items"]:
        items[item["id"]] = items.get(item["id"], 0) + item["count"]
    breakdown = []
    total = 0.0
    for cid, cnt in items.items():
        mass = catalog.items[cid]["mass_kg"]
        if mass is not None:
            breakdown.append({"part": "munition", "id": cid, "count": cnt, "unit_mass_kg": mass})
            total += mass * cnt
    if resolved["container_mass_kg"]:
        breakdown.append({"part": "container_mass_kg", "kg": resolved["container_mass_kg"]})
        total += resolved["container_mass_kg"]
    unknown = any(catalog.items[cid]["mass_kg"] is None for cid in items) or not items
    return {
        "catalog_id": next(iter(items)) if len(items) == 1 else None,
        "items": [{"id": cid, "count": cnt} for cid, cnt in items.items()],
        "mass_kg": None if unknown else _round(total),
        "mass_breakdown": breakdown,
        "mass_status": ("unknown" if unknown else
                        "known_container_only" if resolved["has_container"] and not breakdown else "known"),
        "requires_modification": weapon.get("reqModification"),
        "show_in_weapon_menu": weapon.get("showInWeaponMenu"),
        "trigger": weapon.get("trigger"),
        "machLimit": weapon.get("machLimit"),
        "separate": weapon.get("separate"),
        "external": weapon.get("external"),
        "blk": weapon.get("blk"),
        "emitter": weapon.get("emitter"),
        "bullets": weapon.get("bullets"),
        "branches": resolved["branches"],
        "unresolved": resolved["unresolved"],
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def build_loadouts(model, root, localize) -> dict:
    """Return the loadout structure of one aircraft model.

    ``model``    - parsed aircraft blk (unit record exported as JSON).
    ``root``     - datamine root (``War-Thunder-Datamine``), opened read-only.
    ``localize`` - ``(candidates: list[str], fallback: str) -> str``.
    """
    data = _Data(Path(root))
    catalog = _Catalog(data)
    model = model if isinstance(model, dict) else {}
    weapon_slots = model.get("WeaponSlots") if isinstance(model.get("WeaponSlots"), dict) else {}
    slot_records = [s for s in _as_list(weapon_slots.get("WeaponSlot")) if isinstance(s, dict)]
    tiers_count = weapon_slots.get("weaponsSlotCount")
    tiers_count = tiers_count if isinstance(tiers_count, int) and tiers_count > 0 else MIN_TIERS_COUNT

    def tier_of(record: dict) -> int:
        """weaponrypresets.nut: tier ?? (tiersCount - 1 - index); index required."""
        tier = record.get("tier")
        if isinstance(tier, int):
            return tier
        index = record.get("index")
        return tiers_count - 1 - index if isinstance(index, int) else tiers_count

    preset_by_index: dict[int, list[dict]] = {
        s["index"]: [p for p in _as_list(s.get("WeaponPreset")) if isinstance(p, dict)]
        for s in slot_records if isinstance(s.get("index"), int)
    }

    # ---------------------------------------------------------------- slots
    slots_all = []
    for position, record in enumerate(slot_records, start=1):
        index = record.get("index")
        tier = record.get("tier")
        order = _num(record.get("order"))
        excluded_reason = "WeaponSlot without a numeric index"
        if not isinstance(index, int):
            index = None
        options = []
        for preset in _as_list(record.get("WeaponPreset")):
            if not isinstance(preset, dict):
                continue
            weapons = [_resolve_weapon(data, catalog, localize, w)
                       for w in _as_list(preset.get("Weapon")) if isinstance(w, dict)]
            items: dict[str, int] = {}
            for w in weapons:
                for item in w["items"]:
                    items[item["id"]] = items.get(item["id"], 0) + item["count"]
            solids = [w["mass_kg"] for w in weapons if w["mass_kg"] is not None]
            mass_known = bool(weapons) and all(w["mass_kg"] is not None for w in weapons)
            dependencies = [{"slot": d.get("slot"), "preset": d.get("preset"), "raw": d}
                            for d in _as_list(preset.get("DependentWeaponPreset")) if isinstance(d, dict)]
            blocking = [{"slot": b.get("slot"), "preset": b.get("preset"), "raw": b}
                        for b in _as_list(preset.get("BannedWeaponPreset", preset.get("BlockedWeaponPreset"))) if isinstance(b, dict)]
            # weaponryinfo.nut:723 - iconType: preset first, else first resolvable munition
            icon_type = preset.get("iconType")
            if not icon_type:
                for w in weapons:
                    icon_type = next((catalog.items[i["id"]]["icon_type"] for i in w["items"]
                                      if catalog.items[i["id"]]["icon_type"]), None)
                    if icon_type:
                        break
            if isinstance(icon_type, list):
                icon_type = next((v for v in icon_type if isinstance(v, str)), None)
            name = preset.get("name")
            options.append({
                "id": name,
                "name": _localize(localize, [str(name)], str(name), data)[0],
                "requires_modification": preset.get("reqModification"),
                "dependencies": dependencies,
                "blocking": blocking,
                "items": [{"id": cid, "count": cnt} for cid, cnt in items.items()],
                "mass_kg": _round(sum(solids)) if mass_known else None,
                "mass_status": ("unknown" if not mass_known else
                                "known_container_only" if any(w["mass_status"] == "known_container_only"
                                                              for w in weapons) else "known"),
                "icon_type": icon_type,
                "icon_path": TIER_ICON_PATH + icon_type if icon_type else None,
                "icon_source_file": data.icon_source_file(icon_type),
                "show_in_weapon_menu": bool(preset.get("showInWeaponMenu")),
                "has_targeting_pod": bool(preset.get("hasTargetingPod")),
                "append_prefix": preset.get("appendPrefix"),
                "weapons": weapons,
            })
        slots_all.append({
            "index": index,
            "tier": tier,
            "tier_used": tier_of(record),
            "order": order,
            "order_position": position,
            "not_use_for_disbalance": bool(record.get("notUseforDisbalanceCalculation")),
            "options": options,
        })

    # ---------------------------------------------- exclusions and ordering
    common = model.get("commonWeapons") if isinstance(model.get("commonWeapons"), dict) else {}
    common_slots = sorted({w.get("slot") for w in _as_list(common.get("Weapon"))
                           if isinstance(w, dict) and isinstance(w.get("slot"), int)})
    excluded, kept = [], []
    for slot in slots_all:
        if slot["index"] is None:
            slot["excluded_reason"] = excluded_reason
            excluded.append(slot)
        elif slot["order"] is None and slot["index"] in common_slots:
            slot["excluded_reason"] = "fixed commonWeapons mount (not a selectable pylon)"
            excluded.append(slot)
        elif not slot["options"]:
            slot["excluded_reason"] = "WeaponSlot has no WeaponPreset"
            excluded.append(slot)
        else:
            slot["excluded_reason"] = None
            kept.append(slot)
    kept.sort(key=lambda s: (-s["tier_used"], s["order_position"]))
    mirror_of = {s["index"]: kept[len(kept) - 1 - i]["index"] for i, s in enumerate(kept)}
    for display, slot in enumerate(kept, start=1):
        slot["display_index"] = display
        slot["side"] = ("left" if int(round(slot["order"])) % 2 else "right") if slot["order"] is not None else None
        slot["mirror_slot_index"] = mirror_of[slot["index"]]

    # ------------------------------------------------------------- presets
    preset_specs = []
    if isinstance(model.get("weapon_presets"), dict):
        preset_specs = [p for p in _as_list(model["weapon_presets"].get("preset")) if isinstance(p, dict)]
    presets = []
    for spec in preset_specs:
        block, path = data.ref_json(spec.get("blk"))
        assignments, problems = [], []
        for assignment in _as_list((block or {}).get("Weapon")):
            if not isinstance(assignment, dict):
                continue
            slot_index, option_id = assignment.get("slot"), assignment.get("preset")
            candidates = preset_by_index.get(slot_index, []) if isinstance(slot_index, int) else []
            option = next((o for o in candidates if o.get("name") == option_id), None)
            kept_slot = next((s for s in kept if s["index"] == slot_index), None)
            resolved_option = next((o for o in (kept_slot or {}).get("options", []) if o.get("id") == option_id), None)
            if option is None:
                problems.append({"slot": slot_index, "preset": option_id,
                                 "problem": "WeaponSlot / WeaponPreset not found"})
                assignments.append({"slot": slot_index, "preset": option_id, "found": False})
                continue
            assignments.append({
                "slot": slot_index,
                "preset": option_id,
                "found": True,
                "display_index": kept_slot["display_index"] if kept_slot else None,
                "tier_used": kept_slot["tier_used"] if kept_slot else
                (tiers_count - 1 - slot_index if isinstance(slot_index, int) else None),
                "items": resolved_option["items"] if resolved_option else [],
                "mass_kg": resolved_option["mass_kg"] if resolved_option else None,
                "requires_modification": option.get("reqModification"),
            })
        name = spec.get("name")
        presets.append({
            "id": name,
            "name": _localize(localize, [str(name)], str(name), data)[0],
            "preset_type": (spec.get("weaponConfig") or {}).get("presetType"),
            "is_default": "default" in str(name),
            "assignments": assignments,
            "problems": problems,
            "source": data.rel(path) or spec.get("blk"),
        })

    # -------------------------------------------------------------- matrix
    matrix: dict[str, dict] = {cid: {} for cid in catalog.order}
    for slot in kept:
        view = "slot[%d]" % slot["index"]
        for option in slot["options"]:
            for item in option["items"]:
                matrix[item["id"]].setdefault(view, set()).add(item["count"])
    rows = []
    for cid in catalog.order:
        counters = matrix[cid]
        possible = sorted({c for values in counters.values() for c in values})
        by_index = {int(v[5:-1]): counters.get(v) for v in counters}
        rows.append({
            "catalog_id": cid,
            "name": catalog.items[cid]["name"],
            "type": catalog.items[cid]["type"],
            "icon_source_file": catalog.items[cid]["icon_source_file"],
            "counts_by_slot": {"slot[%d]" % s["index"]: (sorted(by_index[s["index"]])
                                                        if s["index"] in by_index else None)
                               for s in kept},
            "visual_left_to_right": [(sorted(by_index[s["index"]]) if s["index"] in by_index else None)
                                     for s in kept],
            "mountable_slots": len(counters),
            "count_set": possible,
            "min_count": min(possible) if possible else None,
            "max_count": max(possible) if possible else None,
        })

    # ------------------------------------------------ side / parity check
    # weaponrypresetsparams.nut:getPresetWeightRestrictionText centreIdx = count/2:
    # columns [0, centreIdx) are the left console, [centreIdx, n) the right one.
    side_pairs = []
    left = [s for s in kept if s["side"] == "left"]
    right = [s for s in kept if s["side"] == "right"]
    centre_limit = len(kept) // 2
    centre_by_game = [s["index"] for s in kept if (s["display_index"] - 1) >= centre_limit]
    centre_by_flag = [s["index"] for s in kept
                      if next((r for r in slot_records if r.get("index") == s["index"]), {})
                      .get("notUseforDisbalanceCalculation")]
    left_visual = [s["index"] for s in kept[:centre_limit]]
    parity_ok = len(left) == len(right)
    for position in range(min(len(left), len(right))):
        a = left[-1 - position]   # left column, innermost first (kept order)
        b = right[position]       # right column, outermost first
        side_pairs.append({"left": {"slot": a["index"], "display_index": a["display_index"], "order": a["order"]},
                           "right": {"slot": b["index"], "display_index": b["display_index"], "order": b["order"]}})
        if a["display_index"] >= b["display_index"] or a["index"] not in left_visual:
            parity_ok = False

    limits = {
        "maxloadMass": weapon_slots.get("maxloadMass"),
        "maxloadMassLeftConsoles": weapon_slots.get("maxloadMassLeftConsoles"),
        "maxloadMassRightConsoles": weapon_slots.get("maxloadMassRightConsoles"),
        "maxDisbalance": weapon_slots.get("maxDisbalance"),
        "weaponsSlotCount": weapon_slots.get("weaponsSlotCount"),
        "tiers_count_used": tiers_count,
        "unit": "kg",
        "source": "model.WeaponSlots (raw)",
        "apply_rule": "weaponrypresetsparams.nut:getPresetWeightRestrictionText",
    }

    known_rules = [
        {"id": "slots.common_weapons_fixed",
         "rule": "a WeaponSlot referenced by commonWeapons.Weapon[].slot without an order/tier is the fixed mount and is not a selectable pylon",
         "source": "weaponrypresets.nut:getWeaponsByTypes(isCommon) / commonWeapons.Weapon.slot",
         "applied_to": [s["index"] for s in excluded if s["index"] in common_slots]},
        {"id": "slots.no_preset",
         "rule": "a WeaponSlot without any WeaponPreset has no replaceable weapon and is excluded from the display",
         "source": "observed WeaponSlots shape",
         "applied_to": [s["index"] for s in excluded if s["index"] not in common_slots]},
        {"id": "slots.tier_order",
         "rule": "slots sorted by tier descending; this is also the visual left-to-right column order",
         "source": "weaponrypresetsparams.nut:getIndexedTiers maps tierId around middleTierIdx",
         "tiers_in_display_order": [s["tier_used"] for s in kept]},
        {"id": "slots.tier_fallback",
         "rule": "missing WeaponSlot.tier is tiersCount-1-index; weaponsSlotCount falls back to MIN_TIERS_COUNT=13",
         "source": "weaponrypresets.nut:addSlotWeaponsFromPreset", "tiers_count": tiers_count},
        {"id": "slots.side_parity",
         "rule": "order parity: odd -> left column, even -> right column; mirror columns are order_position pairs (order_left + order_right == kept+1) and must sit on opposite sides of display index",
         "source": "WeaponSlot.order + weaponrypresetsparams.nut:getIndexedTiers pairing",
         "pairs": side_pairs, "parity_consistent": parity_ok,
         "attempted_pairs": [{"left": p["left"]["slot"], "right": p["right"]["slot"],
                              "orders": [p["left"]["order"], p["right"]["order"]]} for p in side_pairs]},
        {"id": "slots.index_kept",
         "rule": "the game WeaponSlot.index and the display index are both kept (index is what presets reference)",
         "source": "weapon_presets/*.blk: Weapon[].slot"},
        {"id": "option.unit_count",
         "rule": "one Weapon[] entry = amountPerTier 1; each container contributes bullets x outer bullets; multi-entry presets sum their entries",
         "source": "weaponrypresets.nut:getWeaponBlkParams; unitinfotype.nut:422"},
        {"id": "option.mass",
         "rule": "mass_kg = sum(munition.mass x count) + sum(container.mass x count) over all container levels",
         "source": "weaponrypresets.nut:containerMassKg; weaponryinfo.nut:670 additionalMassKg"},
        {"id": "option.dependencies",
         "rule": "DependentWeaponPreset / BlockedWeaponPreset copied verbatim per option (slot, preset)",
         "source": "weaponrypresets.nut:addSlotWeaponsFromPreset"},
        {"id": "option.icon",
         "rule": "icon_type = preset.iconType, else first munition/weapon iconType; icon_path = #ui/gameuiskin# + icon_type",
         "source": "weaponrypresetsparams.nut:getTierIcon; weaponryinfo.nut:723"},
        {"id": "catalog.id",
         "rule": "stable id = bulletName (after slug), else bulletType_caliber_mass_speed fingerprint",
         "source": "weaponsinfoexporter.nut:makeBulletFingerprint; getProjectileId"},
        {"id": "catalog.guidance",
         "rule": "guidanceType and guidance are copied raw from the munition block",
         "source": "unitinfotype.nut:getWeaponParamsTable"},
        {"id": "catalog.tnt",
         "rule": "tnt_equivalent_kg = explosiveMass * explosiveTypes[type].strengthEquivalent",
         "source": "dmgmodel.nut:getTntEquivalentDmg"},
        {"id": "restrictions",
         "rule": "notUseforDisbalanceCalculation slots are the centre column; the remaining columns below centreIdx=count/2 sum to left console mass, the rest to the right console; none of the four limits is evaluated here",
         "source": "weaponrypresetsparams.nut:getPresetWeightRestrictionText",
         "centre_by_flag": centre_by_flag, "right_console_by_index": centre_by_game},
        {"id": "disbalance_centre_inconsistency",
         "rule": "the engine places the centre from the notUseforDisbalanceCalculation flag while getPresetWeightRestrictionText splits at count/2; both lists are reported so a mismatch is visible",
         "source": "weaponrypresetsparams.nut:712-747"},
    ]
    unknown_rules = [
        {"id": "mass_limits_not_evaluated",
         "detail": "limits are exposed raw; preset pass/fail needs per-column tier masses and addWeaponry mass, not evaluated here"},
        {"id": "pylon_hardpoint_mass",
         "detail": "pylon/list mass is not exported; only container.mass and munition.mass are summed, so options carried on a rack without a container block are marked known_container_only"},
        {"id": "nested_container_mass",
         "detail": "container mass is accumulated for every container level that declares 'mass' (outer x containersCount); unobserved nested chains must be verified per model"},
        {"id": "per_tier_amount_override",
         "detail": "Weapon.tier[].amountPerTier and weapon-block amountPerTier are not applied; counts come from the exported bullets/container chain only (weaponrypresetsparams.nut:getPredefinedTiers is the in-game override path)"},
        {"id": "dependent_presets_not_synthesised",
         "detail": "DependentWeaponPreset auto-fill (e.g. pod slot pairing) is reported, not expanded into combined numbers"},
        {"id": "modification_gating",
         "detail": "reqModification is reported verbatim; whether the player owns the modification is not evaluated"},
        {"id": "gun_ammunition",
         "detail": "fixed cannon ammunition (trigger cannon/other commonWeapons mounts) is out of scope of the loadout matrix"},
        {"id": "custom_presets",
         "detail": "player custom presets are not part of the datamine"},
    ]

    result = {
        "schema": 2,
        "kind": "aircraft_loadouts",
        "model": model.get("model"),
        "slots": kept,
        "excluded_slots": [{"index": s["index"], "tier": s["tier"], "order": s["order"],
                            "reason": s["excluded_reason"]} for s in excluded],
        "presets": presets,
        "limits": limits,
        "catalog": [catalog.items[cid] for cid in catalog.order],
        "matrix_rows": rows,
        "known_rules": known_rules,
        "unknown_rules": unknown_rules + catalog.notes,
    }
    return result


# ---------------------------------------------------------------------------
# CLI: thin wrapper that writes only the requested output file
# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build an aircraft loadout matrix JSON.")
    parser.add_argument("--model", required=True, help="flight model code, e.g. mig_35")
    parser.add_argument("--root", default=None, help="datamine root (default: <repo>/../War-Thunder-Datamine)")
    parser.add_argument("--out", required=True, help="output JSON path")
    args = parser.parse_args(argv)
    root = Path(args.root) if args.root else Path(__file__).resolve().parents[1].parent / "War-Thunder-Datamine"
    model_path = root / "aces.vromfs.bin_u/gamedata/flightmodels" / (args.model + ".blkx")
    if not model_path.is_file():
        raise SystemExit("flight model not found: " + str(model_path))
    model = json.loads(model_path.read_text(encoding="utf-8-sig"))
    data = _Data(root)

    def localize(candidates, fallback):
        for candidate in candidates:
            text = data.localize_key(candidate)
            if text:
                return text
        return fallback

    result = build_loadouts(model, root, localize)
    result["source"] = data.rel(model_path)
    result["datamine_root"] = str(root.resolve())
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                   encoding="utf-8")
    print("wrote %s: %d slots, %d presets, %d catalog, %d matrix rows" % (
        out, len(result["slots"]), len(result["presets"]), len(result["catalog"]),
        len(result["matrix_rows"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
