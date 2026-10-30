"""Read-only economy conversion using the game stat-export formulas.

build_economy returns (section, audit). Repair uses repairCost * avgRepairMul *
(1 + sum(repairCostCoef)), rather than the precomputed repairCostFullUpgraded.
Reward multipliers use Unit.getWpRewardMulList display rounding. Modification
cost is the total cost of all visible research-tier modifications, independent
of a particular player's inventory. All inputs stay local and read-only."""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any
MODES = (("ab", "Arcade"), ("rb", "Historical"), ("sb", "Simulation"))


def load_blk(path: Path) -> dict:
    """Read a ``*.blkx`` JSON export (UTF-8, optional BOM)."""
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def read_version(root: Path) -> str | None:
    path = Path(root) / "version"
    return path.read_text(encoding="utf-8-sig").strip() if path.is_file() else None


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def round_by_value(value: float, step: float) -> float:
    """``stdMath.round_by_value(value, step)``: nearest multiple, halves away from zero."""
    if not step:
        return value
    quotient = Decimal(str(value)) / Decimal(str(step))
    return float(quotient.quantize(Decimal("1"), rounding=ROUND_HALF_UP) * Decimal(str(step)))


def percent_of(value: float) -> int:
    """``(value * 100 + 0.5).tointeger()``: Squirrel truncates towards zero."""
    return int(Decimal(str(value * 100 + 0.5)).to_integral_value(rounding="ROUND_DOWN"))


def mode_row(label: str, values: dict[str, Any], source: str, unit: str | None = None) -> dict:
    row: dict[str, Any] = {"label": label, "value": values, "source": source}
    if unit:
        row["unit"] = unit
    if all(v is None for v in values.values()):
        row["status"] = "uncomputed"
    return row


def simple_row(label: str, value: Any, source: str, unit: str | None = None) -> dict:
    row: dict[str, Any] = {"label": label, "value": value, "source": source}
    if unit:
        row["unit"] = unit
    if value is None:
        row["status"] = "uncomputed"
    return row


def repair_coefficients(entry: dict) -> tuple[float, list[dict]]:
    """``(1 + sum(repairCostCoef), terms)`` over every wpcost modification entry."""
    terms: list[dict] = []
    for mod_id, mod in (entry.get("modifications") or {}).items():
        if not isinstance(mod, dict):
            continue
        coef = mod.get("repairCostCoef")
        if _number(coef):
            terms.append({"modification": mod_id, "tier": mod.get("tier"), "coef": float(coef)})
    return 1.0 + sum(t["coef"] for t in terms), terms


def repair_table(entry: dict, avg_repair_mul: float) -> dict[str, Any]:
    multiplier, terms = repair_coefficients(entry)
    table: dict[str, Any] = {"costMultiplier": multiplier, "avgRepairMul": avg_repair_mul,
                             "coefficients": terms, "modes": {}}
    for mode, suffix in MODES:
        base = entry.get("repairCost" + suffix)
        stored = entry.get("repairCostFullUpgraded" + suffix)
        derived = None
        if _number(base):
            value = float(base) * avg_repair_mul * multiplier
            derived = int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        table["modes"][mode] = {"basic": base, "derived": derived, "stored_full": stored,
                                "stored_minus_derived": (stored - derived)
                                if _number(stored) and derived is not None else None}
    return table


def is_unit_special(entry: dict) -> bool:
    """``ranks_common_shared.nut: isUnitSpecial``."""
    cost_gold = entry.get("costGold")
    return (_number(cost_gold) and cost_gold > 0) or bool(entry.get("premPackAir"))


def reward_table(entry: dict, warpoints: dict, ranks: dict) -> dict[str, Any]:
    special = is_unit_special(entry)
    visual = warpoints.get("rewardMulVisual") or {}
    prem_part = float(visual.get("premRewardMulVisualPart", 0.5) or 0.0) if special else 0.0
    silver: dict[str, Any] = {}
    silver_raw: dict[str, Any] = {}
    for mode, suffix in MODES:
        raw = entry.get("rewardMul" + suffix)
        if not _number(raw):
            silver[mode] = None
            silver_raw[mode] = None
            continue
        mul = float(raw) * float(visual.get("rewardMulVisual" + suffix, 1.0) or 1.0)
        wp_mul = round_by_value(mul * (1.0 - prem_part), 0.05 if special else 0.1)
        prem_mul = round_by_value(1.0 / (1.0 - prem_part), 0.1) if 0.0 < prem_part < 1.0 else 1.0
        silver[mode] = percent_of(wp_mul * prem_mul)
        silver_raw[mode] = {"rewardMul": raw, "visualMul": visual.get("rewardMulVisual" + suffix, 1.0),
                            "mul": mul, "wpMul": wp_mul, "premMul": prem_mul}
    talisman_mul = float(ranks.get("goldPlaneExpMul", 1.0) or 1.0) if special else 1.0
    exp_mul = entry.get("expMul")
    research = percent_of(float(exp_mul) * talisman_mul) if _number(exp_mul) else None
    return {"isSpecial": special, "premPart": prem_part, "talismanMul": talisman_mul,
            "silver": silver, "silver_terms": silver_raw,
            "research": research,
            "expMul": exp_mul}


def silver_rows(rewards: dict) -> dict[str, Any]:
    """Official page shows AB / RB / SB for the SL reward."""
    return dict(rewards["silver"])


def research_rows(rewards: dict) -> dict[str, Any]:
    """``exp_bonus`` is mode independent; SB repeats it (see module docstring)."""
    value = rewards["research"]
    return {"ab": value, "rb": value, "sb": value}


@dataclass
class EconomySource:
    """Everything ``build_economy`` may read; all of it is read-only input."""

    root: Path
    warpoints: dict = field(default_factory=dict)
    ranks: dict = field(default_factory=dict)
    official: Path | None = None
    talisman_opt_in: bool = False

    @classmethod
    def from_root(cls, root: Path, *, official: Path | None = None,
                  talisman_opt_in: bool = False) -> "EconomySource":
        root = Path(root)
        config = root / "char.vromfs.bin_u" / "config"
        return cls(root=root,
                   warpoints=load_blk(config / "warpoints.blkx"),
                   ranks=load_blk(config / "rank.blkx"),
                   official=official,
                   talisman_opt_in=talisman_opt_in)

    @property
    def version(self) -> str | None:
        return read_version(self.root)


def talisman_cost(entry: dict, source: EconomySource) -> tuple[int | None, str]:
    prem = (entry.get("modifications") or {}).get("premExpMul") or {}
    return prem.get("costGold"), "wpcost.modifications.premExpMul.costGold; bulletsinfo.nut:getUniqModificationText premExpMul"


def modification_costs(entry, definitions):
    items=[]
    for code,mod in (entry.get('modifications') or {}).items():
        if not isinstance(mod,dict) or not isinstance(mod.get('tier'),int) or mod['tier']<=0: continue
        definition={**definitions.get(code,{}),**mod}
        if definition.get('isHidden'): continue
        items.append({'id':code,'rp':mod.get('reqExp') or 0,'sl':mod.get('value') or 0})
    return {'flat_sum':{'rp':sum(i['rp'] for i in items),'sl':sum(i['sl'] for i in items)},'items':items}


def build_economy(entry: dict, definitions: dict, model: dict, source: EconomySource) -> tuple[dict, dict]:
    """Return ``(section, audit)`` for one vehicle.

    ``entry`` is ``wpcost.blkx[code]``, ``definitions`` is
    ``modifications.blkx["modifications"]``.  ``model`` is accepted for signature
    parity with the vehicle builder; the economy does not read the model block.
    """
    if not isinstance(entry, dict):
        raise TypeError("entry 必须是 wpcost.blkx 中的载具字典")
    repair = repair_table(entry, float((source.warpoints or {}).get("avgRepairMul", 1.0) or 1.0))
    rewards = reward_table(entry, source.warpoints or {}, source.ranks or {})
    mods = modification_costs(entry, definitions or {})
    talisman, talisman_note = talisman_cost(entry, source)

    def repair_text(mode):
        item = repair['modes'][mode]
        return f"{item['basic']:,} → {item['derived']:,}" if item['basic'] is not None and item['derived'] is not None else None
    rows = [
        *[simple_row(label + '维修费用（基础 → 完全体）', repair_text(mode),
          'unitinfotype.nut:full_repair_cost; repairCost × avgRepairMul × (1 + Σ repairCostCoef)', '银狮')
          for mode,label in [('ab','街机'),('rb','历史'),('sb','全真')]],
        simple_row('乘员组培训', entry.get('trainCost'), 'wpcost.trainCost', '银狮'),
        simple_row('专家', entry.get('train2Cost'), 'wpcost.train2Cost', '银狮'),
        simple_row('王牌', entry.get('train3Cost_gold'), 'wpcost.train3Cost_gold', '金鹰'),
        simple_row('王牌研发', entry.get('train3Cost_exp'), 'wpcost.train3Cost_exp', '研发点'),
        simple_row('银狮收益系数（街机 / 历史 / 全真）', ' / '.join(str(rewards['silver'][m]) if rewards['silver'][m] is not None else '—' for m,_ in MODES), 'unit.nut:getWpRewardMulList; round_by_value(..., 0.1)', '%'),
        simple_row('研发收益系数', rewards['research'], 'unitinfotype.nut:exp_bonus', '%'),
        simple_row('改装总费（研发点）', mods['flat_sum']['rp'], 'Σ visible tier>0 modification.reqExp', '研发点'),
        simple_row('改装总费（银狮）', mods['flat_sum']['sl'], 'Σ visible tier>0 modification.value', '银狮'),
        simple_row('护身符费用', talisman, talisman_note, '金鹰'),
    ]
    section = {"id": "economy", "title": "经济", "rows": rows}

    audit = {
        "version": source.version,
        "inputs": {
            "avgRepairMul": (source.warpoints or {}).get("avgRepairMul"),
            "premRewardMulVisualPart": ((source.warpoints or {}).get("rewardMulVisual") or {}).get("premRewardMulVisualPart"),
            "goldPlaneExpMul": (source.ranks or {}).get("goldPlaneExpMul"),
            "costGold": entry.get("costGold"),
            "isUnitSpecial": rewards["isSpecial"],
            "rank": entry.get("rank"),
        },
        "repair": repair,
        "rewards": rewards,
        "modifications": mods,
        "talisman": {"value": talisman, "note": talisman_note},
    }
    return section, audit
