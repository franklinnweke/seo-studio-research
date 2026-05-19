from pathlib import Path, PurePosixPath
from zipfile import ZipInfo


IGNORED_ZIP_PREFIXES = ("__MACOSX/",)


def is_ignored_zip_entry(name: str) -> bool:
    normalized = name.replace("\\", "/")
    return normalized.startswith(IGNORED_ZIP_PREFIXES) or Path(normalized).name.startswith(".")


def safe_zip_entry_name(info: ZipInfo) -> str:
    name = info.filename.replace("\\", "/")
    path = PurePosixPath(name)

    if info.is_dir():
        raise ValueError("ZIP directories are not saved as image files.")

    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe ZIP entry path: {info.filename}")

    filename = path.name
    if not filename:
        raise ValueError(f"Invalid ZIP entry path: {info.filename}")

    return filename
