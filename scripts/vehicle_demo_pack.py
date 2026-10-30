"""Retired demo command: forward to formal packaging; retain read-only API helpers.

The old demo generator has been removed. It cannot regenerate wrong-name pages.
"""
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://wiki.biligame.com/warthunder/"


def query(titles):
    results = {}
    for start in range(0, len(titles), 15):
        batch = titles[start:start + 15]
        try:
            params = urlencode({"action": "query", "format": "json", "titles": "|".join(batch), "redirects": 1,
                                "prop": "info|imageinfo", "iiprop": "url|size|sha1|timestamp"}).encode()
            request = Request(BASE + "api.php", data=params, headers={"User-Agent": "WTJ-read-only-package/1.0", "Content-Type":"application/x-www-form-urlencoded"})
            with urlopen(request, timeout=30) as response:
                raw = json.load(response)
            if "query" not in raw:
                raise ValueError(str(raw.get("error", raw)))
            normalized = {x["from"]: x["to"] for group in ('normalized', 'converted', 'redirects')
                          for x in raw["query"].get(group, [])}
            found = {x["title"]: x for x in raw["query"]["pages"].values()}
            for title in batch:
                resolved = title
                visited = set()
                while resolved in normalized and resolved not in visited:
                    visited.add(resolved)
                    resolved = normalized[resolved]
                record = found.get(resolved)
                results[title] = {"status": "unknown" if record is None else "missing" if "missing" in record else "existing", "record": record}
        except Exception as exc:
            for title in batch:
                results[title] = {"status": "unknown", "error": str(exc)}
    return results


def has_local_image(record):
    return bool(record and record.get("imageinfo"))


def main():
    from vehicle_pack import main as formal_main
    return formal_main()


if __name__ == "__main__":
    main()
