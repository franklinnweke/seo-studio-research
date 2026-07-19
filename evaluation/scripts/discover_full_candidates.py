#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageOps


EVALUATION_ROOT = Path(__file__).resolve().parents[1]
QUERY_PATH = EVALUATION_ROOT / "configs" / "full-study-discovery-queries.json"
CACHE_ROOT = EVALUATION_ROOT / "dataset" / "cache" / "full-study-candidates"
USER_AGENT = "SEO-Studio-Research/0.1 (https://github.com/franklinnweke/seo-studio-research)"
ALLOWED_LICENSES = {
    "CC0",
    "CC BY 2.0",
    "CC BY 3.0",
    "CC BY 4.0",
    "CC BY-SA 2.0",
    "CC BY-SA 3.0",
    "CC BY-SA 4.0",
    "Public domain",
}


def main() -> int:
    plan = json.loads(QUERY_PATH.read_text())
    per_query = int(plan["candidates_per_query"])
    minimum_per_query = int(plan["selected_per_query"])
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    excluded_pageids = _pilot_pageids()
    selected_pageids: set[int] = set(excluded_pageids)
    records: list[dict[str, Any]] = []
    shortages: list[str] = []

    for domain, queries in plan["domains"].items():
        domain_records: list[dict[str, Any]] = []
        for query_index, query in enumerate(queries, start=1):
            candidates = search_commons(query["query"])
            accepted = 0
            for candidate in candidates:
                pageid = int(candidate["pageid"])
                if pageid in selected_pageids or not _eligible(candidate):
                    continue
                candidate_id = f"{domain.replace('_', '-')}-{query_index:02d}-p{pageid}"
                thumbnail_path = CACHE_ROOT / domain / f"{candidate_id}.jpg"
                thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    _write_thumbnail(candidate["thumb_url"], thumbnail_path)
                except (HTTPError, OSError):
                    continue
                record = {
                    **candidate,
                    "candidate_id": candidate_id,
                    "domain": domain,
                    "purpose_hint": query["purpose"],
                    "query": query["query"],
                    "query_id": query["id"],
                    "thumbnail_path": str(thumbnail_path.relative_to(EVALUATION_ROOT)),
                    "visual_decision": "pending",
                }
                domain_records.append(record)
                records.append(record)
                selected_pageids.add(pageid)
                accepted += 1
                if accepted == per_query:
                    break
            if accepted < minimum_per_query:
                shortages.append(
                    f"{domain}/{query['id']}={accepted}/{minimum_per_query}-minimum"
                )
            time.sleep(0.1)
        _write_contact_sheet(domain, domain_records)

    output_path = CACHE_ROOT / "candidates.json"
    output_path.write_text(json.dumps(records, indent=2, sort_keys=True) + "\n")
    summary = {
        "candidates": len(records),
        "candidates_per_domain": {
            domain: sum(record["domain"] == domain for record in records)
            for domain in plan["domains"]
        },
        "output": str(output_path.relative_to(EVALUATION_ROOT)),
        "query_plan": str(QUERY_PATH.relative_to(EVALUATION_ROOT)),
        "shortages": shortages,
    }
    print(json.dumps(summary, sort_keys=True))
    if shortages:
        raise ValueError("underfilled candidate queries: " + ", ".join(shortages))
    return 0


def search_commons(query: str) -> list[dict[str, Any]]:
    cache_key = hashlib.sha256(query.encode()).hexdigest()[:16]
    cache_path = CACHE_ROOT / "search" / f"{cache_key}.json"
    if cache_path.is_file():
        return json.loads(cache_path.read_text())
    params = urlencode(
        {
            "action": "query",
            "generator": "search",
            "gsrnamespace": "6",
            "gsrsearch": f"{query} filetype:bitmap",
            "gsrlimit": "40",
            "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": "640",
            "format": "json",
            "formatversion": "2",
        }
    )
    payload = json.loads(download(f"https://commons.wikimedia.org/w/api.php?{params}"))
    records: list[dict[str, Any]] = []
    for page in payload.get("query", {}).get("pages", []):
        info = page.get("imageinfo", [{}])[0]
        metadata = info.get("extmetadata", {})
        records.append(
            {
                "author": clean_text(metadata.get("Artist", {}).get("value", "Unknown author")),
                "description": clean_text(metadata.get("ImageDescription", {}).get("value", "")),
                "download_url": info.get("url", ""),
                "height": info.get("height", 0),
                "license": metadata.get("LicenseShortName", {}).get("value", ""),
                "license_url": metadata.get("LicenseUrl", {}).get("value", "").replace(
                    "http://", "https://", 1
                ),
                "mime": info.get("mime", ""),
                "pageid": page["pageid"],
                "source_title": clean_text(
                    metadata.get("ObjectName", {}).get("value", page.get("title", ""))
                ),
                "source_url": info.get("descriptionurl", ""),
                "thumb_url": info.get("thumburl", info.get("url", "")),
                "width": info.get("width", 0),
            }
        )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(records, indent=2, sort_keys=True) + "\n")
    return records


def _eligible(record: dict[str, Any]) -> bool:
    return (
        record["license"] in ALLOWED_LICENSES
        and record["mime"] in {"image/jpeg", "image/png"}
        and record["width"] >= 800
        and record["height"] >= 500
        and record["source_url"].startswith("https://commons.wikimedia.org/")
        and record["thumb_url"].startswith("https://")
        and record["license_url"].startswith("https://")
    )


def _pilot_pageids() -> set[int]:
    catalog = json.loads((EVALUATION_ROOT / "dataset" / "pilot-catalog.json").read_text())
    return {
        int(row["asset"]["pageid"])
        for row in catalog
        if row.get("asset", {}).get("kind") == "commons"
    }


def _write_thumbnail(url: str, output_path: Path) -> None:
    if output_path.is_file():
        return
    media = download(url)
    temporary = output_path.with_suffix(".source")
    temporary.write_bytes(media)
    try:
        with Image.open(temporary) as image:
            ImageOps.exif_transpose(image).convert("RGB").save(output_path, quality=88)
    finally:
        temporary.unlink(missing_ok=True)
    time.sleep(0.25)


def _write_contact_sheet(domain: str, records: list[dict[str, Any]]) -> None:
    cell_width = 320
    image_height = 210
    label_height = 50
    columns = 4
    rows = (len(records) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * cell_width, rows * (image_height + label_height)), "white")
    draw = ImageDraw.Draw(sheet)
    for index, record in enumerate(records):
        image_path = EVALUATION_ROOT / record["thumbnail_path"]
        with Image.open(image_path) as source:
            thumbnail = ImageOps.fit(source.convert("RGB"), (cell_width, image_height))
        x = (index % columns) * cell_width
        y = (index // columns) * (image_height + label_height)
        sheet.paste(thumbnail, (x, y))
        label = f"{record['candidate_id']}  {record['purpose_hint']}\n{record['source_title'][:48]}"
        draw.multiline_text((x + 5, y + image_height + 4), label, fill="black", spacing=2)
    sheet.save(CACHE_ROOT / f"contact-sheet-{domain}.jpg", quality=90)


def download(url: str) -> bytes:
    for delay in (0, 2, 5, 10, 20):
        if delay:
            time.sleep(delay)
        request = Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urlopen(request, timeout=60) as response:
                return response.read()
        except HTTPError as exc:
            if exc.code != 429 or delay == 20:
                raise
    raise RuntimeError("unreachable download retry state")


def clean_text(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return " ".join(without_tags.replace("&nbsp;", " ").split()) or "Untitled"


if __name__ == "__main__":
    raise SystemExit(main())
