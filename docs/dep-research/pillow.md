# Pillow 12.3.0 — Complete API Reference

Import name: `PIL` (fork of the Python Imaging Library). `PIL.__version__ == "12.3.0"`.
Compiled core: `_imaging.cp314-win_amd64.pyd` (`Image.core`, `PILLOW_VERSION == "12.3.0"`;
version mismatch raises `ImportError`). Companion extensions in this wheel:
`_imagingft` (FreeType), `_imagingcms` (LittleCMS2), `_webp`, `_avif`,
`_imagingmath`, `_imagingmorph`, `_imagingtk`. For the C layer, rely on the `.py`
wrappers, docstrings, `__version__`, `PIL._util`, and `.pyi` hints — as instructed.

## Files

Package dir: `.venv/Lib/site-packages/PIL` — 115 entries (excluding `__pycache__`).
Every `.py`/`.pyi` was read; priority modules read in full, the rest via
signature/docstring sweep. No `SvgImagePlugin.py` exists (confirmed by listing) —
SVG is **not** supported by Pillow.

Core / most-used:

| File | Lines | Role |
|---|---|---|
| `Image.py` | 4385 | `Image` class, `open`/`new`/`frombytes`/`frombuffer`/`fromarray`, enums, registries |
| `ImageOps.py` | 749 | Ready-made ops (`exif_transpose`, `fit`, `contain`, `pad`, `invert`, …) |
| `ImageDraw.py` | 1002 | `ImageDraw` shapes + text rendering |
| `ImageFont.py` | 1330 | `truetype`, `FreeTypeFont`, `load_default` bitmap + Aileron FreeType fallback |
| `ImageFilter.py` | 617 | Blur/sharpen/edge/rank filters, `Color3DLUT` |
| `ImageEnhance.py` | ~115 | `Color`/`Contrast`/`Brightness`/`Sharpness.enhance(factor)` |
| `ImageChops.py` | 311 | Channel arithmetic (`difference`, `multiply`, `screen`, …) |
| `ImageMode.py` | small | `getmode(mode) -> ModeDescriptor(basemode, basetype, bands, typestr)` |
| `ImageCms.py` | 1078 | LittleCMS2 ICC transforms (`profileToProfile`, `buildTransform`, …) |
| `ExifTags.py` | 384 | `Base` (~200 tags), `GPS`, `Interop`, `IFD`, `LightSource` enums + `TAGS`/`GPSTAGS` dicts |
| `TiffTags.py` | 566 | `TagInfo`, `lookup(tag, group)` + full TIFF tag table (`_populate`) |
| `ImageSequence.py` | ~110 | `Iterator`, `all_frames(im, func)` |
| `ImageFile.py` | 938 | `ImageFile`, `Parser` (incremental `feed`/`close`), `PyDecoder`/`PyEncoder` |
| `features.py` | 343 | `check_module/codec/feature`, `version_*`, `get_supported*`, `pilinfo` |
| `__init__.py` | 88 | `__version__`, `UnidentifiedImageError`, `_plugins` list (46 plugins) |
| `_util.py` | tiny | `is_path(f)`, `DeferredError` |
| `ImageColor.py` | 320 | `getrgb(color)`, `getcolor(color, mode)` (CSS names/hex) |
| `ImagePalette.py` | 290 | `ImagePalette`, `raw/getcolor`, `make_linear_lut/make_gamma_lut/negative/random/sepia/wedge/load` |
| `ImageStat.py` | ~170 | `Stat(image, mask)` → `extrema/count/sum/sum2/mean/median/rms/var/stddev` |
| `ImageMath.py` | 314 | `lambda_eval`/`unsafe_eval`, `_Operand` arithmetic on `I`/`F` images |
| `ImageTransform.py` | ~140 | `AffineTransform/PerspectiveTransform/ExtentTransform/QuadTransform/MeshTransform` handlers |
| `ImageDraw2.py` | ~240 | Vector-style `Draw` with `Pen`/`Brush`/`Font` (WCK legacy) |
| `ImageMorph.py` | 317 | `MorphOp` + `LutBuilder` (erosion/dilation/edge) on `L` images |
| `ImagePath.py` | — | Path storage used by `ImageDraw.shape`/`polygon` |
| `ImageGrab.py` | — | Screen capture (Windows/macOS only; **not mobile**) |
| `ImageShow.py` | 367 | OS viewer dispatch (**not mobile**) |
| `ImageTk.py` / `ImageQt.py` / `ImageWin.py` | — | Tk/Qt/Win bindings — **irrelevant to Flet** |
| `PSDraw.py` | — | PostScript drawing (**irrelevant**) |
| `JpegPresets.py` | — | `presets` dict: `web_low/medium/high/very_high/maximum`, `low/medium/high/maximum` for `quality=`/`subsampling=`/`qtables=` |
| `ContainerIO.py` / `TarIO.py` | — | `ContainerIO`, `TarIO` partial-file readers |
| `FontFile.py` / `BdfFontFile.py` / `PcfFontFile.py` | — | Bitmap-font compilers for `ImageFont.load` |
| `GdImageFile.py` / `WalImageFile.py` / `PaletteFile.py` / `GimpGradientFile.py` / `GimpPaletteFile.py` | — | Legacy format helpers |
| `PdfParser.py` | 1092 | Low-level PDF xref parser backing `PdfImagePlugin` |
| `__main__.py` / `report.py` | tiny | `python -m PIL` → `features.pilinfo()` |
| `_typing.py` / `py.typed` | — | Public typing helpers; package ships inline types |
| Stubs | — | `_imaging.pyi` (empty), `_avif.pyi`, `_imagingcms.pyi`, `_imagingft.pyi`, `_imagingmath.pyi`, `_imagingmorph.pyi`, `_imagingtk.pyi`, `_webp.pyi` |

Image plugins registered in `__init__._plugins` (46): Avif, Blp, Bmp, BufrStub,
Cur, Dcx, Dds, Eps, Fits, Fli, Fpx, Ftex, Gbr, Gif, GribStub, Hdf5Stub, Icns,
Ico, Im, Imt, Iptc, Jpeg, Jpeg2K, McIdas, Mic, Mpeg, Mpo, Msp, Palm, Pcd, Pcx,
Pdf, Pixar, Png, Ppm, Psd, Qoi, Sgi, Spider, Sun, Tga, Tiff, WebP, Wmf, Xbm,
Xpm, XVThumb. Extension → plugin map lives in `Image._EXTENSION_PLUGIN`
(`.jpg/.jpeg/.png/.apng/.gif/.webp/.avif/.bmp/.tif/.tiff/.ico/.dds/.qoi`…).

## Metadata

From `pillow-12.3.0.dist-info/METADATA` (+ `WHEEL`, `licenses/LICENSE`, `RECORD`):

- **Name / version**: `pillow 12.3.0`. `Summary`: "Python Imaging Library (fork)".
- **Requires-Python**: `>=3.10` (app runs 3.14 — OK). Wheel tag:
  `cp314-cp314-win_amd64` (local dev wheel; `uv.lock` also pins Android
  `cp314-cp314` iOS/manylinux/musllinux/win wheels for the mobile build).
- **License**: `License-Expression: MIT-CMU`; `licenses/LICENSE` text opens
  "Copyright © 1997-2011 by Secret Labs AB … Pillow … Copyright © 2010 by
  Jeffrey 'Alex' Clark" under the MIT-CMU License. Permissive; shippable in-app.
- **Optional extras** (all opt-in): `docs` (furo/olefile/sphinx…), `fpx`+`mic`
  (olefile), `tests` (pytest…).
- **Dependency position**: `pinned-deps.txt:60` → `pillow==12.3.0`;
  `deps-tree.txt:34` → `├── pillow v12.3.0` (top-level, not transitive).
  **Not** in `pyproject.toml:7-21` `dependencies` (which lists
  `av/flet*/…`) — Pillow arrives via the lockfile/pinned-deps dev tree, same
  status the `tools/make_icons.py:1` header claims ("dev-only Pillow").
  For v1.0 decide: promote to `pyproject.toml` if any runtime use lands.

Runtime feature flags (measured in the project venv via `PIL.features`,
`Image.core.PILLOW_VERSION == "12.3.0"`):

- Codecs (`get_supported_codecs()`): `['jpg', 'jpg_2000', 'zlib', 'libtiff']` —
  JPEG libjpeg-turbo `8.0`, zlib `1.3.1.zlib-ng`, libtiff `4.7.1`.
- Modules (`get_supported_modules()`): `['pil', 'tkinter', 'freetype2',
  'littlecms2', 'webp', 'avif']` — FreeType `2.14.3`, LittleCMS2 `2.19`,
  WebP decoder `1.6.0`, AVIF libavif `1.4.2`.
- Extra features (`get_supported_features()`): `['libjpeg_turbo', 'zlib_ng']`.
  NOT compiled in: `mozjpeg`, `raqm` (→ bidirectional/complex-script text falls
  back to `Layout.BASIC`), `libimagequant` (→ `Quantize.LIBIMAGEQUANT`
  unavailable), `xcb`.
- Static vs runtime version caveat (from `features.pilinfo` source): `pil` and
  `jpg` versions are compile-time; the rest are runtime-loaded.

## Module-by-module API

### `PIL.Image` — the world

**Modes** (`MODES`, `ImageMode.getmode`): `"1", "CMYK", "F", "HSV", "I",
"I;16", "I;16B", "I;16L", "I;16N", "L", "LA", "La", "LAB", "P", "PA", "RGB",
"RGBA", "RGBa", "RGBX", "YCbCr"`. Helpers: `getmodebase(mode) -> "L"|"RGB"`,
`getmodetype(mode) -> "L"|"I"|"F"`, `getmodebandnames(mode)`, `getmodebands(mode)`.
Memory-map-friendly raw modes `_MAPMODES = ("L","P","RGBX","RGBA","CMYK","I;16","I;16L","I;16B")`.
Premultiplied variants `La`/`RGBa` exist because `resize`/`reduce` on
`LA`/`RGBA` convert through them internally.

**Enums** (also mirrored as module ints for back-compat):

```python
class Transpose(IntEnum):  # Image.transpose()
    FLIP_LEFT_RIGHT = 0
    FLIP_TOP_BOTTOM = 1
    ROTATE_90 = 2
    ROTATE_180 = 3
    ROTATE_270 = 4
    TRANSPOSE = 5
    TRANSVERSE = 6


class Transform(IntEnum):  # Image.transform()
    AFFINE = 0
    EXTENT = 1
    PERSPECTIVE = 2
    QUAD = 3
    MESH = 4


class Resampling(IntEnum):  # resize/thumbnail/fit/contain/...
    NEAREST = 0
    BOX = 4
    BILINEAR = 2
    HAMMING = 5
    BICUBIC = 3
    LANCZOS = 1


class Dither(IntEnum):
    NONE = 0
    ORDERED = 1
    RASTERIZE = 2
    FLOYDSTEINBERG = 3  # default


class Palette(IntEnum):
    WEB = 0
    ADAPTIVE = 1


class Quantize(IntEnum):
    MEDIANCUT = 0
    MAXCOVERAGE = 1
    FASTOCTREE = 2
    LIBIMAGEQUANT = 3
```

**Open / create**:

```python
Image.open(fp, mode="r", formats=None) -> ImageFile  # lazy; raises FileNotFoundError /
    # UnidentifiedImageError / ValueError(bad mode|StringIO) / TypeError(formats type)
Image.new(mode, size, color=0) -> Image  # color str/int/tuple/None(uninit); P+RGB tuple builds palette
Image.frombytes(mode, size, data, decoder_name="raw", *args) -> Image  # copy
Image.frombuffer(mode, size, data, decoder_name="raw", *args) -> Image  # zero-copy view;
    # for "raw" pass ("raw", mode, 0, 1); shares memory for L/RGBX/RGBA/CMYK; readonly=1
Image.fromarray(obj, mode=None) -> Image  # numpy; mode inferred
Image.fromarrow(obj, mode=None) -> Image  # Arrow C interface
Image.fromqimage(im) / Image.fromqpixmap(im)  # Qt only
Image.blend(im1, im2, alpha) / Image.composite(image1, image2, mask) /
    Image.alpha_composite(im1, im2)  # module-level; im1/im2 RGBA|LA, same size
Image.eval(image, *funcs) -> Image
```

`open()` reads 16 prefix bytes, lazy-imports the plugin for the extension, runs
`accept(prefix)` probes, then `_decompression_bomb_check(im.size)` against
`MAX_IMAGE_PIXELS = 1024*1024*1024//4//3` (~89.5 MP for 24-bit) — over-limit
raises `DecompressionBombWarning/Error`. `ImageFile.LOAD_TRUNCATED_IMAGES = True`
tolerates truncated PNGs.

**`Image` instance essentials** (all verified in `Image.py`):

```python
im.size/width/height/mode/format/info/palette/n_frames/is_animated
im.load() -> PixelAccess | None; im.verify(); im.close()
im.copy(); im.convert(mode=None, matrix=None, dither=None, palette=Palette.WEB, colors=256)
im.quantize(colors=256, method=None, kmeans=0, palette=None, dither=FLOYDSTEINBERG)
im.resize(size, resample=None(BICUBIC; P/1 force NEAREST), box=None, reducing_gap=None)
im.reduce(factor, box=None)                      # integer-factor fast path
im.thumbnail(size, resample=BICUBIC, reducing_gap=2.0)  # IN PLACE, aspect-preserving, returns None
im.crop(box=None); im.transpose(Transpose.*); im.transform(size, method, data=None,
    resample=NEAREST, fill=1, fillcolor=None); im.effect_spread(distance)
im.rotate(angle, resample=NEAREST, expand=False, center=None, translate=None, fillcolor=None)
    # angle deg CCW; 90/180/270 fast-path via transpose when no center/translate;
    # expand grows canvas; P/1 force NEAREST
im.filter(ImageFilter.*); im.split() -> tuple[Image,...]; im.getchannel(ch)
im.merge? (module-level via Image.merge(mode, bands)); im.getbands/getbbox(alpha_only=True)/
    getcolors(maxcolors=256)/getdata(band=None)/getextrema/getxmp/getexif/getpalette(rawmode="RGB")/
    getpixel/getprojection/histogram(mask, extrema)/entropy(mask, extrema)
im.paste(im|color, box=None, mask=None)  # mask in 1/L/LA/RGBA/RGBa; 4-tuple box must match size
im.putalpha(Image|int); im.putdata(data, scale=1.0, offset=0.0); im.putpalette(data, rawmode="RGB")
im.putpixel(xy, value); im.remap_palette(dest_map, source_palette=None)
im.point(lut|func|ImagePointHandler, mode=None); im.alpha_composite(im2, dest=(0,0), source=(0,0))
im.draft(mode, size) -> (bands, (x0,y0,x1,y1), (sx,sy))|None  # JPEG reader fast-path for thumbnail()
im.seek(frame)/tell(); im.show(title=None); im.save(fp, format=None, **params)
im.tobytes(encoder_name="raw", *args); im.tobitmap(name="image"); im.getim()
im.apply_transparency(); im.has_transparency_data; im.get_child_images()
im._repr_png_/_repr_jpeg_  # notebook previews
```

`save(fp, format=None, **params)`: format guessed from extension (`EXTENSION`
registry) else `ValueError`; unknown writer options silently ignored; `save_all`
selects `SAVE_ALL` handler (GIF/PNG-APNG/WebP/TIFF); per-frame `encoderinfo`
dict supported; writing over the open source path forces `_ensure_mutable()`;
partial-file failure removes a newly created target. Common `**params`:
`quality, optimize, progressive/progression, subsampling, qtables, dpi,
icc_profile, exif (bytes|Image.Exif), xmp, comment, save_all, append_images,
duration, loop, disposal, transparency, compress_level, lossless`.

**Per-format save/open notes**:

- **JPEG** (`JpegImagePlugin._save` + `JpegPresets.presets`): writable modes
  `RAWMODE`-limited (`L/RGB/CMYK…`; raises `OSError("cannot write mode … as JPEG")` —
  convert `RGBA→RGB` first). Params: `quality=int|-1|preset-name|"keep"`,
  `subsampling={0,1,2,"4:4:4","4:2:2","4:2:0","keep",preset}`, `qtables`, `optimize`,
  `progressive/progression`, `smooth`, `keep_rgb`, `streamtype`,
  `restart_marker_blocks/rows`, `dpi`, `comment`, `exif` (≤65533 B else
  `ValueError`), `xmp`, `icc_profile` (chunked), `extra`. Open side records
  `jfif_version/dpi/exif/icc_profile/comment/progressive/progression`;
  `get_sampling(im)` reads chroma sampling.
- **PNG** (incl. **APNG** save_all): `optimize`, `compress_level (-1..9)`,
  `dpi`, `transparency`, `interlace`, `pnginfo (PngInfo chunk container)`,
  `icc_profile`, `exif`, `xmp`, `comment`, plus APNG `save_all=True,
  append_images=[…], duration (ms|list), loop, disposal, blend`. Open side parses
  `icc_profile/interlace/transparency/dpi/text/exif/xmp/loop/duration/disposal/blend`.
- **WebP** (`WebPImagePlugin`, needs `_webp`, present `1.6.0`): `quality=80`,
  `lossless=False`, `alpha_quality=100`, `method=0`, `minimize_size`, `kmin/kmax`,
  `icc_profile/exif/xmp`, animated `save_all/append_images/duration/loop`.
  Open exposes `loop/background/duration/timestamp/icc_profile/exif/xmp`,
  `is_animated`, `n_frames`.
- **GIF**: open records `version/background/duration/disposal/comment/transparency/
  interlace`; save honors `save_all/append_images/duration/loop/disposal/
  transparency/interlace/palette/comment/include_color_table`. Palette
  optimization built in.
- **AVIF** (`AvifImagePlugin`, needs `_avif`, present `1.4.2`): `quality`,
  `subsampling`, `speed/tile_rows_log2/tile_cols_log2`, `icc_profile/exif/xmp`,
  animated save_all; `DECODE_CODEC_CHOICE`/`DEFAULT_MAX_THREADS` module globals.
- **BMP/ICO/ICNS/TIFF/JPEG2000/QOI/PPM/TGA/SGI/PSD/etc.**: registered; TIFF has
  the richest tag/metadata path (`TiffTags.lookup`). PDF/EPS are rasterize-on-open
  (Ghostscript may be required for EPS).

**Exceptions**: `UnidentifiedImageError(OSError)`, `DecompressionBombError`,
`DecompressionBombWarning`, `ImageCms.PyCMSError`, std `OSError/ValueError/TypeError`.

### `ImageOps` — one-liners that prevent bugs

```python
exif_transpose(image, *, in_place=False) -> Image | None  # applies+strips Orientation 1..8; in_place=True returns None
fit(image, size, method=BICUBIC, bleed=0.0, centering=(0.5,0.5))  # resize+crop to exact size
contain(image, size, method=BICUBIC)  # max-fit preserving ratio
cover(image, size, method=BICUBIC)    # min-cover preserving ratio
pad(image, size, method=BICUBIC, color=None, centering=(0.5,0.5))
expand(image, border=0, fill=0)       # add border; border int|2|4-tuple
crop(image, border=0); scale(image, factor, resample=BICUBIC)  # factor>0 else ValueError
flip/mirror/grayscale/invert(image); posterize(image, bits 1-8); solarize(image, threshold=128)
autocontrast(image, cutoff=0|tuple, ignore=None, mask=None, preserve_tone=False)
equalize(image, mask=None)  # P auto-converted to RGB
colorize(image(L), black, white, mid=None, blackpoint=0, whitepoint=255, midpoint=127)
deform(image, deformer.getmesh(image), resample=BILINEAR)
```

`_lut`-backed ops raise `NotImplementedError` on `P` and `OSError` on exotic modes —
`convert("RGB"/"L")` first where needed.

### `ImageDraw` — 2D drawing

`Draw(im, mode=None) -> ImageDraw`; methods:
`arc(xy,start,end,fill,width=1)`, `bitmap(xy,bitmap,fill)`,
`chord/ellipse(xy,fill,outline,width=1)`, `circle(xy,radius,fill,outline,width=1)`,
`line(xy,fill,width=1,joint=None|"curve")`, `shape/pieslice/polygon/
regular_polygon/rectangle/rounded_rectangle(xy,…,fill,outline,width)`,
`point(xy,fill)`, `text(xy,text,fill,font,anchor,spacing=4,align="left",
direction,features,language,stroke_width=0,stroke_fill,embedded_color=False)`,
`multiline_text`, `textlength/textbbox/multiline_textbbox`, `floodfill(xy,value,
border=None,thresh=0)`. Colors: `_Ink` int|tuple|str (CSS via `ImageColor`).
`ImageDraw2` offers `Pen(color,width,opacity)/Brush/Font` + vector `Draw`.

### `ImageFont` — text fonts

```python
truetype(font, size=10, index=0, encoding="", layout_engine=None) -> FreeTypeFont
load(filename) / load_path(filename)  # bitmap .pil fonts
load_default() -> FreeTypeFont|ImageFont  # Aileron, scalable via size=
load_default_imagefont()                 # legacy bitmap
Layout: BASIC=0, RAQM=1  # RAQM unavailable here (no raqm feature) → non-English shaping is BASIC
FreeTypeFont: getname/getmetrics/getlength/getbbox/getmask/getmask2/
    font_variant/size/index/encoding/layout_engine,
    get_variation_names/set_variation_by_name/get_variation_axes/set_variation_by_axes
TransposedFont(font, orientation)  # WRITEMODE helper
```

Windows note (docstring): FreeType keeps the file open; ≤512 C handles — copy to
memory (`BytesIO`) when opening many fonts.

### `ImageFilter` — kernels

`im.filter(f)`: builtin `BLUR/CONTOUR/DETAIL/EDGE_ENHANCE/EDGE_ENHANCE_MORE/
EMBOSS/FIND_EDGES/SHARPEN/SMOOTH/SMOOTH_MORE`; parameterized
`GaussianBlur(radius=2)`, `BoxBlur(radius)`, `UnsharpMask(radius=2, percent=150,
threshold=3)`, `Kernel(size, kernel, scale=None, offset=0)`,
`RankFilter(size,rank)` → `MedianFilter/MinFilter/MaxFilter/ModeFilter(size=3)`,
`Color3DLUT(size, table, channels=3, target_mode=None)` + `Color3DLUT.generate(
size, callback, channels=3, target_mode=None)` + `.transform(callback, with_normals=False)`.

### `ImageEnhance` / `ImageChops` / `ImageStat` / `ImageMath`

```python
ImageEnhance.Color/Contrast/Brightness/Sharpness(image).enhance(factor)
    # 1.0 = original; 0.0 = degenerate (B&W / gray / black / blurred)
ImageChops: constant/duplicate/invert/lighter/darker/difference/multiply/screen/
    soft_light/hard_light/overlay/add(scale,offset)/subtract/add_modulo/
    subtract_modulo/logical_and/or/xor/blend(alpha)/composite/mask/offset(xoffset,yoffset)
ImageStat.Stat(image, mask=None): extrema/count/sum/sum2/mean/median/rms/var/stddev
ImageMath.lambda_eval(expr, **images) / unsafe_eval(expr, **images)  # I/F-mode arithmetic
```

### Channels / palettes / color

`split()/merge(mode, bands)/getchannel()`; `convert("P", palette=ADAPTIVE,
colors=256)`; `quantize(method=MEDIANCUT|MAXCOVERAGE|FASTOCTREE|LIBIMAGEQUANT*)`
(*unavailable — no libimagequant; RGBA forces FASTOCTREE);
`ImagePalette.{raw,make_linear_lut,make_gamma_lut,negative,random,sepia,wedge,load}`;
`ImageColor.getrgb/getcolor`; `ImageCms.profileToProfile(im, in, out,
renderingIntent=PERCEPTUAL, outputMode, inPlace, flags)` + `buildTransform/
buildProofTransform/applyTransform/getOpenProfile/createProfile/getProfile*/isIntentSupported`.

### Sequences / animation / metadata

`ImageSequence.Iterator(im)` (`seek`-based, `IndexError→StopIteration`);
`all_frames(im|list, func)` (restores position; returns copies);
frame protocol `seek/tell/n_frames/is_animated/duration/loop/disposal`;
`getexif() -> Exif` (`_get_merged_dict()`, `tobytes()`, `hide_offsets()`),
`getxmp()`, `tag_v2`; `ExifTags.Base.Orientation==0x0112` values 1–8 with the
`exif_transpose` method map `{2:FLIP_LR,3:R180,4:FLIP_TB,5:TRANSPOSE,6:R270,
7:TRANSVERSE,8:R90}`; `ExifTags.{GPS,Interop,IFD,LightSource}` + `TAGS/GPSTAGS`;
`TiffTags.lookup(tag, group)`; `ImageFile.Parser().feed(data)/close()` for
streaming decodes.

## App usage & correctness

Only two Pillow touchpoints exist today (`grep -rn PIL src tools tests`):

**(a) Correct usage — `tools/make_icons.py` (entire file, 64 lines)**. Dev-only
icon pipeline: `Image.open(src)` → `_pad_square` (`convert("RGBA")`,
`Image.new("RGBA", (side,side), (0,0,0,0))`, centered `paste`) →
`_adaptive_foreground` (`resize(…, Image.LANCZOS)`, **correct**: LANCZOS for
downscale; mask-`paste(glyph, center, glyph)` preserving alpha) →
`save(src, optimize=True)`. No EXIF/JPEG pitfalls (RGBA PNG in/out). Correct.

**(b) No active misuse** — because there is no runtime use: `src` never imports
PIL. Thumbnailing is PyAV-only: `src/services/engine_service.py:142
_mjpeg_bytes` (PyAV `reformat` + mjpeg encode, no Pillow) and
`:1680 thumbnail_strip` (single-pass demux + disk cache). `src/screens/
cut_screen.py:116` consumes bytes; `result_screen.py:283` shows output via
`ft.Image`; `probe_screen.py:39` only labels `"attached_pic": "Cover"`.
`tests/test_previews.py:22-35` covers the PyAV strip. So misuse classes to avoid
when adopting: (1) `resize` default BICUBIC on huge photos instead of
`thumbnail(reducing_gap=…)`/`draft`; (2) `save(...".jpg")` on RGBA (raises
`OSError`) instead of `convert("RGB")`; (3) `Image.open` without
`exif_transpose` (rotated phone photos); (4) `thumbnail()` mutating a shared
image (it is in-place — `copy()` first); (5) `MAX_IMAGE_PIXELS` bombs on
user-supplied panoramas (wrap in try/except).

Dependency note: Pillow is pinned (`pinned-deps.txt:60`, `deps-tree.txt:34`,
`uv.lock:584`) but absent from `pyproject.toml:7-21` — consistent with
dev-only. Any runtime adoption below must add it to `dependencies`.

## Underused APIs to adopt

Concrete v1 proposals, each one Pillow call away:

1. **EXIF orientation everywhere an image is shown** — `result_screen.py:283`
   (`ft.Image(src=out_path)`) and any Convert-screen image output:
   `ImageOps.exif_transpose(Image.open(p))` before display/save. Zero-dependency,
   fixes sideways phone photos.
2. **Video-poster thumbnails via PyAV → Pillow** — in
   `engine_service.py:142/1680`, replace/augment mjpeg-bytes with
   `Image.frombuffer("RGB", (w,h), frame.to_ndarray(format="rgb24"))` (or
   `frombytes`) then `thumbnail((w,h))` + `save(buf, "JPEG", quality=…)` /
   `"WEBP"`. Unifies the Cut strip, share posters, and result previews on one
   resampler (LANCZOS/BICUBIC + `reducing_gap`).
3. **Convert-screen image tools**: rotate/normalize (`transpose`/`rotate(expand=True)`),
   `ImageOps.{autocontrast,equalize,fit,contain,pad}`, `ImageEnhance` brightness/
   contrast, `convert("L")` grayscale export refusals — all client-side, no FFmpeg
   round-trip for pure-image ops.
4. **WebP conversion + metadata hygiene**: `save("….webp", quality, method,
   lossless)` for posters/covers; strip/normalize with `getexif()`/`tobytes()`,
   preserve-or-drop `icc_profile`/`xmp` deliberately on export.
5. **Icon/splash QA checks** (extend `tools/make_icons.py`): assert sizes/modes,
   `getbbox(alpha_only=True)` for glyph-centering, `ImageStat` for contrast,
   APNG/WebP export smoke tests.
6. **Cover-art extraction path**: `probe_screen.py:39 attached_pic` currently a
   label — `av` attachment → `BytesIO` → `Image.open` → `exif_transpose` →
   `thumbnail` is the 5-line implementation.

## Gotchas

- `thumbnail()` is **in-place** (returns `None`); `resize/fit/contain` return copies.
- `resize` on `P`/`1` silently forces `NEAREST`; convert first for smooth art.
- JPEG cannot save `RGBA/P` (`OSError`); `convert("RGB")`. JPEG-on-transparency
  pastes black unless composited onto a background first.
- `save()` ignores unknown kwargs silently — typos in `quality=` etc. fail open.
- `open()` is lazy — wrap `load()`/`verify()` + `exif_transpose` early; keep the
  source `fp` alive or `copy()` (file-handle lifetime bug source on mobile shares).
- `MAX_IMAGE_PIXELS` (~89.5 MP) trips on panoramas; catch
  `DecompressionBombError` and downsample via `draft`/`reduce`.
- `putalpha(int)` broadcasts; `paste(mask=…)` needs `1/L/LA/RGBA/RGBa` mask.
- `quantize(LIBIMAGEQUANT)` and `Layout.RAQM` unavailable in this wheel.
- `ImageGrab/ImageShow/ImageTk/ImageQt/ImageWin` are desktop-only — do not use
  in the Flet mobile path. No SVG support at all.
- Android packaging: Pillow ships cp314 Android wheels in `uv.lock`, but confirm
  `flet build apk` bundles `_imaging/_webp/_avif/_imagingft/_imagingcms` `.so`s;
  keep Pillow out of the hot path (decode/resize on background isolates).
