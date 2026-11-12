"""Surface tests: the capability layer is derived from the wheel, not written.

The DDGS/proot pattern: equality against the installed package (not a
subset), and an AST scan that fails if hand-written capability tables creep
back into the screens.
"""

from __future__ import annotations

import ast
import glob
from pathlib import Path

import av

from core.engine_probe import can_encode, can_encode_format, codec_label, probe

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def test_encoders_equal_the_wheels_full_set():
    """No preference filtering: probe.encoders is EXACTLY the wheel's w-mode
    set, in the wheel's canonical names (the wheel resolves aliases itself:
    Codec("h264","w").name is "libx264")."""
    p = probe()
    expected = set()
    for name in av.codecs_available:
        try:
            codec = av.codec.Codec(name, mode="w")
        except Exception:
            continue
        expected.add(str(codec.name or name))
    assert p.encoders == expected
    assert p.encoder_count == len(expected)


def test_decoders_equal_the_wheels_full_set():
    p = probe()
    expected = set()
    for name in av.codecs_available:
        try:
            av.codec.Codec(name, mode="r")
        except Exception:
            continue
        expected.add(name)
    assert p.decoders == expected


def test_codec_families_partition_constructible_codecs():
    """Every constructible codec belongs to exactly one AVCodecID family, and
    members of one family share the id (h264 decoder == libx264 encoder)."""
    p = probe()
    seen: set[str] = set()
    for members in p.codec_families.values():
        assert members
        ids = set()
        for name in members:
            assert name not in seen, f"{name} appears in two families"
            seen.add(name)
            for mode in ("r", "w"):
                try:
                    ids.add(av.codec.Codec(name, mode=mode).id)
                except Exception:
                    pass
        assert len(ids) == 1, f"family {members} does not share an AVCodecID: {ids}"
    assert seen == p.codecs, "some codecs did not land in any family"


def test_option_schema_covers_every_encoder():
    p = probe()
    assert set(p.encoder_option_schema) == p.encoders
    for name, schema in p.encoder_option_schema.items():
        assert schema, f"{name}: empty option schema"
        for opt in schema:
            assert opt["name"]
            assert opt["type"]


def test_derived_labels_and_lookups():
    p = probe()
    for name in p.video_encoder_picks[:5]:
        label = codec_label(name)
        assert (label and label.lower() != name.lower()) or name in label
    assert can_encode("libx264") == ("libx264" in p.encoders)
    # Formats derive from muxer extensions + encodable audio codecs.
    assert can_encode_format("mp3") == ("libmp3lame" in p.encoders or "mp3" in p.encoders)
    assert can_encode_format("definitely-not-a-format") is False


def test_no_handwritten_codec_tables_in_screens():
    """AST scan: no codec-name string literals in src/screens/.

    Format names that collide with codec names (mp3/aac/flac/opus/ogg/gif/
    wav/m4a) are legitimate container keys — excluded via the wheel's own
    format names and extensions. license_view.py's native-component table is
    display text naming the shipped payload, not a capability table.
    """
    p = probe()
    format_keys: set[str] = set()
    for name, meta in p.format_meta.items():
        format_keys.add(name.lower())
        format_keys.update(e.lower() for e in meta.get("extensions", []))
    allow_list = {"license_view.py"}
    offenders: dict[str, list[tuple[str, int]]] = {}
    for fname in sorted(glob.glob(str(SRC / "screens" / "*.py"))):
        basename = Path(fname).name
        if basename in allow_list:
            continue
        tree = ast.parse(Path(fname).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                value = node.value
                if value in av.codecs_available and value.lower() not in format_keys:
                    offenders.setdefault(basename, []).append((value, node.lineno))
    assert offenders == {}, f"hand-written codec literals crept back: {offenders}"
