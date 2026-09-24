# qrcode 8.2 — Complete API Reference

QR code generation library (Lincoln Loop `python-qrcode`). Installed at
`<repo>\.venv\Lib\site-packages\qrcode`
(Python 3.14 venv, Flet 1.0 app, preparing v1.0).

## Files

Package root (`qrcode/`), `__pycache__` skipped:

| File | Purpose |
|---|---|
| `__init__.py` | Public surface: re-exports `QRCode`, `make`, `ERROR_CORRECT_*`, `image`; `run_example()` demo |
| `main.py` | Core: `make()`, `QRCode`, `ActiveWithNeighbors`, mask/box/border validators |
| `base.py` | Reed–Solomon math: `EXP_TABLE`/`LOG_TABLE`, `gexp`/`glog`, `Polynomial`, `RSBlock`, `rs_blocks()`, `RS_BLOCK_TABLE` |
| `LUT.py` | Precomputed `rsPoly_LUT` error-correction polynomials |
| `constants.py` | Error-correction level constants |
| `exceptions.py` | `DataOverflowError` only |
| `util.py` | Encoding modes, `QRData`, `BitBuffer`, chunk optimizer, mask funcs, lost-point scoring, `create_data`/`create_bytes` |
| `console_scripts.py` | `qr` CLI (`main()`): tty-vs-pipe output, `--factory/--factory-drawer/--optimize/--error-correction/--ascii/--output` |
| `release.py` | Maintainer-only zest.releaser hook (`update_manpage`); not runtime API |
| `compat/__init__.py` | Empty |
| `compat/etree.py` | Prefers `lxml.etree`, falls back to `xml.etree.ElementTree` (aliased `ET`) |
| `compat/png.py` | Optional `from png import Writer as PngWriter`, else `PngWriter = None` |
| `image/__init__.py` | Empty (namespace only) |
| `image/base.py` | `BaseImage`, `BaseImageWithDrawer` (drawer plumbing, `pixel_box`, `is_eye`, `check_kind`) |
| `image/pil.py` | `PilImage` (default factory when Pillow present) |
| `image/pure.py` | `PyPNGImage` (+ `PymagingImage` alias, kept for back-compat) |
| `image/svg.py` | `SvgFragmentImage`, `SvgImage`, `SvgPathImage`, `SvgFillImage`, `SvgPathFillImage` |
| `image/styledpil.py` | `StyledPilImage` (module drawer + color mask + embedded logo) |
| `image/styles/__init__.py` | Empty |
| `image/styles/colormasks.py` | `QRColorMask` + 6 concrete masks (see below) |
| `image/styles/moduledrawers/__init__.py` | Re-exports PIL drawers for back-compat |
| `image/styles/moduledrawers/base.py` | `QRModuleDrawer` ABC (`drawrect`, `initialize`, `needs_neighbors`) |
| `image/styles/moduledrawers/pil.py` | 6 PIL drawers (see below) |
| `image/styles/moduledrawers/svg.py` | 6 SVG drawers (see below) |
| `tests/` | `test_qrcode.py`, `test_qrcode_pil.py`, `test_qrcode_pypng.py`, `test_qrcode_svg.py`, `test_script.py`, `test_util.py`, `test_example.py`, `test_release.py`, `consts.py` |
| `qrcode-8.2.dist-info/` | `METADATA`, `RECORD`, `WHEEL`, `INSTALLER`, `LICENSE`, `REQUESTED`, `entry_points.txt` |

> Layout note: the brief's `image/styling.py`, `image/mix.py`, `scripts?` do **not**
> exist in 8.2. Styling lives in `image/styledpil.py` + `image/styles/`; there is no
> `mix` module. The "full/vertical/horizontal mix" idea maps to the gradient
> **color masks** (`RadialGradiant` sic, `SquareGradiant` sic, `HorizontalGradiant`
> sic, `VerticalGradiant` sic — upstream typos preserved). There is no "dots"
> drawer by name; `CircleModuleDrawer` / `SvgCircleDrawer` is the dots look.

## Metadata

From `qrcode-8.2.dist-info/METADATA` (`RECORD` confirms `Scripts/qr.exe` shipped):

- **Name / version:** `qrcode 8.2` (changelog head: 8.2, 01 May 2025). Summary
  "QR Code image generator". Home-page `https://github.com/lincolnloop/python-qrcode`.
- **License:** `License: BSD`; classifiers `OSI Approved :: BSD License` (+ stray
  `Other/Proprietary License` classifier). `LICENSE` text is BSD-3-clause-style
  (Lincoln Loop, 2011) and notes the forked ancestor code was MIT (Kazuhiko Arase /
  pyqrnative). Commercial-app-safe permissive license; keep the attribution notice.
- **Requires-Python:** `>=3.9,<4.0` — fine on this repo's Python 3.14.
- **Dependencies — required vs extras (verified):**
  - REQUIRED (conditional): `colorama ; sys_platform == "win32"` — installed here
    (`colorama 0.4.6`) because the venv is Windows; the CLI imports it for TTY colors.
  - OPTIONAL extras only: `pillow (>=9.1.0) ; extra == "pil" or extra == "all"`,
    `pypng ; extra == "png" or extra == "all"`. `Provides-Extra: pil, png, all`.
  - `typing_extensions` is **not** a dependency (removed in 8.0; stdlib typing suffices
    on 3.9+). `colorama` is the only unconditional-on-Windows pin; there is no
    `pillow`/`typing_extensions` hard requirement.
  - Present in this venv: `PIL/` + `pillow-12.3.0.dist-info` exist (so PIL factories
    work), `pypng` dist-info does **not** exist (so `PyPNGImage` raises
    `ImportError: PyPNG library not installed` if selected).
- **Entry points** (`entry_points.txt`): one console script —
  `[console_scripts] qr = qrcode.console_scripts:main`. The command is **`qr`**,
  not `qrcode` (`qr "Some text" > test.png`, `qr --output=test.png "Some data"`).
- **Why installed:** transitive dev-tool dependency. `uv.lock` has
  `qrcode 8.2` (deps: win32 `colorama` only); `flet_cli-1.0.0.dist-info/METADATA`
  lists `Requires-Dist: qrcode>=7.4.2` (flet-cli uses it for project scaffolding
  templating). The app's own `pyproject.toml [project] dependencies`
  (`av, flet, flet-ads, flet-audio, flet-audio-recorder, flet-camera,
  flet-permission-handler, flet-video, httpx`) do **not** list qrcode, and
  `pinned-deps.txt` / `deps-tree.txt` show no qrcode line — it is **not** a runtime
  dependency and will not ship inside the mobile package unless explicitly added.

## Module-by-module API

### `qrcode/__init__.py` — public surface

```python
import qrcode

qrcode.QRCode  # from qrcode.main import QRCode
qrcode.make(...)  # shortcut -> image object
qrcode.ERROR_CORRECT_L / _M / _Q / _H
qrcode.image  # image-factory subpackage
qrcode.run_example(data="http://www.lincolnloop.com", *args, **kwargs)
```

### `qrcode.constants` — error-correction levels

```python
ERROR_CORRECT_L = 1  # ~7%  recoverable
ERROR_CORRECT_M = 0  # ~15% recoverable (default)
ERROR_CORRECT_Q = 3  # ~25% recoverable
ERROR_CORRECT_H = 2  # ~30% recoverable (REQUIRED for embedded logos)
```

Values are deliberately non-ordinal (they feed directly into type-info bits).

### `qrcode.main.QRCode` — the core class

```python
QRCode(
    version=None,
    error_correction=ERROR_CORRECT_M,
    box_size=10,
    border=4,
    image_factory=None,
    mask_pattern=None,
)
```

| Param | Default | Rules |
|---|---|---|
| `version` | `None` (auto-fit 1–40) | `int`; `util.check_version` raises `ValueError` outside 1–40 |
| `error_correction` | `ERROR_CORRECT_M` (0) | `int(...)`; pick L/M/Q/H constant |
| `box_size` | `10` | pixels per module; `<= 0` raises `ValueError` |
| `border` | `4` | boxes of quiet zone (spec minimum 4; `0` allowed); `< 0` raises `ValueError` |
| `image_factory` | `None` → auto: `PilImage` if Pillow importable else `PyPNGImage` | must be a `BaseImage` subclass (`assert`) |
| `mask_pattern` | `None` → auto-best of 0–7 | `int` 0–7; wrong type → `TypeError`, out of range → `ValueError` |

Methods:

```python
qr.add_data(data, optimize=20)
# data: str/bytes/int/etc (non-bytes str()-ified to UTF-8); QRData passed through.
# optimize: min run length worth re-encoding; 0 disables chunk optimization.

qr.make(fit=True)        # compile matrix; fit picks min version, else DataOverflowError
qr.make_image(image_factory=None, **kwargs)   # build image; forwards kwargs to factory
qr.get_matrix()          # list[list[bool]] WITH border; set border=0 first for raw modules
qr.print_ascii(out=None, tty=False, invert=False)  # cp437 half-block chars to any stream
qr.print_tty(out=None)   # ANSI-background TTY dump; raises OSError("Not a tty") if piped
qr.clear()               # reset data_list/modules (reuse object for new payload)
qr.best_fit(start=None) -> int                 # min version for current data_list
qr.best_mask_pattern() -> int (0-7)            # lowest lost_point mask
qr.active_with_neighbors(row, col) -> ActiveWithNeighbors  # 3x3 context NamedTuple
qr.is_constrained(row, col) -> bool
# internals (tinkerer-use): makeImpl, setup_position_probe_pattern,
#   setup_position_adjust_pattern, setup_timing_pattern, setup_type_info,
#   setup_type_number, map_data
qr.version               # property; auto best_fit() when None
qr.mask_pattern          # property with validation
```

`ActiveWithNeighbors` fields: `NW N NE W me E W…` (`SW S SE`); `bool(ctx)` == `ctx.me`.

`make_image` extras:

- Embedded-logo guard: passing `embedded_image`/`embedded_image_path`
  (incl. legacy `embeded_*` typo spellings) with `error_correction != H` raises
  `ValueError("Error correction level must be ERROR_CORRECT_H ...")`.
- When `image_factory.needs_drawrect`, iterates modules calling
  `drawrect(r, c)` or `drawrect_context(r, c, qr=qr)` when `needs_context`; when
  `needs_processing`, calls `im.process()` (SVG-path assembly, styled recolor/logo).

Module-level shortcut:

```python
qrcode.make(data=None, **kwargs)  # QRCode(**kwargs) + add_data + make_image
import qrcode

img = qrcode.make("Some data here")  # -> PilImage (Pillow installed)
img.save("some_file.png")
img = qrcode.make("Some data", image_factory=qrcode.image.svg.SvgPathImage)
```

Exceptions:

```python
from qrcode import exceptions

exceptions.DataOverflowError  # data doesn't fit even version 40 (best_fit hits 41)
# plus ValueError/TypeError/OSError from validators above
```

### `qrcode.util` — encoding internals (stable enough to use selectively)

```python
# Modes
MODE_NUMBER = 1; MODE_ALPHA_NUM = 2; MODE_8BIT_BYTE = 4; MODE_KANJI = 8
ALPHA_NUM = b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:"
NUMBER_LENGTH = {3: 10, 2: 7, 1: 4}

class QRData(data, mode=None, check_data=True)  # auto optimal_mode; len(); write(buffer); repr
def optimal_data_chunks(data, minimum=4)   # iterator of QRData; add_data(optimize=N) uses this
def optimal_mode(data) -> mode
def to_bytestring(data) -> bytes            # str(data).encode("utf-8") if not bytes
def mask_func(pattern: 0-7) -> callable     # lambda (i, j) -> bool
def check_version(version)                  # ValueError outside 1..40
def mode_sizes_for_version(version)         # SMALL <10 / MEDIUM <27 / LARGE
def length_in_bits(mode, version)
def pattern_position(version) -> list[int]  # alignment-pattern centers
def lost_point(modules) -> int              # mask-quality score (levels 1-4)
def create_data(version, error_correction, data_list) -> list[int]  # may raise DataOverflowError
def create_bytes(buffer, rs_blocks) -> list[int]
class BitBuffer()                           # put(num, length), put_bit, get, len
def BCH_type_info(data) / BCH_type_number(data) / BCH_digit(data)
BIT_LIMIT_TABLE[ec][version]                # capacity bits lookup
```

### Image factories

Base contract (`image/base.py`):

```python
class BaseImage:
    kind: str | None; allowed_kinds: tuple | None
    needs_context=False; needs_processing=False; needs_drawrect=True
    def __init__(self, border, width, box_size, *args, **kwargs)  # kwargs.pop("qrcode_modules")
    def drawrect(self, row, col) ...            # abstract
    def drawrect_context(self, row, col, qr)    # drawer-aware path
    def process(self)                           # post-pass (SvgPath / StyledPil)
    def save(self, stream, kind=None)           # stream path or file-like
    def pixel_box(self, row, col) -> ((x,y),(x1,y1))
    def new_image(self, **kwargs)               # abstract
    def get_image(self, **kwargs)               # underlying PIL img / ET element
    def check_kind(self, kind, transform=None)
    def is_eye(self, row, col) -> bool          # finder-pattern guard

class BaseImageWithDrawer(BaseImage):  # needs_context=True
    def __init__(self, *args, module_drawer=None, eye_drawer=None, **kwargs)
    # drawer: QRModuleDrawer instance OR alias string resolved via drawer_aliases
```

Concrete factories:

```python
# PIL (default while Pillow installed)
from qrcode.image.pil import PilImage

qr.make_image(fill_color="black", back_color="white")  # str names (lower-cased) or RGB tuples
qr.make_image(fill_color=(55, 95, 35), back_color=(255, 195, 235))
img.save(stream, format=None, **kwargs)  # kind defaults to "PNG"; __getattr__ proxies PIL Image
# back_color="transparent" -> RGBA mode; black-on-white fast-path uses mode "1"

# Pure-Python PNG (pypng — NOT installed here)
from qrcode.image.pure import PyPNGImage, PymagingImage  # latter = back-compat alias
# needs_drawrect=False; save() accepts path str or binary stream

# SVG — no Pillow needed
from qrcode.image.svg import (
    SvgFragmentImage,
    SvgImage,
    SvgPathImage,
    SvgFillImage,
    SvgPathFillImage,
)

# box_size 10 == 1mm; units()/unit_size handle mm conversion
# SvgImage.drawer_aliases = {"circle":..., "gapped-circle":..., "gapped-square":...}
# SvgPathImage (single <path>, ~30% smaller, no zoom gaps) is recommended
img.to_string(encoding="unicode")  # extra kwargs -> ET.tostring
qr.make_image(image_factory=SvgPathImage, attrib={"class": "qr"})  # kwargs -> root element
# SvgFillImage / SvgPathFillImage preset background="white"
```

Styled PIL (`image/styledpil.py`):

```python
from qrcode.image.styledpil import StyledPilImage

qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H)
img = qr.make_image(
    image_factory=StyledPilImage,
    module_drawer=RoundedModuleDrawer(),
    color_mask=RadialGradiantColorMask(),
    embedded_image_path="/path/to/logo.png",
)
# kwargs: color_mask=QRColorMask (default SolidFillColorMask()),
#   embedded_image=|PIL Image, embedded_image_path= (typo embeded_* still accepted),
#   embedded_image_ratio=0.25 (logo width / QR width),
#   embedded_image_resample=Image.Resampling.LANCZOS
```

PIL module drawers (`styles/moduledrawers/pil.py`):
`SquareModuleDrawer` (default), `GappedSquareModuleDrawer(size_ratio=0.8)`,
`CircleModuleDrawer` (dots look), `RoundedModuleDrawer(radius_ratio=1)`
(needs_neighbors), `VerticalBarsDrawer(horizontal_shrink=0.8)` (needs_neighbors),
`HorizontalBarsDrawer(vertical_shrink=0.8)` (needs_neighbors).

SVG module drawers (`styles/moduledrawers/svg.py`):
`SvgSquareDrawer`, `SvgCircleDrawer` (rect/circle tags, `size_ratio`),
`SvgPathSquareDrawer` (default for `SvgPathImage`),
`SvgPathCircleDrawer` (subpath arc strings).

Color masks (`styles/colormasks.py`):
`SolidFillColorMask(back_color, front_color)` (B&W fast-path skips masking),
`RadialGradiantColorMask(back/center/edge)`, `SquareGradiantColorMask(...)`,
`HorizontalGradiantColorMask(left/right)`, `VerticalGradiantColorMask(top/bottom)`,
`ImageColorMask(back_color, color_mask_path|color_mask_image)` (resized to QR;
4-tuple back_color enables transparency handling).

Custom drawer skeleton:

```python
from qrcode.image.styles.moduledrawers.base import QRModuleDrawer


class MyDrawer(QRModuleDrawer):
    needs_neighbors = True

    def initialize(self, img):
        super().initialize(img)
        ...

    def drawrect(self, box, is_active): ...
```

### `qrcode.console_scripts` — `qr` CLI

```
qr [--factory pil|png|svg|svg-fragment|svg-path|pymaging|<dotted.path>]
   [--factory-drawer <alias>] [--optimize N] [--error-correction L|M|Q|H]
   [--ascii] [--output FILE] [DATA]
# no DATA -> reads sys.stdin.buffer (bytes, surrogateescape)
# tty stdout (or --ascii) -> print_ascii; else image bytes to stdout.buffer
# --factory-drawer values come from the factory's drawer_aliases
#   (svg/svg-path: circle, gapped-circle, gapped-square)
```

Examples:

```bash
qr "Some text" > test.png
qr --output=test.png "Some data"
qr --factory=svg-path "Some text" > test.svg
qr --factory=svg "Some text" > test.svg
qr --ascii "Some data" > test.txt
echo -n "hello" | qr > hello.png
```

### Supporting modules

- `base.py`: `RSBlock(total_count, data_count)` NamedTuple,
  `rs_blocks(version, error_correction)`, Galois `gexp/glog`, `Polynomial`
  (`*`, `%`), `EXP_TABLE/LOG_TABLE`, `RS_BLOCK_OFFSET`, 40-version `RS_BLOCK_TABLE`.
- `LUT.py`: `rsPoly_LUT` precomputed generator polynomials.
- `compat`: `etree.ET` (lxml preferred), `png.PngWriter` (`None` when pypng absent).
- `release.py`: packaging-time manpage helper only.

## App usage & correctness

- **Chain:** `app pyproject dependencies` → no qrcode. `dev` group → `flet-cli`
  → `qrcode>=7.4.2` → resolved `qrcode 8.2` (+ win32 `colorama`). Verified in
  `uv.lock` (`name = "qrcode", version = "8.2"`, deps `[colorama win32]`), in
  `flet_cli-1.0.0.dist-info/METADATA` (`Requires-Dist: qrcode>=7.4.2`), and by
  absence in `deps-tree.txt`/`pinned-deps.txt`/app `dependencies`.
- **Direct usage in app:** none. Case-insensitive grep for `qrcode` across
  `src/`, `tests/`, `tools/` returns zero hits. No misuse is possible where there
  is no use; no dead import to remove.
- **Correctness notes for future use:**
  - Default factory resolves at call time: Pillow 12.3.0 is present so
    `qrcode.make(...)` returns `PilImage` today; on a Pillow-less target it would
    fall to `PyPNGImage` and fail here because `pypng` is not installed. Pin the
    factory explicitly (`image_factory=PilImage` or an SVG factory) rather than
    relying on the fallback.
  - No `__init__` version pin, no `RECORD` hash drift, no vendored copy.
    `Scripts/qr.exe` exists for dev-tool use.
  - Flet boundary: a search of the installed `flet` 1.0 package found **no**
    `QrCode` control class, so QR display must go through `ft.Image`
    (PNG bytes via `PilImage.save(BytesIO)` → `base64`/`Image(src_bytes=...)`, or an
    `Svg*` string rendered per Flet's SVG support) — qrcode is a *generator*, Flet
    owns the pixels on screen.
  - Deep-link base already configured: `[tool.flet.deep_linking] scheme="ffmpeg",
    host="app"` → payloads shaped like `ffmpeg://app/...` are routable.

## Underused APIs to adopt

All v1-sized, none currently used:

1. **About/Share screen QR (file URL / device pairing).**
   `qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=10, border=4)`;
   `qr.add_data(url)`; `qr.make_image(image_factory=PilImage)` → PNG bytes into
   `ft.Image`. SVG alternative (`SvgPathImage` + `to_string(encoding="unicode")`)
   for crisp print. Pairing payload = short token URL, not raw binary.
2. **Job-result sharing.** Encode the share link / job ID with `qrcode.make(link)`;
   `print_ascii(out=io.StringIO())` gives a log/console fallback for headless runs.
3. **Deep-link QR.** Payload `ffmpeg://app/<route>?job=<id>` (scheme/host from
   pyproject) at `ERROR_CORRECT_Q`+ so printed codes survive camera smudge; verify
   the app's route handler resolves the same path the QR encodes.
4. **Desktop↔mobile remote job control.** Short-lived pairing URL
   (`https://…/pair#token` or `ffmpeg://app/pair?token=…`); regenerate per session
   (`clear()` + `add_data()` on a reused `QRCode`, or fresh object), short expiry,
   `ERROR_CORRECT_H` if a logo is embedded.
5. **Branded codes.** `StyledPilImage` + `RoundedModuleDrawer` /
   `GappedSquareModuleDrawer` + gradient `*GradiantColorMask` + `embedded_image_*`
   (forces `ERROR_CORRECT_H`); test-scan on real devices — styled codes are
   explicitly "not guaranteed with all readers".
6. **Offline/dev tooling.** `qr --output=pair.png "ffmpeg://app/pair?token=…"` and
   `qr --factory=svg-path …` for docs; `qr.get_matrix()` (with `border=0`) feeds
   custom painters if a future canvas-based QR widget is preferred over `ft.Image`.

## Gotchas

- **Constant values are non-ordinal:** `L=1, M=0, Q=3, H=2`. Never persist/sort them
  as "low→high"; always use the symbolic names.
- **Embedded logo ⇒ H only.** Any `embedded_image*` kwarg with EC ≠ H raises
  `ValueError`. Styled/logo codes also deserve real-scanner testing.
- **Capacity failures raise `DataOverflowError`** (including `best_fit` running past
  version 40). Catch it when encoding user-controlled payloads; shorten the payload
  or lower EC (M over Q/H) before retrying.
- **Validators are strict:** `box_size <= 0` → `ValueError`; `border < 0` →
  `ValueError`; `mask_pattern` non-int → `TypeError`, outside 0–7 → `ValueError`;
  `version` outside 1–40 → `ValueError`; `print_tty` on a pipe → `OSError`.
- **`get_matrix()` includes the border** (default 4 modules of `False`); set
  `qr.border = 0` before calling for raw data. Border rows alias each other
  (`[[False]*width]*border`), so never mutate the returned matrix in place.
- **`optimize` default is 20, not 0/4:** `add_data` re-chunks alphanumeric/numeric
  runs ≥ 20 chars into tighter modes. Pass `optimize=0` for byte-exact single-chunk
  encoding; `util.optimal_data_chunks` otherwise yields multiple `QRData` segments.
- **PyPNG path is broken in this venv** (no `pypng` installed): `--factory=png` /
  `PyPNGImage` raises `ImportError`. Use PIL or SVG factories, or add the `png` extra.
- **CLI name is `qr`, not `qrcode`.** Stdin is read as bytes with
  `errors="surrogateescape"`; non-UTF-8 input round-trips as bytes.
- **SVG sizing:** `box_size=10` renders as 1 mm per module; `SvgPathImage` merges
  modules into one `<path>` (≈30% smaller, no inter-rect seams on zoom).
- **Color-mask API quirks:** gradient class names carry upstream typos
  (`Gradiant`); `ImageColorMask` resizes the mask image to the QR size on
  `initialize`; 4-tuple `back_color` switches transparency handling; the default
  B&W `SolidFillColorMask` short-circuits masking entirely (fast path).
- **Windows-only hard dep:** `colorama` installs only on `sys_platform=="win32"`;
  lockfiles for other platforms will not include it.
- **Not shipped to mobile:** adding any runtime QR feature means adding
  `qrcode` (and for PIL output, `pillow`) to app `dependencies` + `uv.lock`;
  today it arrives only via the dev-only `flet-cli` chain.
