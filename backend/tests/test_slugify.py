from app.utils.slugify import slugify


def test_slugify_normalizes_names() -> None:
    assert slugify("IMG 123 Final!!") == "img-123-final"


def test_slugify_falls_back_for_empty_names() -> None:
    assert slugify("!!!") == "file"
