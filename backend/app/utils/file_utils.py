from pathlib import Path

from app.utils.slugify import slugify


def sanitize_filename(filename: str) -> str:
    path = Path(filename)
    extension = path.suffix.lower()
    return f"{slugify(path.stem)}{extension}"


def dedupe_filename(filename: str, used_names: set[str]) -> str:
    path = Path(filename)
    stem = path.stem
    extension = path.suffix
    candidate = filename
    counter = 2

    while candidate.lower() in used_names:
        candidate = f"{stem}-{counter}{extension}"
        counter += 1

    used_names.add(candidate.lower())
    return candidate
