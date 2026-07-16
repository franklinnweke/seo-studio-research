#!/usr/bin/env python3
import argparse
from datetime import datetime
import html
import json
from pathlib import Path
import re
import shutil
import time
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PIL import Image


EVALUATION_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = EVALUATION_ROOT.parent
CATALOG_PATH = EVALUATION_ROOT / "dataset" / "pilot-catalog.json"
MANIFEST_PATH = EVALUATION_ROOT / "dataset" / "manifest.jsonl"
USER_AGENT = "SEO-Studio-Research/0.1 (https://github.com/iobami/seo-studio; educational capstone)"
ALLOWED_LICENSES = {
    "CC0",
    "CC BY 2.0",
    "CC BY 4.0",
    "CC BY-SA 3.0",
    "CC BY-SA 4.0",
    "Public domain",
    "Public domain (U.S. government work)",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize the declared 20-item licensed pilot set")
    parser.add_argument("--retrieved-at", required=True, help="ISO-8601 evidence retrieval timestamp")
    parser.add_argument("--force", action="store_true", help="Replace only generated pilot artifacts")
    args = parser.parse_args()
    datetime.fromisoformat(args.retrieved_at.replace("Z", "+00:00"))

    catalog = json.loads(CATALOG_PATH.read_text())
    if not isinstance(catalog, list) or len(catalog) != 20:
        raise ValueError("pilot catalog must contain exactly 20 items")
    if MANIFEST_PATH.exists() and not args.force:
        raise FileExistsError("pilot manifest exists; pass --force to replace generated pilot artifacts")

    image_dir = EVALUATION_ROOT / "dataset" / "images" / "pilot"
    license_dir = EVALUATION_ROOT / "dataset" / "licenses" / "pilot"
    context_dir = EVALUATION_ROOT / "dataset" / "page-contexts" / "pilot"
    for directory in (image_dir, license_dir, context_dir):
        directory.mkdir(parents=True, exist_ok=True)

    commons_pageids = [
        int(entry["asset"]["pageid"])
        for entry in catalog
        if entry.get("asset", {}).get("kind") == "commons"
    ]
    commons_sources = fetch_commons_metadata_batch(commons_pageids)
    manifest_rows: list[dict[str, Any]] = []
    for entry in catalog:
        manifest_rows.append(
            materialize_item(
                entry,
                image_dir,
                license_dir,
                context_dir,
                args.retrieved_at,
                commons_sources,
            )
        )

    MANIFEST_PATH.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in manifest_rows)
    )
    summary = {
        "catalog": str(CATALOG_PATH.relative_to(EVALUATION_ROOT)),
        "items": len(manifest_rows),
        "manifest": str(MANIFEST_PATH.relative_to(EVALUATION_ROOT)),
        "retrieved_at": args.retrieved_at,
    }
    (EVALUATION_ROOT / "dataset" / "pilot-materialization-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


def materialize_item(
    entry: dict[str, Any],
    image_dir: Path,
    license_dir: Path,
    context_dir: Path,
    retrieved_at: str,
    commons_sources: dict[int, dict[str, str]],
) -> dict[str, Any]:
    item_id = required_text(entry, "id")
    asset = entry.get("asset")
    if not isinstance(asset, dict):
        raise ValueError(f"{item_id}: asset must be an object")
    filename = required_text(entry, "filename")
    image_path = image_dir / filename

    if asset.get("kind") == "commons":
        source = commons_sources[int(asset["pageid"])]
        expected_license = required_text(asset, "expected_license")
        if source["license"] != expected_license:
            raise ValueError(
                f"{item_id}: expected {expected_license!r}, Commons returned {source['license']!r}"
            )
        media = download(source["download_url"])
        image_path.write_bytes(media)
        preprocessing = "wikimedia_thumbnail_max_width_1280_v1"
    elif asset.get("kind") == "local":
        source_path = resolve_repository_path(required_text(asset, "path"))
        shutil.copyfile(source_path, image_path)
        source = {
            "source_url": required_text(asset, "source_url"),
            "source_title": required_text(asset, "source_title"),
            "author": required_text(asset, "author"),
            "license": required_text(asset, "license"),
            "license_url": required_text(asset, "license_url"),
            "original_media_url": required_text(asset, "source_url"),
            "download_url": required_text(asset, "source_url"),
        }
        preprocessing = "existing_wikimedia_thumbnail_no_additional_processing_v1"
    else:
        raise ValueError(f"{item_id}: unsupported asset kind")

    if source["license"] not in ALLOWED_LICENSES:
        raise ValueError(f"{item_id}: license is outside the approved pilot allowlist")
    with Image.open(image_path) as image:
        width, height = image.size
        image.verify()

    context = entry.get("page_context")
    if not isinstance(context, dict):
        raise ValueError(f"{item_id}: page_context must be an object")
    context_path = context_dir / f"{item_id}.json"
    context_path.write_text(json.dumps(context, indent=2, sort_keys=True) + "\n")

    evidence = {
        "item_id": item_id,
        "source_url": source["source_url"],
        "source_title": source["source_title"],
        "author": source["author"],
        "license": source["license"],
        "license_url": source["license_url"],
        "original_media_url": source["original_media_url"],
        "retrieved_at": retrieved_at,
    }
    evidence_path = license_dir / f"{item_id}.json"
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")

    brand_profile_path = EVALUATION_ROOT / required_text(entry, "brand_profile_path")
    if not brand_profile_path.is_file() or EVALUATION_ROOT not in brand_profile_path.resolve().parents:
        raise ValueError(f"{item_id}: invalid brand profile path")

    return {
        "id": item_id,
        "split": "pilot",
        "image_path": relative(image_path),
        "sha256": sha256_file(image_path),
        "image_bytes": image_path.stat().st_size,
        "width": width,
        "height": height,
        "preprocessing": preprocessing,
        "domain": required_text(entry, "domain"),
        "license": source["license"],
        "license_url": source["license_url"],
        "license_evidence_path": relative(evidence_path),
        "license_evidence_sha256": sha256_file(evidence_path),
        "source_url": source["source_url"],
        "source_title": source["source_title"],
        "author": source["author"],
        "purpose": required_text(entry, "purpose"),
        "page_context_id": required_text(context, "id"),
        "page_context_path": relative(context_path),
        "page_context_sha256": sha256_file(context_path),
        "brand_profile_id": required_text(entry, "brand_profile_id"),
        "brand_profile_path": required_text(entry, "brand_profile_path"),
        "brand_profile_sha256": sha256_file(brand_profile_path),
        "scene_tags": entry["scene_tags"],
        "reference_visible_facts": entry["reference_visible_facts"],
        "forbidden_claims": entry["forbidden_claims"],
        "adjudication_alt_examples": entry["adjudication_alt_examples"],
        "annotation_notes": required_text(entry, "annotation_notes"),
    }


def fetch_commons_metadata_batch(pageids: list[int]) -> dict[int, dict[str, str]]:
    params = urlencode(
        {
            "action": "query",
            "pageids": "|".join(str(pageid) for pageid in pageids),
            "prop": "imageinfo",
            "iiprop": "url|size|extmetadata",
            "iiurlwidth": "1280",
            "format": "json",
            "formatversion": "2",
        }
    )
    payload = json.loads(download(f"https://commons.wikimedia.org/w/api.php?{params}"))
    sources: dict[int, dict[str, str]] = {}
    for page in payload["query"]["pages"]:
        info = page["imageinfo"][0]
        metadata = info["extmetadata"]
        license_name = metadata.get("LicenseShortName", {}).get("value", "")
        license_url = metadata.get("LicenseUrl", {}).get("value", "")
        if not license_url and license_name == "Public domain":
            license_url = "https://commons.wikimedia.org/wiki/Commons:Copyright_tags#Public_domain"
        license_url = license_url.replace("http://", "https://", 1)
        sources[int(page["pageid"])] = {
            "source_url": info["descriptionurl"],
            "source_title": clean_html(metadata.get("ObjectName", {}).get("value", page["title"])),
            "author": clean_html(metadata.get("Artist", {}).get("value", "Unknown author")),
            "license": license_name,
            "license_url": license_url,
            "original_media_url": info["url"],
            "download_url": info.get("thumburl", info["url"]),
        }
    missing = sorted(set(pageids) - set(sources))
    if missing:
        raise ValueError(f"Commons metadata missing for page ids: {missing}")
    return sources


def download(url: str) -> bytes:
    for delay in (0, 1, 2, 4):
        if delay:
            time.sleep(delay)
        request = Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urlopen(request, timeout=60) as response:
                return response.read()
        except HTTPError as exc:
            if exc.code != 429 or delay == 4:
                raise
    raise RuntimeError("unreachable download retry state")


def clean_html(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return " ".join(html.unescape(without_tags).split()) or "Unknown author"


def resolve_repository_path(value: str) -> Path:
    path = (REPOSITORY_ROOT / value).resolve()
    if REPOSITORY_ROOT not in path.parents:
        raise ValueError(f"local source escapes repository root: {value}")
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def relative(path: Path) -> str:
    return str(path.resolve().relative_to(EVALUATION_ROOT))


def required_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value.strip()


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
