# flet-platform-assets 1.0.0 — Complete API Reference

> Icon + splash asset generation for Flet builds. Pure render step (Pillow in,
> Pillow out, no filesystem, no prints) separated from a single `write()` that
> persists into a rendered Flutter project. Consumed by `flet build`
> (`flet_cli/commands/build_base.py`); importable standalone. Pillow is the
> only dependency.

## Files

Package dir: `.venv/Lib/site-packages/flet_platform_assets/` — 7 source files,
no template/data assets, no bundled images:

| File | Role |
|---|---|
| `__init__.py` | Public re-exports + `__all__` (27 names), package docstring with preview idiom |
| `_icons.py` | `render_icons`, platform specs, framing rules, macOS/Linux/web special cases |
| `_imaging.py` | Low-level compositing: resample-once, premultiplied alpha, masks, grids, save helpers |
| `_models.py` | Frozen dataclasses: `Target`, `AssetSpec`, `IconOptions`, `SplashOptions`, `RenderResult`, `RenderedAsset` |
| `_source.py` | `load_source`, `square`, `SourceError`, `MAX_SOURCE_SIZE` |
| `_splash.py` | `render_splash` for android/ios/web, Android 12 canvas, stale-file lists |
| `_write.py` | `write()` — the only filesystem writer |

(`__pycache__/*.pyc` and `*.dist-info/` excluded; nothing else ships.)

## Metadata

From `flet_platform_assets-1.0.0.dist-info/METADATA` (+`WHEEL`, `top_level.txt`, `INSTALLER`):

- **Name / version:** `flet-platform-assets 1.0.0`
- **Summary:** "Generate app icons and splash screens for every platform Flet builds for"
- **Author:** Appveyor Systems Inc. <hello@flet.dev>; Homepage/Repo/Docs → flet.dev
- **License:** `Apache-2.0` (License-Expression; no vendored LICENSE file in dist-info)
- **Requires-Python:** `>=3.10`
- **Dependencies:** exactly one — `pillow>=11.3.0`
- **Entry points:** none (no `entry_points.txt` in dist-info; library only, driven by `flet-cli`)
- **Wheel:** `py3-none-any`, pure lib, built by setuptools 84.0.0, installed via uv

## Module-by-module API

### `_source.py` — input normalisation

```python
MAX_SOURCE_SIZE = 2048  # sources larger than this are reduced ONCE, up front


class SourceError(Exception): ...  # unreadable/missing/truncated source


def load_source(path: str | Path) -> tuple[Image.Image, bool]:
    """Read + normalise to RGBA. Handles EXIF rotation, palette/CMYK → RGBA,
    animated (first frame wins), non-square (passed through, see square()),
    .ico/.icns multi-frame (largest frame taken, pre_rendered=True).
    Returns (image, pre_rendered). Raises SourceError."""


def square(img: Image.Image) -> tuple[Image.Image, str | None]:
    """Centre-pad non-square to square with transparency. Returns (image,
    warning-or-None). Stretching/cropping deliberately never done."""
```

Input contract: any Pillow-readable raster; **SVG is never decoded** (caller
drops it); `.ico`/`.icns` flag `pre_rendered=True` which skips the macOS grid.
Example: `src, pre = load_source("assets/icon.png")`.

### `_models.py` — options, specs, results

```python
@dataclass(frozen=True)
class Target:
    relative_path: str  # dest relative to Flutter project root
    size: int  # side length px
    opaque: bool = False  # flatten onto background (alpha-rejecting surfaces)
    frame: str | None = None  # per-target FRAMING rule ("maskable", "apple-touch")


@dataclass(frozen=True)
class AssetSpec:
    targets: Sequence[Target] = ()
    ico_sizes: Sequence[int] = ()


@dataclass(frozen=True)
class IconOptions:
    background: tuple[int, int, int] = (255, 255, 255)  # WHITE; flatten/tile colour
    macos_style: str = "auto"  # "auto" | "grid" | "raw"
    application_id: str = "com.example.app"  # names Linux hicolor files


@dataclass(frozen=True)
class SplashOptions:
    color: str = "#ffffff"  # light-mode background
    dark_color: str = "#222222"  # dark-mode background
    icon_background: str | None = None  # Android 12 splash icon canvas bg
    icon_dark_background: str | None = None  # dark-mode variant
    icon_fit: str = "contain"  # "contain" (fit to visible circle) | "none" (passthrough)


@dataclass(frozen=True)
class RenderedAsset:
    relative_path: str
    image: Image.Image

    @property
    def path(self) -> Path: ...


@dataclass
class RenderResult:
    assets: list[RenderedAsset] = ...
    warnings: list[str] = ...  # diagnostics-as-data; caller surfaces them
    ico: dict[str, dict[int, Image.Image]] = ...  # .ico = many images, one file
    stale: list[str] = ...  # previous-generator leftovers to delete

    def add(self, relative_path, image) -> None: ...
    def warn(self, message) -> None: ...
```

### `_icons.py` — `render_icons` + platform tables

```python
def render_icons(
    source: Image.Image,  # normalised RGBA from load_source
    options: IconOptions | None = None,
    spec: AssetSpec | None = None,  # default: stock Flutter layout
    *,
    platform: str,  # ios|macos|android|windows|web|linux (required kw)
    pre_rendered: bool = False,  # source already shaped → skip macOS grid
    derived: bool = False,  # generic icon.png → apply FRAMING margins
) -> RenderResult: ...  # raises ValueError on unknown platform
```

Platform output tables (defaults = stock Flutter layout):

- **iOS** (`ios/Runner/Assets.xcassets/AppIcon.appiconset/`): 15 sizes 20→1024,
  all `opaque=True` (App Store rejects alpha — flattened onto `IconOptions.background`).
- **macOS** (`macos/.../AppIcon.appiconset/app_icon_{s}.png`): 16/32/64/128/256/512/1024.
  `macos_style="auto"` (default) composes the Apple grid (824/1024 inset squircle
  tile + drop shadow) unless `looks_pre_shaped()` detects a finished icon;
  `"grid"` forces it, `"raw"` places full-bleed. Chained downscale from the
  composed 1024 canvas — the one place that is correct.
- **Android** (`android/app/src/main/res/`): legacy mipmaps 48/72/96/144/192
  (`mipmap-*/ic_launcher.png`) + adaptive foregrounds 108/162/216/324/432
  (`drawable-*/ic_launcher_foreground.png`). Adaptive background colour arrives
  via template resource, not pixels. Warns if artwork exceeds the
  `ADAPTIVE_SAFE_FRACTION` (72/108) safe zone.
- **Windows**: multi-size `.ico` `windows/runner/resources/app_icon.ico` with
  `WINDOWS_ICO_SIZES = (16, 32, 48, 256)` — one entry per size because a single
  256 downscaled everywhere looks mushy.
- **Web**: `favicon.png` (32), `Icon-192/512.png`, opaque `Icon-maskable-192/512.png`
  (flattened, maskable-framed), opaque `apple-touch-icon-192.png`. Warns on
  maskable safe-zone violations for explicit `icon_web.png` sources.
- **Linux**: freedesktop hicolor tree 16/24/32/48/64/128/256/512
  (`linux/icons/hicolor/{s}x{s}/apps/{application_id}.png`) + `linux/app_icon.png`
  (256, GTK window icon). Filenames need the app id, so defaults live in:

```python
def linux_targets(application_id: str) -> AssetSpec: ...
def web_targets_from_manifest(manifest: dict, favicon_size: int = 32) -> AssetSpec: ...
```

Framing rules (`FRAMING`, shrink-only/never-enlarge/idempotent, opaque sources
untouched): `ios 0.60`, `macos 0.68`, `android 0.567` (radial), `maskable 0.80`
(radial), `apple-touch 0.60`, `splash 0.60`; `FRAMING_TOLERANCE = 1.02`.
`derived=True` (generic `icon.png`) applies the platform margin; an explicit
`icon_<platform>.png` is treated as finished and placed full-bleed. Low-resolution
warning fires when the source is smaller than the largest produced asset.

### `_imaging.py` — compositing primitives

```python
WHITE = (255, 255, 255)
MACOS_TILE_RATIO = 824/1024; MACOS_SQUIRCLE_N = 5.0
MACOS_SHADOW_BLUR = 11; MACOS_SHADOW_DY = 8; MACOS_SHADOW_ALPHA = 64
WEB_TILE_INSET = 0.953; WEB_TILE_N = 4.0

def parse_hex_color(value: str) -> tuple[int, int, int]  # "#rrggbb"/"rrggbb"/3-digit; ValueError otherwise
def density_size(width: int, height: int, density: float) -> tuple[int, int]  # Dart `w*density~/4` truncation, ≥1x1
def scale_to_height(art, height) -> Image.Image
def scale_to_fit(art, box: int) -> Image.Image   # into box×box, aspect kept
def superellipse_mask(size: int, n: float, supersample: int = 4) -> Image.Image  # L-mode, AA
def place(art, canvas: int, *, bg=None, tile=None, tile_n=WEB_TILE_N,
          tile_color=WHITE, offset=(0, 0)) -> Image.Image  # RGB iff bg given
def apple_grid(art, canvas=1024, *, tile_ratio=..., n=..., blur=..., dy=...,
               shadow_alpha=..., tile_color=WHITE) -> Image.Image  # RGBA, transparent corners
def alpha_extent(img) -> float | None       # axial reach; None iff fully opaque
def radial_extent(img, *, sample=256) -> float | None  # centre-distance reach for circular masks
def looks_pre_shaped(img, *, min_fill=0.70, aspect_tolerance=0.08) -> bool
def has_transparent_corners(img, *, probe=0.06, threshold=8) -> bool
def save_png(img, path: Path) -> None       # makedirs; optimize=True, deterministic
def save_ico(path: Path, images: Mapping[int, Image.Image]) -> None  # base=largest; ValueError if empty
```

Two package-wide invariants: resample **once from the full-resolution source**
with **premultiplied alpha** (no dark halos on soft edges).

### `_splash.py` — `render_splash`

```python
ANDROID_DENSITIES = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}
IOS_SCALES = {"": 1, "@2x": 2, "@3x": 3}
WEB_SCALES = {"1x": 1, "2x": 2, "3x": 3, "4x": 4}
ANDROID_12_VISIBLE_FRACTION = 2 / 3  # canvas 288dp, 240dp w/ icon background


def render_splash(
    light: Image.Image,
    dark: Image.Image | None = None,  # omitted → dark outputs reuse light / are marked stale
    options: SplashOptions | None = None,
    *,
    platform: str,  # android|ios|web (required kw)
    derived: bool = False,  # fell back to icon.png → apply "splash" framing
) -> RenderResult: ...  # ValueError on unknown platform / icon_fit
```

Sizes follow flutter_native_splash's `width * density / 4` rule. Android writes
`drawable(-night)-*/splash.png` + `android12splash.png` (fitted into the visible
circle unless `icon_fit="none"` or already fitting; opaque art placed whole and
left to crop), deletes legacy `background.png`/`launch_background.xml` night
variants as `stale`. iOS writes `LaunchImage[.png/@2x/@3x]` + `LaunchImageDark*`
(both sets always — `Contents.json` declares all six) plus 1×1 `background.png` /
`darkbackground.png` swatches. Web writes `web/splash/img/light-{1..4}x.png` +
`dark-*` (always `.png`; stale `.webp` from older builds removed).

### `_write.py` — persistence

```python
def write(
    result: RenderResult, project_dir: str | Path, *, declared_only: bool = True
) -> list[Path]:
    """Delete result.stale, then write assets (+ .ico). declared_only=True skips
    files not already in the project (catalog/manifest-declared only); flet-cli
    passes False for android+linux (adaptive layers, hicolor tree) and splash.
    Returns paths written, in order."""
```

Preview idiom (no disk touched until `write`):

```python
from flet_platform_assets import load_source, render_icons, write

source, pre = load_source("assets/icon.png")
result = render_icons(source, platform="web")
[w for w in result.warnings]
write(result, "build/flutter")
```

## App usage & correctness

Config audited: `pyproject.toml` (`[tool.flet]`, `[tool.flet.splash]`,
`[tool.flet.android]`), `src/assets/`, `tools/make_icons.py`.

**(a) Correct config (keep as-is)**

- `[tool.flet] icon_background = "#0f1114"` (`pyproject.toml:38`) — dark Kiri
  slate behind transparent art on iOS flatten + macOS tile + opaque web icons.
  Matches `KIRI_DARK_BG` (`src/core/constants.py:86`). Correct for a dark brand;
  default white would have produced a white square on Apple platforms.
- `[tool.flet.android] adaptive_icon_background = "#0f1114"`
  (`pyproject.toml:59`) — feeds the adaptive-icon colour resource; flet-cli
  falls back to `icon_background` when unset (`build_base.py:1600-1606`), but
  the explicit key is right.
- `[tool.flet.splash] color = "#ffffff"`, `dark_color = "#0f1114"`
  (`pyproject.toml:46-48`) — distinct light/dark splash backgrounds; light
  launch is white, dark matches brand. Correct.
- `src/assets/icon_android.png` (1024×1024 RGBA) — flet-cli resolves
  `icon_<platform>.png` before generic `icon` (`build_base.py:2058-2063`), so
  Android builds use this finished foreground with `derived=False` (no
  reframing). Glyph pre-scaled to 64% of canvas by `tools/make_icons.py:21,33-44`,
  inside the 66.7% adaptive safe zone. Correct layering.
- `src/assets/icon.png` (2048×2048 RGBA) — comfortably above the largest
  target (1024 iOS/macOS), so no low-resolution warning; below `MAX_SOURCE_SIZE`
  2048 so no pre-reduction. Correct.
- `tools/make_icons.py` is dev-only Pillow and excluded from the APK via
  `[tool.flet.cleanup] app_files` (`pyproject.toml:98-108` lists `tools`). Correct.

**(b) Misuse / bugs found**

1. **Stale docstring, `tools/make_icons.py:3`** — claims icon.png is
   "currently 2048x1612", but the file on disk is already 2048×2048 (the script
   has been run since). Cosmetic; update the line so the next dev doesn't
   "fix" a square file.
2. **`src/assets/icon.svg` + `icon_white.svg` are invisible to the builders,
   by design but worth knowing** — `find_platform_image`
   (`build_base.py:3355-3427`) drops `.svg` (vector, never decoded) and warns
   `"icon.svg" is a vector (SVG) image…`. They still serve as in-app assets
   (`src="/icon.svg"` in `src/components/brand_header.py:85`,
   `src/screens/onboarding_screen.py:23`), so retention is fine — but no SVG
   will ever become a launcher icon or splash. Do not delete them thinking they
   are build inputs; do not add more expecting them to be.
3. **Non-premultiplied resize in `tools/make_icons.py:38-41,43`** — uses
   `img.resize(..., Image.LANCZOS)` + `paste` instead of the package's
   premultiplied `_resample`. For this hard-edged glyph the difference is
   negligible, but re-running it on softer future artwork risks the dark-halo
   edge the package docs warn about. Prefer importing `scale_to_fit`/`place`
   from `flet_platform_assets` if the script is ever touched.
4. **No per-platform `icon_ios.png` / `icon_macos.png` / `icon_web.png`** —
   not a bug (generic path auto-frames via `derived=True`), but be aware the
   macOS grid and iOS flatten are being applied to a *derived* composition.
   If the App Store tile ever looks off, author an explicit `icon_macos.png`
   / `icon_ios.png` rather than tweaking the shared master.

**(c) Splash derivation (implicit, verify on device)**

No `splash*.png` ships in `src/assets/`, so `render_splash` runs with
`derived=True`: the app icon gets the `"splash"` 0.60 framing shrink before
being drawn. That is the intended fallback, but the boot visual is therefore a
shrunk launcher glyph on `color`/`dark_color` — confirm on a real Android 12+
device that the 288dp canvas composition (no `icon_background` set, see §5)
reads as a splash, not a floating stamp.

## Underused config to adopt

1. **`[tool.flet.splash] icon_background` (+ `icon_dark_background`)** — highest
   value. Today Android 12 renders the 288dp canvas with no flatten colour;
   setting `icon_background = "#0f1114"` switches to the 240dp canvas and an
   opaque branded tile behind the glyph (mirrors `adaptive_icon_background`).
   Old key aliases `icon_bgcolor`/`icon_dark_bgcolor` still read
   (`build_base.py:108-114`), but use the new names.
2. **`[tool.flet.splash] icon_fit`** — `"contain"` (default, fit artwork into
   the visible circle) is right for this glyph; only set `"none"` if a
   hand-padded splash foreground is authored, and expect the
   `_warn_android_12_crop` warning if artwork exceeds the 2/3 circle.
3. **Dark splash artwork (`src/assets/splash_dark.png`, optionally
   `splash_dark_android/ios/web.png`)** — today dark mode reuses the light
   image on a dark background. A dedicated dark composition (e.g. light glyph
   variant like `icon_white.svg` rasterised) would complete the chain
   `splash_{platform} → splash → icon` (`build_base.py:2326-2341`).
4. **Light splash artwork (`src/assets/splash.png`)** — decouples the boot
   visual from the launcher glyph so the icon can evolve without changing boot.
5. **`[tool.flet.macos] icon_style`** — defaults `"auto"` are fine; set
   `"grid"` only to force the Apple tile over a shaped source, `"raw"` only if
   a future icon ships its own shape (auto-detection warns and does the right
   thing otherwise).
6. **Per-platform web art (`icon_web.png`)** — only if the maskable-crop
   warning ever fires; the generic path already fits + flattens maskables.

## Gotchas

- **SVG is dropped with a warning, never decoded.** Any `icon*.svg` /
  `splash*.svg` in `src/assets/` is skipped by `find_platform_image`; raster
  `.png` always wins ties. Keep SVGs for in-app `src=` only.
- **Generic vs explicit is a framing switch, not just a filename.**
  `icon.png` → `derived=True` → platform margins computed for you;
  `icon_android.png` → used exactly as supplied. Never "fix" Android framing by
  editing the master — edit the platform file.
- **Opaque art is treated as finished.** Fully opaque sources skip all
  reframing (`_frame` returns them untouched) and are placed whole into the
  Android 12 circle to be cropped. Transparency is how you ask for fitting.
- **iOS flatten is mandatory.** Any alpha in iOS output is composited onto
  `icon_background` — there is no transparent iOS icon. A wrong
  `icon_background` shows on every Apple surface.
- **`write(declared_only=True)` won't invent files.** iOS/macOS/web only
  overwrite catalog-/manifest-declared targets; Android adaptive layers, Linux
  hicolor, and splash pass `False`. A missing catalog entry means a silently
  unwritten icon — check the template, not the generator.
- **Stale files are deleted on write.** Disabling dark splash (or switching a
  `.webp` source) removes the orphan outputs; do not hand-place files under
  those generated paths.
- **Build caching is hash-gated.** Identical source + options + template digest
  skips regeneration (`.hash/icons`, `.hash/splashes`); `touch` noise won't
  rebuild, but a changed `pyproject.toml` colour will.
- **Colour formats:** `IconOptions.background` is an RGB tuple (parsed by
  flet-cli via `parse_hex_color`, invalid → white + warning);
  `SplashOptions` colours are `"#rrggbb"` strings (3-digit accepted).
  `icon_fit` accepts only `"contain"`/`"none"` — anything else is `ValueError`.
