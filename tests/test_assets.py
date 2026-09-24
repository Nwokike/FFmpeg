"""Brand asset loading must not depend on Flet's client URL resolver."""

from flet import Image

from core.assets import app_icon_svg


def test_svg_is_loaded_as_tintable_bytes():
    data = app_icon_svg()
    assert b"<svg" in data[:256]
    image = Image(src=data, width=32, height=32)
    assert image.src == data
