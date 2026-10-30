"""Parse saved official vehicle pages (War Thunder Wiki MHTML) with the standard library only.

The official vehicle page (``https://wiki.warthunder.com/unit/<code>``) is a rendered
HTML document.  This module builds a tiny DOM from it with :class:`html.parser.HTMLParser`
and extracts the structures we care about into a generic, source-faithful shape:

* ``specification_blocks`` -- one entry per ``.block`` inside ``#specification``:
  the block header (e.g. "Flight performance"), the feature chips shown above the
  characteristic rows, and the rows themselves.
* ``belts`` -- every ``table.game-unit_belt-list`` row: belt name, filling, the
  ordered bullet-icon layers and the armour-penetration values at each distance.
* ``slot_headers`` / ``loadout_rows`` -- ``table.game-unit_slot-list``: the column
  headers and, per row, the store name, single-round weight, per-slot quantities
  and icons, plus the parameters carried in the row's ``data-feature-popover``.

References are snapshotted input.  Nothing here invents values: a field that the
page does not contain stays ``None`` or an empty list, and every text value keeps
the wording found in the page (whitespace collapsed, entities decoded).

This module never writes to the Wiki and never touches the game datamine.
"""
from __future__ import annotations

import argparse
import email
import hashlib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterator

from paths import ROOT

# Elements that never carry children we care about, so the DOM builder can skip
# them instead of tracking a closing tag.
VOID_TAGS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
})
# Elements whose text content is not part of the rendered page text.
NON_TEXT_TAGS = frozenset({"script", "style", "template", "noscript"})
# Elements that do not introduce a line break when flattening text.
INLINE_TAGS = frozenset({
    "a", "abbr", "b", "bdi", "bdo", "br", "cite", "code", "data", "dfn", "em",
    "i", "img", "kbd", "mark", "q", "s", "samp", "small", "span", "strong",
    "sub", "sup", "time", "u", "var", "wbr",
})

# "show-char-rb-mod-ref" / "show-char-ab-mod-basic" drive the stock/upgraded switch.
CHAR_CLASS_RE = re.compile(r"^show-char-(ab|rb|sb)-mod-(ref|basic)$")
# Same switch without the ``show-char-`` prefix, used by some generated tables.
CHAR_CLASS_SHORT_RE = re.compile(r"^char-(ab|rb|sb)-mod-(ref|basic)$")
DISTANCE_RE = re.compile(r"^\s*([0-9][0-9,.]*)\s*m\s*$")
LEADING_NUMBER_RE = re.compile(r"[-+]?[0-9][0-9,.]*")


class Node:
    """Minimal DOM node: tag name, attributes, children, parent."""

    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag: str, attrs: dict[str, str], parent: "Node | None" = None) -> None:
        self.tag = tag
        self.attrs = attrs
        self.children: list["Node | str"] = []
        self.parent = parent

    # -- attribute helpers -------------------------------------------------
    @property
    def classes(self) -> tuple[str, ...]:
        return tuple(self.attrs.get("class", "").split())

    def has_class(self, name: str) -> bool:
        return name in self.classes

    def get(self, name: str, default: str = "") -> str:
        return self.attrs.get(name, default)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{self.tag} {self.attrs.get('class', '')!r}>"

    # -- traversal ---------------------------------------------------------
    def iter(self) -> Iterator["Node"]:
        """Depth-first walk over this node and every element below it."""
        stack: list["Node"] = [self]
        while stack:
            current = stack.pop()
            yield current
            stack.extend(reversed([c for c in current.children if isinstance(c, Node)]))

    def find_all(self, tag: str | None = None, *, cls: str | None = None) -> list["Node"]:
        return [n for n in self.iter()
                if (tag is None or n.tag == tag) and (cls is None or n.has_class(cls))]

    def first(self, tag: str | None = None, *, cls: str | None = None) -> "Node | None":
        for node in self.iter():
            if (tag is None or node.tag == tag) and (cls is None or node.has_class(cls)):
                return node
        return None

    def ancestors(self) -> Iterator["Node"]:
        node = self.parent
        while node is not None:
            yield node
            node = node.parent


class DOMBuilder(HTMLParser):
    """Build a :class:`Node` tree while tolerating unclosed tags."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("#document", {})
        self._stack: list[Node] = [self.root]
        self._skip_depth = 0

    @property
    def _current(self) -> Node:
        return self._stack[-1]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag, {k: ("" if v is None else v) for k, v in attrs}, self._current)
        self._current.children.append(node)
        if tag in VOID_TAGS:
            return
        if tag in NON_TEXT_TAGS:
            self._skip_depth += 1
        self._stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag, {k: ("" if v is None else v) for k, v in attrs}, self._current)
        self._current.children.append(node)

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID_TAGS:
            return
        # Pop up to the matching open element; ignore stray closers.
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == tag:
                for closed in self._stack[index:]:
                    if closed.tag in NON_TEXT_TAGS:
                        self._skip_depth = max(0, self._skip_depth - 1)
                del self._stack[index:]
                return

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if data:
            self._current.children.append(data)


def parse_dom(raw_html: str) -> Node:
    """Return the document root for ``raw_html``."""
    builder = DOMBuilder()
    builder.feed(raw_html)
    builder.close()
    return builder.root


# -----------------------------------------------------------------------------
# text helpers
# -----------------------------------------------------------------------------
def _normalize(text: str) -> str:
    """Collapse whitespace, keeping non-breaking spaces as plain spaces."""
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def text_of(node: Node | None) -> str:
    """Flatten a node's rendered text with whitespace collapsed."""
    if node is None:
        return ""

    def walk(current: Node, parts: list[str]) -> None:
        for child in current.children:
            if isinstance(child, str):
                parts.append(child)
            elif child.tag in NON_TEXT_TAGS:
                continue
            elif child.tag == "br":
                parts.append(" ")
            else:
                walk(child, parts)
                if child.tag not in INLINE_TAGS:
                    parts.append(" ")

    parts: list[str] = []
    walk(node, parts)
    return _normalize("".join(parts))


def text_excluding(node: Node, exclude: frozenset[str]) -> str:
    """Flatten text while skipping descendants whose classes are in ``exclude``."""
    parts: list[str] = []

    def walk(current: Node) -> None:
        for child in current.children:
            if isinstance(child, str):
                parts.append(child)
            elif child.tag in NON_TEXT_TAGS:
                continue
            elif exclude.intersection(child.classes):
                continue
            elif child.tag == "br":
                parts.append(" ")
            else:
                walk(child)
                if child.tag not in INLINE_TAGS:
                    parts.append(" ")

    walk(node)
    return _normalize("".join(parts))


def to_number(text: str) -> int | float | None:
    """Convert the leading numeric part of ``text``; ``None`` when there is none."""
    match = LEADING_NUMBER_RE.search(text or "")
    if not match:
        return None
    raw = match.group(0).replace(",", "")
    try:
        value = float(raw)
    except ValueError:
        return None
    return int(value) if value.is_integer() else value


def split_value(text: str) -> dict[str, Any]:
    """Split a characteristic value such as ``2,286 km/h`` into number and unit."""
    flat = _normalize(text)
    number = to_number(flat)
    unit = ""
    if number is not None:
        match = re.match(r"^\s*[-+]?[0-9][0-9,.]*\s*(.*)$", flat)
        unit = _normalize(match.group(1)) if match else ""
    return {"text": flat, "value": number, "unit": unit}


def _clean_url(url: str) -> str:
    return url.strip()


# -----------------------------------------------------------------------------
# specification
# -----------------------------------------------------------------------------
def _split_class_toggle(node: Node) -> dict[str, dict[str, Any]] | None:
    """Handle the compact ``<span class="show-char-rb-mod-ref">2,286</span>`` run.

    The official page writes all four states as sibling spans with no separator,
    so the enclosing value span must be walked in document order.
    """
    states: dict[str, dict[str, Any]] = {}
    seen = False
    for span in node.find_all("span"):
        for name in span.classes:
            match = CHAR_CLASS_RE.match(name)
            if not match:
                continue
            seen = True
            mode = match.group(1)
            state = "stock" if match.group(2) == "basic" else "upgraded"
            states.setdefault(mode, {})[state] = to_number(text_of(span))
            break
    if not seen:
        return None
    return {mode: {s: states[mode].get(s) for s in ("stock", "upgraded")}
            for mode in ("ab", "rb") if mode in states}


def _mode_unit(raw_value: str) -> str:
    """Trailing unit text after the last numeric token, e.g. ``km/h`` or ``t``."""
    match = re.search(r"[-+]?[0-9][0-9,.]*\s*(.*)$", raw_value or "")
    return _normalize(match.group(1)) if match else ""


def _row_from_chars_line(line: Node) -> dict[str, Any] | None:
    """Turn one ``.game-unit_chars-line`` into a labelled row."""
    header_node = line.first(cls="game-unit_chars-header")
    if header_node is None:
        return None
    label = text_of(header_node)
    info_node = line.first(cls="game-unit_chars-info")
    info = text_of(info_node) if info_node is not None else ""
    # The value span is the line's own value element, excluding header/info text.
    value_nodes = [n for n in line.find_all(cls="game-unit_chars-value")]
    value_node = value_nodes[0] if value_nodes else None
    # A take-off height such as "at 12,000 m" is a sibling span inside the line,
    # before the value span; keep it as explicit condition text.
    takeoff = ""
    if value_node is not None:
        condition = text_excluding(line, frozenset({"game-unit_chars-value",
                                                    "game-unit_chars-header",
                                                    "game-unit_chars-info"}))
        if condition:
            takeoff = condition
    raw_value = text_excluding(value_node, frozenset({"game-unit_chars-value"})) \
        if value_node is not None else ""
    modes = _split_class_toggle(value_node) if value_node is not None else None
    parsed = split_value(raw_value)
    if modes:
        # The four AB/RB x stock/upgraded spans concatenate into one meaningless
        # number, so the flat value stays unset and the modes carry the data.
        parsed = {"text": "", "value": None, "unit": _mode_unit(raw_value)}
    row: dict[str, Any] = {
        "label": label,
        "text": parsed["text"],
        "value": parsed["value"],
        "unit": parsed["unit"],
    }
    if info:
        row["info"] = info
    if takeoff:
        row["takeoff_condition"] = takeoff
    if modes:
        row["modes"] = modes
    return row


def _row_from_subline(subline: Node) -> dict[str, Any] | None:
    """Turn one ``.game-unit_chars-subline`` into ``{label, text, ...}``."""
    value_node = subline.first(cls="game-unit_chars-value")
    if value_node is None:
        return None
    label = text_excluding(subline, frozenset({"game-unit_chars-value", "game-unit_chars-header"}))
    modes = _split_class_toggle(value_node)
    raw_value = text_excluding(value_node, frozenset({"game-unit_chars-value", "game-unit_chars-header"}))
    parsed = split_value(raw_value)
    if modes:
        parsed = {"text": "", "value": None, "unit": _mode_unit(raw_value)}
    result: dict[str, Any] = {"label": label, "text": parsed["text"],
                              "value": parsed["value"], "unit": parsed["unit"]}
    if modes:
        result["modes"] = modes
    return result


def _walk_chars(chars: Node) -> list[dict[str, Any]]:
    """Read a ``.game-unit_chars`` container as an ordered list of rows.

    A ``.game-unit_chars-block`` may hold one line plus following sublines
    (e.g. "Flap Speed Limit" with "L / T" values).  Sublines stay attached to
    the line of the same block as ``sub_rows``.
    """
    rows: list[dict[str, Any]] = []
    for block in chars.children:
        if not isinstance(block, Node):
            continue
        if block.has_class("game-unit_chars-block"):
            children = [c for c in block.children if isinstance(c, Node)]
        elif block.has_class("game-unit_chars-line") or block.has_class("game-unit_chars-subline"):
            children = [block]
        else:
            continue
        for child in children:
            if child.has_class("game-unit_chars-line"):
                row = _row_from_chars_line(child)
                if row:
                    rows.append(row)
            elif child.has_class("game-unit_chars-subline"):
                sub = _row_from_subline(child)
                if not sub:
                    continue
                if rows:
                    rows[-1].setdefault("sub_rows", []).append(sub)
    return rows


def _characteristics(chars: Node) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split a ``.game-unit_chars`` container into main lines and trailing sublines."""
    rows = _walk_chars(chars)
    lines = [r for r in rows if "label" in r]
    sublines = [r for r in rows if "label" not in r]
    return lines, sublines


def _specs_table(container: Node) -> dict[str, Any] | None:
    """Read a ``.gunit_specs-table`` (e.g. flaps/air brake availability)."""
    rows = [r for r in container.find_all("div") if r.has_class("gunit_specs-table_row")]
    if not rows:
        return None
    labels = [_normalize(text_of(c)) for c in rows[0].children if isinstance(c, Node)]
    states = []
    for cell in (rows[1].children if len(rows) > 1 else []):
        if not isinstance(cell, Node):
            continue
        classes = " ".join(n.get("class") for n in cell.iter() if isinstance(n, Node))
        icon = cell.first(cls="bi")
        mark = None
        if icon is not None:
            tokens = icon.classes
            if "bi-check-circle-fill" in tokens or "check-circle-fill" in tokens:
                mark = "yes"
            elif "bi-x-circle" in tokens or "x-circle" in tokens:
                mark = "no"
        states.append({"mark": mark,
                       "icon_class": icon.get("class") if icon is not None else "",
                       "text": _normalize(text_of(cell)),
                       "has_check": "bi-check-circle-fill" in classes.split()})
    return {"labels": labels, "states": states}


def _feature_chips(container: Node) -> list[dict[str, Any]]:
    """Read ``button.game-unit_feature`` chips and their popover header title."""
    chips: list[dict[str, Any]] = []
    for button in container.find_all("button", cls="game-unit_feature"):
        title = ""
        detail = ""
        popover = button.get("data-feature-popover")
        if popover:
            inner = parse_dom(popover)
            header = inner.first(cls="game-unit_popover-header")
            content = inner.first(cls="game-unit_popover-content")
            if header is not None:
                title = _section_title(header)
            if content is not None:
                detail = text_of(content)
        if not title:
            title = text_of(button)
        chips.append({"title": title, "detail": detail})
    return chips


def _section_title(header: Node) -> str:
    """Popover headers append a link/btn after the title span; take the last span."""
    spans = [s for s in header.find_all("span") if not s.has_class("icon")]
    if spans:
        return text_of(spans[0])
    return text_of(header)


def extract_specification(root: Node) -> list[dict[str, Any]]:
    """Return one record per ``.block`` directly under ``#specification``.

    Weapon blocks ("Offensive armament", "Suspended armament") live under
    ``#weapon``, not ``#specification``; read them separately by their block
    header so the result still covers every titled specification block.
    """
    return _block_records(root)


def _section_for(node: Node) -> Node | None:
    """Nearest ``#specification`` or ``#weapon`` ancestor of ``node``."""
    for anc in node.ancestors():
        if anc.get("id") in ("specification", "weapon"):
            return anc
    return None


def _block_records(root: Node) -> list[dict[str, Any]]:
    """Read every titled ``.block`` owned by ``#specification`` or ``#weapon``."""
    blocks: list[dict[str, Any]] = []
    for block in root.find_all("div", cls="block"):
        section = _section_for(block)
        if section is None:
            continue
        # Only blocks owned by that section, not blocks nested inside one.
        if any(a.has_class("block") for a in block.ancestors()):
            continue
        header = block.first(cls="block-header")
        if header is None:
            continue
        content = block.first(cls="block-content") or block
        entry: dict[str, Any] = {
            "section": section.get("id"),
            "title": text_of(header),
            "features": _feature_chips(content),
        }
        rows: list[dict[str, Any]] = []
        for chars in _top_level_chars(content):
            rows.extend(_walk_chars(chars))
        entry["rows"] = rows
        for table in content.find_all("div", cls="gunit_specs-table"):
            specs = _specs_table(table)
            if specs:
                entry["availability"] = specs
                break
        weapons = _block_weapons(content)
        if weapons:
            entry["weapons"] = weapons
        blocks.append(entry)
    return blocks


def _top_level_chars(container: Node) -> list[Node]:
    """``.game-unit_chars`` nodes that are not nested inside a weapon card."""
    result = []
    for chars in container.find_all("div", cls="game-unit_chars"):
        if any(a.has_class("game-unit_weapon") for a in chars.ancestors()):
            continue
        result.append(chars)
    return result


def _block_weapons(content: Node) -> list[dict[str, Any]]:
    """Read ``.game-unit_weapon`` cards: title link plus characteristic rows."""
    result: list[dict[str, Any]] = []
    for weapon in content.find_all("div", cls="game-unit_weapon"):
        title_node = weapon.first(cls="game-unit_weapon-title")
        link = title_node.first("a") if title_node is not None else None
        rows: list[dict[str, Any]] = []
        for chars in weapon.find_all("div", cls="game-unit_chars"):
            lines, sublines = _characteristics(chars)
            rows.extend(lines)
            rows.extend(sublines)
        result.append({
            "name": text_of(title_node) if title_node is not None else "",
            "href": _clean_url(link.get("href")) if link is not None else "",
            "rows": rows,
        })
    return result


# -----------------------------------------------------------------------------
# belts
# -----------------------------------------------------------------------------
def _layers_from(container: Node | None) -> list[str]:
    """Ordered ``gui_skin`` image file names inside a belt icon container."""
    if container is None:
        return []
    layers = []
    for img in container.find_all("img"):
        src = _clean_url(img.get("src"))
        if not src:
            continue
        layers.append(src.rsplit("/", 1)[-1])
    return layers


def _nested_popover(node: Node) -> Node | None:
    """Parse a ``data-feature-popover`` attribute value into a DOM node."""
    raw = node.get("data-feature-popover")
    if not raw:
        return None
    return parse_dom(raw)


def _belt_popover(button: Node) -> dict[str, Any]:
    """Belt name, base/full icon layers and popover details."""
    info: dict[str, Any] = {}
    popover = _nested_popover(button)
    if popover is None:
        return info
    # The name is the header's last non-icon span (links may follow it).
    header = popover.first(cls="game-unit_popover-header")
    name = ""
    if header is not None:
        spans = [s for s in header.find_all("span") if not s.has_class("icon")]
        name = text_of(spans[0]) if spans else text_of(header)
    info["belt"] = name
    base = popover.first(cls="game-unit_b-icon_base")
    info["base_icon_layers"] = _layers_from(base)
    full_icon = popover.first(cls="game-unit_b-icon")
    info["icon_layers"] = _layers_from(full_icon)
    content = popover.first(cls="game-unit_popover-content")
    if content is not None:
        desc = content.find_all("div")
        if desc:
            first_text = text_of(desc[0])
            if first_text:
                info["filling_detail"] = first_text
    return info


def _belt_row(cells: list[Node]) -> dict[str, Any]:
    """Turn the ``<td>`` cells of one belt table row into a record."""
    row: dict[str, Any] = {"belt": "", "filling": "", "icon_layers": [], "penetration": {}}
    if cells:
        first = cells[0]
        button = first.first("button")
        popover = _belt_popover(button) if button is not None else {}
        name = popover.get("belt") or text_of(first)
        row["belt"] = name
        row["icon_layers"] = popover.get("icon_layers", [])
        if popover.get("base_icon_layers"):
            row["base_icon_layers"] = popover["base_icon_layers"]
        if popover.get("filling_detail"):
            row["filling_detail"] = popover["filling_detail"]
    if len(cells) > 1:
        row["filling"] = text_of(cells[1])
    if len(cells) > 2:
        values = []
        for cell in cells[2:]:
            parsed = split_value(text_of(cell))
            values.append(parsed)
        row["penetration_values"] = values
    return row


def _distance_headers(headers: list[Node]) -> list[dict[str, Any]]:
    result = []
    for th in headers:
        text = text_of(th)
        match = DISTANCE_RE.match(text)
        if match:
            result.append({"text": text, "distance_m": to_number(match.group(1))})
    return result


def _belt_table(table: Node) -> dict[str, Any]:
    thead = table.first("thead")
    tbody = table.first("tbody")
    head_rows = thead.find_all("tr") if thead is not None else []
    headers = [th for tr in head_rows for th in tr.find_all("th")]
    distance_headers = _distance_headers(headers)
    distances = [d["distance_m"] for d in distance_headers]
    result: dict[str, Any] = {
        "headers": [text_of(th) for th in headers],
        "distances": distances,
        "rows": [],
    }
    body_rows = tbody.find_all("tr") if tbody is not None else []
    for tr in body_rows:
        cells = [c for c in tr.children if isinstance(c, Node) and c.tag == "td"]
        if not cells:
            continue
        row = _belt_row(cells)
        penetration: dict[str, Any] = {}
        values = row.pop("penetration_values", [])
        for index, value in enumerate(values):
            if index < len(distances) and distances[index] is not None:
                penetration[str(distances[index])] = value["value"]
            else:
                penetration[f"column_{index}"] = value["value"]
        row["penetration"] = penetration
        result["rows"].append(row)
    return result


def _belt_container_label(table: Node) -> dict[str, str]:
    """Identify the accordion section (weapon preset + belt id) holding a table."""
    for anc in table.ancestors():
        for attr in ("aria-controls", "id"):
            value = anc.get(attr)
            if value.startswith("weapon-belts-"):
                return {"container_id": value}
        if anc.get("id").startswith("weapon-preset-"):
            return {"preset_id": anc.get("id")}
    return {}


def extract_belts(root: Node) -> list[dict[str, Any]]:
    """Return every ``table.game-unit_belt-list`` with its rows."""
    belts: list[dict[str, Any]] = []
    for table in root.find_all("table", cls="game-unit_belt-list"):
        entry = _belt_container_label(table)
        for anc in table.ancestors():
            if anc.has_class('game-unit_weapon'):
                title=anc.first(cls='game-unit_weapon-title')
                entry['weapon_title']=text_of(title) if title else ''
                break
        entry.update(_belt_table(table))
        belts.append(entry)
    return belts


# -----------------------------------------------------------------------------
# loadout / slots
# -----------------------------------------------------------------------------
POPOVER_TEXT_ROW = re.compile(r"^(?P<label>[^:<]{1,80}):\s*(?P<value>.+)$")


def _popover_rows(node: Node | None) -> list[dict[str, str]]:
    """Flatten a ``data-feature-popover`` into ``label``/``value`` pairs."""
    if node is None:
        return []
    rows: list[dict[str, str]] = []
    content = node.first(cls="game-unit_popover-content")
    if content is None:
        return rows
    for line in content.find_all("div", cls="game-unit_chars-line"):
        header = line.first(cls="game-unit_chars-header")
        value = line.first(cls="game-unit_chars-value")
        if header is None:
            continue
        label = text_of(header)
        if value is None:
            continue
        value_text = text_excluding(value, frozenset({"game-unit_chars-value"}))
        if not value_text:
            marks = ' '.join(n.get('class') for n in value.iter())
            if 'check' in marks: value_text='✓'
            elif 'times' in marks or 'xmark' in marks: value_text='—'
        rows.append({"label": label, "value": value_text})
    if rows:
        return rows
    # Fallback: plain ``Label: value`` lines.
    for line in content.find_all("div"):
        text = _normalize(text_of(line))
        match = POPOVER_TEXT_ROW.match(text)
        if match:
            rows.append({"label": match.group("label").strip(),
                         "value": match.group("value").strip()})
    return rows


def _popover_title(node: Node | None) -> str:
    if node is None:
        return ""
    header = node.first(cls="game-unit_popover-header")
    if header is None:
        return ""
    spans = [s for s in header.find_all("span") if not s.has_class("icon")]
    return text_of(spans[0]) if spans else text_of(header)


def _store_popover(button: Node) -> dict[str, Any]:
    """Name, collection link, description and parameter rows for a store."""
    result: dict[str, Any] = {"name": "", "href": "", "parameters": []}
    popover = _nested_popover(button)
    if popover is None:
        return result
    result["name"] = _popover_title(popover)
    link = popover.first("a")
    if link is not None:
        result["href"] = _clean_url(link.get("href"))
    content = popover.first(cls="game-unit_popover-content")
    if content is not None:
        description = text_of(content.find_all("div")[0]) if content.find_all("div") else ""
        if description and description != result["name"]:
            result["description"] = description
        nested_button = content.first("button", cls="penetration-info")
        if nested_button is not None:
            rows = _popover_rows_of_content(_nested_content(nested_button))
            if rows:
                result["penetration_table"] = rows
    result["parameters"] = _popover_rows(popover)
    return result


def _nested_content(button: Node) -> Node | None:
    raw = button.get("data-bs-content")
    return parse_dom(raw) if raw else None


def _popover_rows_of_content(content: Node | None) -> list[dict[str, str]]:
    if content is None:
        return []
    rows: list[dict[str, str]] = []
    for line in content.find_all("div", cls="game-unit_chars-line"):
        header = line.first(cls="game-unit_chars-header")
        value = line.first(cls="game-unit_chars-value")
        if header is not None and value is not None:
            rows.append({"label": text_of(header), "value": text_of(value)})
    if rows:
        return rows
    # Nested penetration popovers render a plain table of "distance / value".
    for tr in content.find_all("tr"):
        cells = [c for c in tr.children if isinstance(c, Node) and c.tag in ("td", "th")]
        if len(cells) >= 2:
            rows.append({"label": text_of(cells[0]), "value": text_of(cells[-1])})
    return rows


def _slot_cell(cell: Node) -> dict[str, Any]:
    """Read one slot cell: quantity text/number plus pylon icon and its hints."""
    text = _normalize(text_of(cell))
    result: dict[str, Any] = {"text": text, "value": to_number(text)}
    icons = []
    for img in cell.find_all("img"):
        src = _clean_url(img.get("src"))
        if not src:
            continue
        icon: dict[str, Any] = {"file": src.rsplit("/", 1)[-1]}
        # Hardpoint icons carry the mount id / count in attributes on the page.
        for attr in ("title", "alt", "data-slot", "data-count"):
            value = img.get(attr)
            if value:
                icon[attr.replace("data-", "")] = value
        icons.append(icon)
    if icons:
        result["icons"] = [i["file"] for i in icons]
        result["icon_details"] = icons
        if not text:
            # Fall back to an icon-carried count when the cell has no text.
            for icon in icons:
                for key in ("count", "title"):
                    if key in icon:
                        number = to_number(icon[key])
                        if number is not None:
                            result["value"] = number
                            result["value_source"] = "icon." + key
                            break
                if result["value"] is not None:
                    break
    return result


def _loadout_row(cells: list[Node], slot_headers: list[str]) -> dict[str, Any]:
    row: dict[str, Any] = {
        "name": "",
        "weight_text": "",
        "weight_kg": None,
        "slots": [],
        "parameters": [],
    }
    if cells:
        first = cells[0]
        button = first.first("button")
        if button is not None:
            store = _store_popover(button)
            row["name"] = store["name"] or text_of(first)
            if store["href"]:
                row["href"] = store["href"]
            if store.get("description"):
                row["description"] = store["description"]
            if store.get("penetration_table"):
                row["penetration_table"] = store["penetration_table"]
            row["parameters"] = store["parameters"]
        else:
            row["name"] = text_of(first)
    if len(cells) > 1:
        parsed = split_value(text_of(cells[1]))
        row["weight_text"] = parsed["text"]
        row["weight_kg"] = parsed["value"]
        row["weight_unit"] = parsed["unit"]
    for index, cell in enumerate(cells[2:]):
        slot = _slot_cell(cell)
        slot["index"] = index + 1
        slot["header"] = slot_headers[index] if index < len(slot_headers) else ""
        # Keep every slot cell so positions stay aligned with the header order;
        # an unused hardpoint simply has an empty text and no icon.
        row["slots"].append(slot)
    return row


def _slot_headers(headers: list[Node]) -> tuple[list[str], dict[str, Any]]:
    """Return the leading column names and the trailing slot-column labels."""
    names = [text_of(th) for th in headers]
    leading = [n for n in names[:2]]
    slot_headers: list[str] = []
    trailing: list[str] = []
    for th in headers[2:]:
        text = text_of(th)
        colspan = th.get("colspan")
        width = int(colspan) if colspan.isdigit() else 1
        label = text
        # The "Slot" group header may be followed by per-pylon labels; a group
        # header without per-column text simply names the group.
        if width > 1 and not label:
            label = "slot"
        for index in range(width):
            slot_headers.append(label if width == 1 else f"{label}[{index + 1}]")
        if label:
            trailing.append(label)
    return slot_headers, {"labels": leading, "slot_columns": slot_headers}


def extract_loadout(root: Node) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    """Return ``(slot_headers, leading_headers, rows)`` for the slot list."""
    slot_headers: list[str] = []
    leading: list[str] = []
    rows: list[dict[str, Any]] = []
    for table in root.find_all("table", cls="game-unit_slot-list"):
        thead = table.first("thead")
        headers = []
        if thead is not None:
            tr = thead.first("tr")
            if tr is not None:
                headers = [th for th in tr.find_all("th")]
        if not slot_headers and headers:
            slot_headers, meta = _slot_headers(headers)
            leading = meta["labels"]
        tbody = table.first("tbody")
        if tbody is None:
            continue
        for tr in tbody.find_all("tr"):
            cells = [c for c in tr.children if isinstance(c, Node) and c.tag == "td"]
            if not cells:
                continue
            rows.append(_loadout_row(cells, slot_headers))
    return slot_headers, leading, rows


# -----------------------------------------------------------------------------
# top level
# -----------------------------------------------------------------------------
def extract_reference(raw_html: str) -> dict[str, Any]:
    """Parse one official vehicle page and return every structure we model.

    The result is deliberately generic (no vehicle-specific assumptions) and
    keeps the source wording.  Missing structures yield empty lists.
    """
    root = parse_dom(raw_html)
    spec_blocks = extract_specification(root)
    belts = extract_belts(root)
    slot_headers, leading_headers, loadout_rows = extract_loadout(root)
    return {
        "specification_blocks": spec_blocks,
        "belts": belts,
        "slot_headers": slot_headers,
        "loadout_leading_headers": leading_headers,
        "loadout_rows": loadout_rows,
    }


# -----------------------------------------------------------------------------
# MHTML / CLI
# -----------------------------------------------------------------------------
def _unit_title_from_url(location: str) -> str:
    return location.rstrip("/").rsplit("/", 1)[-1].casefold()


def official_pages(reference_dir: Path, code: str) -> list[tuple[Path, str, str]]:
    """Yield ``(path, location, html_text)`` for saved pages of ``code``."""
    target = code.casefold()
    found: list[tuple[Path, str, str]] = []
    for path in sorted(reference_dir.glob("*.mhtml")):
        message = email.message_from_bytes(path.read_bytes())
        for part in message.walk():
            if part.get_content_type() != "text/html":
                continue
            location = part.get("Content-Location", "") or ""
            if location and _unit_title_from_url(location) != target:
                continue
            if not location and target not in path.name.casefold():
                continue
            payload = part.get_payload(decode=True) or b""
            charset = part.get_content_charset() or "utf-8"
            found.append((path, location, payload.decode(charset, errors="replace")))
    return found


def parse_saved_page(reference_dir: Path, code: str) -> dict[str, Any]:
    """Parse the first saved official page for ``code``; raise when absent."""
    pages = official_pages(reference_dir, code)
    if not pages:
        raise FileNotFoundError(f"Reference 目录中找不到 {code} 的官方页面：{reference_dir}")
    path, location, text = pages[0]
    result = extract_reference(text)
    result = {"source": {"file": "Reference/" + path.name, "location": location,
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()},
              **result}
    return result


def extract_saved_html(path: Path, *, location: str = "") -> dict[str, Any]:
    """Parse an already-saved rendered HTML file (no MHTML wrapping)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    result = extract_reference(text)
    result = {"source": {"file": path.as_posix(), "location": location,
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()},
              **result}
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--unit", help="vehicle code such as mig_35 (reads Reference/*.mhtml)")
    parser.add_argument("--html", type=Path,
                        help="already-saved rendered HTML file (default: work/research/<unit>-official.html)")
    parser.add_argument("--out", type=Path, help="output JSON path")
    args = parser.parse_args(argv)

    if not args.unit and not args.html:
        parser.error("需要 --unit 或 --html")
    html_path = args.html
    if html_path is None and args.unit:
        # Prefer the saved MHTML snapshot; fall back to the plain saved HTML.
        reference = ROOT.parent / "Reference"
        if not official_pages(reference, args.unit):
            candidate = ROOT / "work" / "research" / f"{args.unit.replace('_', '-')}-official.html"
            if not candidate.is_file():
                candidate = ROOT / "work" / "research" / f"{args.unit}-official.html"
            if candidate.is_file():
                html_path = candidate
    if html_path is not None:
        result = extract_saved_html(html_path, location="https://wiki.warthunder.com/unit/" + (args.unit or ""))
    else:
        result = parse_saved_page(ROOT.parent / "Reference", args.unit)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
