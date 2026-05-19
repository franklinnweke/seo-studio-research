SUPPORTED_UPLOAD_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".zip"}
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def is_supported_upload_extension(extension: str) -> bool:
    return extension.lower() in SUPPORTED_UPLOAD_EXTENSIONS


def is_supported_image_extension(extension: str) -> bool:
    return extension.lower() in SUPPORTED_IMAGE_EXTENSIONS
