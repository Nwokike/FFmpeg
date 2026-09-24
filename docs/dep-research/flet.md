# flet 1.0.0 — Complete API Reference

Package: `flet` 1.0.0 (Flutter 3.44.8 client). Framework for building
multi-platform (iOS / Android / Windows / Linux / macOS / Web) apps in pure
Python. UI is rendered by Flutter; Python drives it through dataclass-based
controls synced over a msgpack socket protocol (or in-browser via Pyodide).

Ground truth for this report: source read exhaustively from
`.venv/Lib/site-packages/flet` (279 `.py` files, 59,365 lines — every file
parsed via AST plus full reads of `router.py`, `page.py`, `base_page.py`,
`use_state.py`, `use_effect.py`, `use_ref.py`, `use_dialog.py`,
`observable.py`, `app.py`) and metadata from
`.venv/Lib/site-packages/flet-1.0.0.dist-info/`.

---

## Files

279 `.py` files (excluding `__pycache__`/`*.pyc`), 59,365 lines total.
`flet/__init__.py` re-exports **~537 public names** (`__all__` = 536).

Largest modules (>800 lines):

| File | Lines | Contents |
|---|---|---|
| `controls/theme.py` | 3604 | `Theme` + ~43 per-control theme classes |
| `controls/types.py` | 1745 | ~39 shared enums/value types |
| `controls/object_patch.py` | 1739 | Wire-protocol diff/patch engine (internal) |
| `flet/__init__.py` | 1832 | Public re-export surface |
| `controls/page.py` | 1340 | `Page` (session, nav, tasks, OAuth, pubsub) |
| `utils/validation.py` | 1848 | `V` rule builders, `validate()` |
| `controls/core/markdown.py` | 1040 | `Markdown` + stylesheets/code themes |
| `testing/flet_test_app.py` | 939 | Integration-test app controller |
| `components/router.py` | 902 | `Router`, `Route`, matching, view stacks |
| `controls/device_info.py` | 883 | Per-OS device info snapshots |
| `controls/base_page.py` | 864 | `BasePage` (views, dialogs, overlay, drawers) |
| `app.py` | 753 | `run()`, `run_async()` |

Subpackages: `auth/` (+`providers/`), `canvas/` (re-export only),
`components/` (+`hooks/`), `controls/` (`core/`, `material/`, `cupertino/`,
`services/`), `fastapi/`, `messaging/`, `pubsub/`, `security/`, `testing/`,
`utils/`.

Data (non-Python) files:

| File | Notes |
|---|---|
| `py.typed` | PEP 561 marker — package ships inline types |
| `controls/material/icons.json` | **8825** Material icon codepoints; lazily loaded by `Icons` proxy |
| `controls/cupertino/cupertino_icons.json` | Cupertino icon codepoints |
| `controls/material/icons.pyi`, `controls/cupertino/cupertino_icons.pyi` | Static icon name stubs for IDE completion |
| No templates / static assets / locale files | All rendering lives in the Flutter client |

Console scripts (`entry_points.txt`): `flet = flet.cli:main`
(`flet/cli.py` is a 12-line shim re-exporting the `flet-cli` package).
Pytest plugin entry point: `flet = flet.pytest_plugin` (group `pytest11`).

---

## Metadata

From `flet-1.0.0.dist-info/METADATA` (+`WHEEL`, `top_level.txt`):

- **Name / Version:** `flet` 1.0.0. `flet.version.flet_version = "1.0.0"`,
  `flutter_version = "3.44.8"`. Helpers: `get_flet_version()`,
  `get_flutter_version()`, `from_git()`, `find_repo_root()`.
- **Summary:** "Flet for Python - easily build interactive multi-platform apps
  in Python". License: **Apache-2.0**. Requires-Python: **>=3.10**.
  Pure-Python wheel (`py3-none-any`).
- **Runtime deps:** `oauthlib>=3.2.2` (non-Emscripten), `httpx>=0.28.1`
  (non-Emscripten), `repath>=0.9.0` (route-template matching used by
  `Router`), `msgpack>=1.1.0` (wire protocol), `typing-extensions`
  (Python < 3.11).
- **Extras:** `cli` → `flet-cli==1.0.0`; `web` → `flet-web==1.0.0`;
  `desktop` → `flet-desktop==1.0.0`; `all` → cli+web+desktop; `test` →
  `pytest>=7.2.0`, `pytest-asyncio>=1.1.0`, `numpy>=2.2.0`, `pillow>=10.3.0`,
  `scikit-image>=0.25.2`.

---

## Module-by-module API

Conventions used below: every control is a `@control`-decorated dataclass;
construct with keyword args, mutate fields, then call `.update()` (or
`page.update()`) to flush. Event handlers receive an event object with
`.control` (the source control), `.data`, `.name`, `.page`. Unless noted,
handlers may be sync or async callables.

### 1. App entry points (`app.py`, `cli.py`, `version.py`)

```python
ft.run(main, *, before_main=None, name="", host=None, port=0,
       view=AppView.FLET_APP, assets_dir="assets", upload_dir=None,
       web_renderer=WebRenderer.AUTO,
       route_url_strategy=RouteUrlStrategy.PATH, no_cdn=False,
       export_asgi_app=False)
ft.run_async(...)  # same signature minus export_asgi_app; awaitable
```

- `main: (page: ft.Page) -> Any | Awaitable[Any]` — sync or async.
- `view: AppView` — `FLET_APP | WEB_BROWSER | NATIVE_OS_WINDOW`.
- `web_renderer: WebRenderer` — `AUTO | CANVAS_KIT | SKWASM`.
- `route_url_strategy: RouteUrlStrategy` — `PATH | HASH`.
- Example: `ft.run(main, assets_dir=str(Path(__file__).parent / "assets"))`.

### 2. Page — `BasePage` (`controls/base_page.py`) + `Page` (`controls/page.py`)

`Page(BasePage)`; `BasePage(AdaptiveControl)`. Root view auto-created per
session. `page.views: list[View]`, `page.route: str`, `page.title`,
`page.theme / dark_theme: Theme`, `page.theme_mode: ThemeMode`,
`page.padding`, `page.bgcolor`, `page.scroll`, `page.overlay: list`,
`page.services: list[Service]`, `page.fonts`, `page.platform: PagePlatform`,
`page.web: bool`, `page.width/height`, `page.url`, `page.query: QueryString`,
`page.session: Session`, `page.pubsub: PubSubClient`, `page.auth`,
`page.loop`, `page.executor`.

Views & content:

```python
page.add(*controls) -> None
page.insert(at: int, *controls) -> None
page.remove(*controls) -> None
page.remove_at(index: int) -> None
page.clean() -> None
page.update(*controls) -> None        # no args = patch whole page
page.render(component, *args, **kwargs)       # single-view component tree
page.render_views(component, *args, **kwargs) # Router(manage_views=True) tree
await page.scroll_to(offset=None, delta=None, scroll_key=None,
                     duration=None, curve=None) -> None
```

Dialogs (the ONLY dialog API — see Gotchas):

```python
page.show_dialog(dialog: DialogControl) -> None  # raises RuntimeError if already open
page.pop_dialog() -> DialogControl | None
```

Drawers / capture:

```python
await page.show_drawer() / close_drawer() / show_end_drawer() / close_end_drawer()
await page.take_screenshot(pixel_ratio=None, delay=None) -> bytes
await page.take_animation(...)  # animated capture (delay/frames)
```

Navigation (note sync vs async):

```python
page.navigate(route: str, **kwargs) -> None        # sync, fires on_route_change
await page.push_route(route: str, **kwargs) -> None # async variant
await page.pop_views_until(route: str, result=None) -> None
```

Background work:

```python
page.run_task(handler, *args, **kwargs) -> Future
# handler MUST be a coroutine function (TypeError otherwise).
page.run_thread(handler, *args, **kwargs)  # thread-pool offload
```

OAuth / misc:

```python
await page.login(provider, scopes=None, ...) -> ...  # fires on_login: LoginEvent
page.logout() -> None
page.get_upload_url(file_name: str, expires: int) -> str
await page.get_device_info() -> DeviceInfo | None
await page.set_allowed_device_orientations(orientations: list[DeviceOrientation]) -> None
await page.wait_until_visible() -> None
```

Page events (assign callables): `on_route_change -> RouteChangeEvent`,
`on_view_pop -> ViewPopEvent`, `on_views_pop_until -> ViewsPopUntilEvent`,
`on_error`, `on_close`, `on_disconnect`, `on_platform_brightness_change ->
PlatformBrightnessChangeEvent`, `on_app_lifecycle_state_change ->
AppLifecycleStateChangeEvent`, `on_keyboard_event -> KeyboardEvent`,
`on_login -> LoginEvent`, `on_logout`, `on_locale_change ->
LocaleChangeEvent`, `on_multi_view_add/remove`, `on_click`.

`MultiView(BasePage)` — additional app views for multi-view sessions.

### 3. Reactive components & hooks (`components/`)

```python
@ft.component
def MyComp(prop: str, *, key: Key | None = None) -> ft.Control: ...
```

- Component functions re-render when hook state or subscribed observables
  change. `key` (e.g. `ft.ValueKey("home")`) preserves identity.
- `ft.memo(fn)` — memoize a component function itself.
- `ft.unwrap_component(c)` — unwrap to the underlying control.

```python
value, set_value = ft.use_state(initial)
# initial: value or lazy callable. Setter accepts value OR updater fn
# (prev) -> next. Shallow (==) compare: equal values are no-ops.
# Observable values auto-subscribe the component.
```

```python
ref: ft.MutableRef[T] = ft.use_ref(initial_value)  # .current, stable identity, no re-render
ft.use_effect(setup, dependencies=None, cleanup=None)
# setup() may be sync/async and may return a cleanup. dependencies=None → mount only.
ft.on_mounted(fn)            # use_effect(fn, [])
ft.on_unmounted(fn)          # cleanup-only on unmount
ft.on_updated(fn, dependencies=None)  # post-mount renders (None = every update)
memoed = ft.use_memo(calculate_value, dependencies=None)
cb = ft.use_callback(fn, dependencies=None)  # stable fn identity
ft.use_dialog(dialog: DialogControl | None)  # portal dialog to page overlay; None hides
```

Observable + context:

```python
@ft.observable
class AppState:
    def __init__(self): self.count: int = 0  # field writes notify subscribers
state.subscribe(fn) -> disposer      # fn(sender, field)
state.notify()                       # manual broadcast
# ObservableList / ObservableDict auto-wrap list/dict fields (mutation notifies).
Ctx = ft.create_context(default_value)
value = ft.use_context(Ctx)          # subscribes component to context
```

`ft.Ref[T]` (`controls/ref.py`) — weak-reference holder with `.current`;
used for imperative control handles.
`ft.context` — ambient `Context` (`context.page`, components-mode flag).

### 4. Routing (`components/router.py`, `controls/template_route.py`)

```python
ft.Route(path=None, *, index=False, component=None, children=None,
         loader=None, outlet=False, modal=False, recursive=False)
ft.Router(routes: list[Route], not_found=None, manage_views=False) -> Control | list[View]
```

- `path` supports `:name`, `:name?`, `:name*`, `:name(\d+)` (via `repath`).
- `index=True` matches parent exactly. `children` nest (layout routes).
- `loader(params) -> Any`, read with `ft.use_route_loader_data()`.
- `outlet=True` + `manage_views=True`: layout wraps child views
  (render child via `ft.use_route_outlet()`).
- `modal=True` + `manage_views=True`: overlay view on the base stack;
  component should return `View(..., fullscreen_dialog=True)`.
- `recursive=True`: unbounded-depth segments (e.g. `/folder/a/b/c`).
- `manage_views=True` → returns `list[View]`; mount with
  `page.render_views(App)`; enables swipe-back / system back / AppBar back.

Router hooks (must be called inside Router-rendered components; safe
fallbacks outside: `{}` / `""` / `None` / `False`):

```python
ft.use_route_params() -> dict[str, str]
ft.use_route_location() -> str            # full pathname
ft.use_view_path() -> str                 # this view level's URL (use as View.route)
ft.use_route_outlet() -> Control | None
ft.use_route_loader_data() -> Any
ft.is_route_active(path: str, exact: bool = False) -> bool
ft.LocationInfo(pathname, search="", hash="")  # dataclass
```

`ft.TemplateRoute(route: str)` — `.match(route_template: str) -> bool`
for imperative template matching outside `Router`.

### 5. Base control classes

`BaseControl` — `.update() -> None`, `.page`, `.parent`,
lifecycle `init/build/before_update/did_mount/will_unmount/before_event(e)`.
`Control(BaseControl)` adds: `expand: bool|int`, `expand_loose: bool`,
`col: ResponsiveNumber (=12)`, `opacity`, `tooltip: str|Tooltip`,
`badge: Badge`, `visible=True`, `disabled=False`, `rtl=False`.
`LayoutControl(Control)` adds geometry + animation: `width/height`,
`left/top/right/bottom`, `align`, `margin: MarginValue`,
`rotate/scale/offset: ...Value`, `flip: Flip`, `transform: Transform`,
`aspect_ratio`, `animate_opacity/animate_size/animate_position/animate_align/
animate_margin/animate_rotation/animate_scale/animate_offset:
AnimationValue`, `size_change_interval=10`,
`on_size_change -> LayoutSizeChangeEvent`, `on_animation_end`.
`ScrollableControl(Control)`: `scroll: ScrollMode|Scrollbar`,
`auto_scroll: bool`, `on_scroll -> OnScrollEvent`,
`await scroll_to(offset/delta/scroll_key, duration, curve)`.
`AdaptiveControl(Control)` — Cupertino adaptation (`adaptive` pattern).
`DialogControl(AdaptiveControl)` — `open: bool`, `on_dismiss`;
shown ONLY via `page.show_dialog()`.
`ActionControl(Control)` — client-side actions without a Python round-trip:
`ft.OpenUrl(url)`, `ft.CopyToClipboard(value)`, `ft.PickFiles(...)`,
`ft.ShareText(text)`.
`FormFieldControl(LayoutControl)` — `label/label_style`, `error_text`,
`border: ControlStateValue[InputBorder]`, `content_padding`, `dense`,
`filled/fill_color`, `hint_text/helper_text (+styles)`; borders:
`UnderlineInputBorder | OutlineInputBorder | NoInputBorder`.
`ControlState` enum (`DEFAULT FOCUSED HOVER PRESSED DISABLED ...`);
`ControlStateValue[T] = T | dict[ControlState, T]`.

### 6. Layout & core controls (`controls/core/`)

- `ft.Text(value="", *, spans, text_align=START, font_family(+_fallback),
  size, weight: FontWeight, italic, style: TextStyle,
  theme_style: TextThemeStyle, max_lines, overflow=CLIP, selectable,
  no_wrap, color, bgcolor, semantics_label, on_tap, on_selection_change, ...)`.
  `TextSpan` (ActionControl) for rich spans; selection events carry
  `TextSelection` + `TextSelectionChangeCause`.
- `ft.Row / ft.Column(controls=[], *, alignment=START, vertical_alignment /
  horizontal_alignment, spacing=10, tight, wrap, run_spacing,
  run_alignment, intrinsic_height/intrinsic_width)`. **No `padding` kwarg.**
- `ft.Stack(controls=[], *, clip_behavior=HARD_EDGE, alignment=None,
  fit=StackFit.LOOSE)`. **There is NO `ft.Positioned` in 1.0** — position
  children with `Container.alignment/margin` or `LayoutControl.offset`.
- `ft.Container(content, *, padding, alignment, bgcolor, gradient, blend_mode,
  border, border_radius: Number|BorderRadius, shape, clip_behavior, ink,
  image: DecorationImage, blur, shadow, url, color_filter,
  ignore_interactions, on_click/on_tap_down/on_long_press/on_hover, ...)`.
- `ft.ListView(controls=[], *, horizontal, reverse, spacing=0, item_extent,
  divider_thickness, padding, clip_behavior, cache_extent,
  build_controls_on_demand=True, ...)`. `ft.GridView` — 2D scrollable array.
  `ft.ResponsiveRow(controls, columns=12, spacing/run_spacing,
  breakpoints={XS:0,...})` — virtual-column responsive layout.
- `ft.View(controls=[], *, route="/", appbar, bottom_appbar,
  floating_action_button(+_location), navigation_bar, drawer/end_drawer,
  vertical_alignment, horizontal_alignment, spacing=10,
  padding=Padding.all(10), bgcolor, decoration, fullscreen_dialog=False,
  can_pop=True, on_confirm_pop, ...)`.
- `ft.Dismissible(content, *, background, secondary_background,
  dismiss_direction=HORIZONTAL, dismiss_thresholds, movement_duration=200ms,
  resize_duration=300ms, on_update, on_dismiss, on_confirm_dismiss,
  on_resize)`. Events: `DismissibleDismissEvent(direction, progress...)`,
  `DismissibleUpdateEvent`.
- `ft.GestureDetector(content, *, on_tap/on_tap_down/on_tap_up,
  on_double_tap(+_down), on_long_press(+_start/_end/_move_update),
  on_horizontal_drag_down/_start/_update/_end (+vertical/pan/scale/hover/
  enter/exit/scroll variants), ...)`. Drag payloads in `flet.events`:
  `DragDown/Start/Update/EndEvent` (`primary_velocity: float|None` on end),
  `TapEvent/TapMoveEvent`, `ScaleStart/Update/EndEvent`, `PointerEvent`,
  `ScrollEvent`, `HoverEvent`, `ForcePressEvent`, `LongPress*`,
  `MultiTapEvent`.
- `ft.Markdown(value="", *, selectable, extension_set=NONE,
  code_theme: MarkdownCodeTheme|MarkdownCustomCodeTheme, auto_follow_links,
  shrink_wrap=True, fit_content=True, on_tap_link, on_tap_text, ...)`.
  `MarkdownExtensionSet` (`NONE GITHUB_WEB GITHUB_FLAVORED`); `MarkdownStyleSheet`.
- `ft.Tabs(content, length, selected_index=0, animation_duration=100ms,
  on_change)`; `ft.TabBar(tabs, scrollable=True, tab_alignment,
  indicator_color/indicator/indicator_size/indicator_animation,
  label_color(+unselected), on_click, on_hover, ...)`; `ft.Tab(label, icon,
  height, icon_margin)`; `ft.TabBarView(controls, viewport_fraction=1.0)`.
  `ft.PageView` — swipeable one-child-per-page.
- `ft.Icon(icon: IconData, *, color, size, fill/grade/weight/optical_size,
  shadows, ...)`; `ft.Icons.*` (8825 lazy names); `ft.CupertinoIcons.*`.
- `ft.Image(src: str|bytes, *, fit: BoxFit, repeat, border_radius, color(+_blend_mode),
  filter_quality=MEDIUM, placeholder_src, fade_in_animation,
  cache_width/cache_height, gapless_playback, ...)`.
  `ft.RawImage` — streams pixel frames from Python.
- `ft.Pagelet` — Material visual-layout scaffold. `ft.SafeArea(content)` —
  OS-intrusion insets. `ft.AnimatedSwitcher(content, *, transition, ...)`.
- `ft.Draggable` / `ft.DragTarget(content, on_will_accept/on_accept/on_leave/
  on_move)` with `DragTargetEvent/DragWillAcceptEvent/DragTargetLeaveEvent`.
- `ft.DataTable` (`DataColumn/DataRow/DataCell`, `on_sort`).
  `ft.AutoComplete` (`AutoCompleteSuggestion`, `on_select`).
  `ft.SearchBar`, `ft.MenuBar(MenuStyle)`, `ft.MenuItemButton`,
  `ft.SubmenuButton`, `ft.PopupMenuButton` (`PopupMenuItem`,
  `PopupMenuPosition`), `ft.ContextMenu` (+events/trigger),
  `ft.ExpansionPanel/ExpansionPanelList(on_change)`, `ft.ExpansionTile`,
  `ft.ReorderableListView` (`OnReorderEvent`), `ft.SelectionArea`,
  `ft.KeyboardListener` (`KeyDown/Up/RepeatEvent`),
  `ft.InteractiveViewer` (pan/zoom/rotate), `ft.Hero` (shared-element
  transitions), `ft.Shimmer(content, direction)`, `ft.ShaderMask`,
  `ft.Screenshot`, `ft.Semantics/MergeSemantics`, `ft.TransparentPointer`,
  `ft.Placeholder`, `ft.RotatedBox`, `ft.WindowDragArea`,
  `ft.Window` (desktop window control; `WindowEvent/WindowEventType/
  WindowResizeEdge`), `ft.FletApp` (embed a Flet app; `FletAppOutputEvent`),
  `ft.AutofillGroup` (`AutofillHint`), Canvas (`ft.Canvas(shapes=[...])`
  + `Arc/Circle/Color/Fill/Image/Line/Oval/Path/Points/Rect/Shadow/Text`
  shapes, `PointMode`).

### 7. Material controls (`controls/material/`)

Buttons: `ft.Button` base; `ft.FilledButton/FilledTonalButton`,
`ft.OutlinedButton`, `ft.TextButton` (`content: str|Control`, `icon`,
`icon_color`, `style: ButtonStyle`, `autofill... autofocus`,
`clip_behavior`, `url`, `on_click/on_long_press/on_hover/on_focus/on_blur`).
`ft.IconButton(icon, icon_color, icon_size, selected/selected_icon(+_color),
style, splash_radius, size_constraints, ...)` + `FilledIconButton`,
`FilledTonalIconButton`, `OutlinedIconButton`.
`ft.FloatingActionButton`. `ft.ButtonStyle(...)` + shape borders
(`StadiumBorder/CircleBorder/RoundedRectangleBorder/Bevelled/
ContinuousRectangleBorder`).

Inputs: `ft.TextField(value="", *, keyboard_type=TEXT, multiline/min/max_lines,
max_length, password/can_reveal_password, read_only, text_align, autofocus,
capitalization, input_filter: NumbersOnly|TextOnly|InputFilter(regex),
obscuring_character, cursor_*, autofill_hints, on_change/on_submit/on_focus/
on_blur/on_tap_outside/on_click, +FormFieldControl decor, ...)` — 48 fields.
`ft.Checkbox(label, value=False, tristate, label_position,
fill_color: ControlStateValue, border_side, on_change, ...)`.
`ft.Switch(label, value=False, thumb_color/track_color (+active/inactive),
thumb_icon: ControlStateValue[IconData], on_change, ...)`.
`ft.Radio` + `ft.RadioGroup(content, value, on_change)`.
`ft.Slider(value, min=0.0, max=1.0, divisions, round, label,
active_color/inactive_color/thumb_color, interaction: SliderInteraction,
secondary_track_value, padding, on_change/on_change_start/on_change_end,
...)`. `ft.RangeSlider(start_value, end_value, min, max, divisions, round,
on_change(+_start/_end), ...)`.
`ft.Dropdown(value: str|None, options: list[DropdownOption], *,
enable_filter, enable_search=True, editable, menu_height/width/style,
selected_suffix, input_filter, trailing/leading_icon, on_select,
on_text_change, on_focus/on_blur, +FormFieldControl decor, ...)` —
M3 dropdown; `DropdownOption(key, text, content, leading/trailing_icon,
style)`. Legacy `DropdownM2/Option` also shipped.
`ft.DatePicker/ DateRangePicker/TimePicker` (dialogs; entry-mode events).
`ft.SegmentedButton(segments: list[Segment], selected: list[str],
allow_empty/multiple_selection, on_change)`; `Segment(value, icon, label)`.
`ft.Chip(label: str|Control, leading, selected, selected_color,
show_checkmark, delete_icon(+_tooltip/_color), on_click/on_delete/on_select,
...)` — 35 fields. `ft.CircleAvatar`, `ft.Badge` (also attachable via
`Control.badge`), `ft.Card(+CardVariant)`, `ft.ListTile` (33 fields),
`ft.Divider/VerticalDivider`, `ft.Tooltip`, `ft.Banner`, `ft.BottomSheet`,
`ft.AppBar`, `ft.BottomAppBar`, `ft.NavigationBar(destinations[2..],
selected_index=0, label_behavior, indicator_color(+_shape), border,
animation_duration, on_change)` + `NavigationBarDestination(icon,
label, selected_icon, bgcolor)`, `ft.NavigationDrawer(+Destination)`,
`ft.NavigationRail(+Destination, label_type)`, `ft.ProgressBar(value 0..1,
bar_height, ...)` / `ft.ProgressRing(value, stroke_width, stroke_cap, ...)`,
`ft.AlertDialog(title, content, actions, modal, shape, scrollable,
actions_alignment, barrier_color, icon(+_color), ...)` — 25 fields,
`ft.SnackBar(content, behavior, dismiss_direction, show_close_icon,
action: str|SnackBarAction, duration=Duration(ms=4000), margin, padding,
width, elevation, shape, on_action, on_visible, ...)` with
`SnackBarAction(label, ..., on_click)`, `SnackBarBehavior
(FLOATING FIXED ...)`, `DismissDirection`.

### 8. Cupertino controls (`controls/cupertino/`, ~28 classes)

`CupertinoButton(+Size)` / `CupertinoFilledButton` /
`CupertinoTintedButton`, `CupertinoSwitch`, `CupertinoCheckbox`,
`CupertinoRadio`, `CupertinoSlider`, `CupertinoTextField(+OverlayVisibilityMode)`,
`CupertinoAlertDialog`, `CupertinoActionSheet(+Action)`,
`CupertinoBottomSheet`, `CupertinoAppBar`, `CupertinoNavigationBar`,
`CupertinoListTile`, `CupertinoDatePicker(+Mode/DateOrder)`,
`CupertinoTimerPicker(+Mode)`, `CupertinoPicker`,
`CupertinoSegmentedButton`, `CupertinoSlidingSegmentedButton`,
`CupertinoActivityIndicator`, `CupertinoContextMenu(+Action)`,
`CupertinoDialogAction`, `CupertinoColors` (str enum),
`CupertinoIcons`. Any `AdaptiveControl` renders its Cupertino variant when
`adaptive=True` on iOS/macOS.

### 9. Services (`controls/services/`) — MUST be in `page.services`

Unregistered services are garbage-collected and their calls fail.

```python
await ft.Clipboard().get/set(value: str)
await get_image/set_image(bytes) / set_files(list[str]) -> bool / get_files()
await ft.UrlLauncher().launch_url(url: str|Url, ...) -> bool
await can_launch_url(url) -> bool
await close_in_app_web_view() / open_window(...) / supports_launch_mode(mode)
# LaunchMode, WebViewConfiguration, BrowserConfiguration
await ft.Share().share_text(text, ...) / share_uri(uri, ...) -> ShareResult
await share_files(list[ShareFile], text=None, ...) -> ShareResult
ft.ShareFile.from_path(path, *, name=None) / .from_bytes(name, bytes, mime_type=None)
# ShareResult(status: ShareResultStatus, ...), ShareCupertinoActivityType
fp = ft.FilePicker()
await fp.pick_files(dialog_title=None, file_type=FilePickerFileType.ANY,
                    allowed_extensions=None, allow_multiple=False,
                    with_data=False, ...) -> FilePickerResultEvent | None
await fp.save_file(dialog_title=None, file_name=None, src_bytes: bytes|None, ...) -> str|None
await fp.get_directory_path(...) -> str|None
await fp.upload(list[FilePickerUploadFile])  # events: FilePickerUploadEvent
# FilePickerFile(path, name, bytes, size); FilePickerFileType(ANY AUDIO IMAGE
# VIDEO MEDIA CUSTOM); FilePickerFile/ResultEvent(files)
sp = ft.SharedPreferences()
await sp.set(key, value: str|int|float|bool|list[str]) -> bool
await sp.get(key) / contains_key(key) / remove(key) / get_keys(prefix) / clear()
wl = ft.Wakelock(); await wl.enable() / wl.disable() / wl.is_enabled()
conn = ft.Connectivity()
await conn.get_connectivity() -> list[ConnectivityType]  # NONE means offline
conn.on_change -> ConnectivityChangeEvent
await ft.Battery()... state queries + BatteryStateChangeEvent
ft.HapticFeedback()  # platform haptics (selection/light/medium/heavy/vibrate)
ft.ScreenBrightness()  # get/set + ScreenBrightnessChangeEvent
ft.SemanticsService()  # announcements (Assertiveness), AccessibilityFeatures
ft.ShakeDetector()     # on_shake
ft.StoragePaths()      # platform directories (temp/cache/app-docs/...)
ft.BrowserContextMenu()  # enable/disable web context menu
ft.Tester()  # see Testing
# Sensors: Accelerometer / UserAccelerometer / Gyroscope / Magnetometer /
# Barometer — reading events (x/y/z[, pressure]) + on_error: SensorErrorEvent
```

### 10. Value types, enums, styling

- `ft.Animation(duration: Duration|int-ms = ..., curve=AnimationCurve.LINEAR)`.
  Shorthand `AnimationValue = bool|int|Animation` (`True` = 1000ms linear).
- `AnimationCurve` — `LINEAR EASE_IN(/OUT/CUBIC/...) EASE_OUT ELASTIC_IN ...
  BOUNCE ... DECELERATE ...` (~30 members).
- `ft.Duration(days=0, hours=0, ..., milliseconds=0)`; `DurationValue =
  Duration | int` (int = ms). Constants `MICROSECONDS_PER_*`.
- `ft.Alignment(x, y)` + constants (`CENTER TOP_LEFT BOTTOM_RIGHT ...`).
  `ft.Axis` (`HORIZONTAL VERTICAL`).
- `ft.Padding(left,top,right,bottom)` + `.all(v) / .symmetric(vertical,
  horizontal) / .only(...)`; `PaddingValue = Number | Padding`. Same shape
  for `ft.Margin` / `MarginValue`. Plain numbers accepted anywhere these
  appear.
- `ft.Border(top,right,bottom,left: BorderSide)` + `.all/.symmetric/.only`;
  `BorderSide(color, width, style=SOLID, stroke_align)`;
  `BorderStyle(SOLID NONE)`; `BorderSideStrokeAlign(INSIDE CENTER OUTSIDE)`.
- `ft.BorderRadius(top_left, top_right, bottom_left, bottom_right)` +
  `.all/.circular/...`; `BorderRadiusValue = Number | BorderRadius`.
- `ft.BoxDecoration(color, image: DecorationImage, border(+radius), shape,
  gradient: Linear|Radial|SweepGradient, shadows: list[BoxShadow],
  background_blend_mode)`; `BoxFit(CONTAIN COVER FILL FIT_WIDTH ... benefits)`;
  `BoxShape(CIRCLE RECTANGLE)`; `FilterQuality(NONE LOW MEDIUM HIGH)`;
  `BoxShadow(color, spread_radius, blur_radius, offset: Offset, blur_style)`;
  `BoxConstraints(min/max_width/height)`; `ColorFilter.mode/srgb...`.
- `ft.Blur(sigma_x, sigma_y, tile_mode=BlurTileMode.CLAMP)`.
- `ft.LinearGradient(colors, begin, end, stops, tile_mode)` (+Radial/Sweep);
  `GradientTileMode(CLAMP DECAL MIRROR REPEATED)`.
- `ft.Paint(color, style=PaintingStyle.FILL, stroke_width, stroke_cap/join,
  gradient: PaintLinear|Radial|SweepGradient, ...)` (Canvas painting).
- `ft.Rotate(angle) / ft.Scale(scale_x/scale_y) / ft.Offset(x, y) /
  ft.Flip(horizontal/vertical) / ft.Transform(...) / ft.Matrix4(...)`.
- `ft.TextStyle(size, weight: FontWeight, italic, color, bgcolor, decoration:
  TextDecoration (IntFlag: NONE UNDERLINE OVERLINE LINE_THROUGH) (+style),
  font_family, letter/word/height... )`; `TextOverflow(CLIP ELLIPSIS FADE
  VISIBLE)`; `TextBaseline`; `TextThemeStyle` (M3 roles:
  `DISPLAY_LARGE ... TITLE_MEDIUM BODY_MEDIUM LABEL_SMALL ...`);
  `StrutStyle`; `TextAlign(START END LEFT RIGHT CENTER JUSTIFY)`.
- `ft.FontWeight` (`W100..W900 BOLD NORMAL`).
- `ft.Colors` — str enum of Material colors (`RED WHITE BLACK SURFACE
  PRIMARY ERROR ...` + `*_50..900` shades, `ON_*` variants);
  `Colors.with_opacity(opacity, color) -> str`;
  `Colors.random(...)`. `ft.CupertinoColors` — same idea, iOS palette.
- `ft.Icons` / `ft.CupertinoIcons` — lazy proxies over the JSON maps;
  attribute access returns `IconData`.
- `ft.MainAxisAlignment(START END CENTER SPACE_BETWEEN SPACE_AROUND
  SPACE_EVENLY)`; `CrossAxisAlignment(START END CENTER STRETCH BASELINE)`;
  `ScrollMode(ALWAYS AUTO HIDDEN ADAPTIVE ...)`;
  `ClipBehavior(NONE HARD_EDGE ANTI_ALIAS ...)`; `BlendMode` (~29);
  `ThemeMode(SYSTEM LIGHT DARK)`; `Brightness(LIGHT DARK)`;
  `PagePlatform(IOS ANDROID ANDROID_TV MACOS WINDOWS LINUX)` with
  `.is_mobile() / .is_desktop() / .is_apple()`; `Orientation`;
  `DeviceOrientation`; `FloatingActionButtonLocation`;
  `AppLifecycleState`; `AppView`; `MouseCursor`; `PointerDeviceType`;
  `StrokeCap/StrokeJoin`; `VisualDensity`; `ImageRepeat`;
  `UrlTarget`; `Locale/LocaleConfiguration`; `KeyboardType`;
  `TextCapitalization`; `LabelPosition`; `VerticalAlignment`;
  `ResponsiveRowBreakpoint`; `PageTransitionTheme/PageTransitionsTheme`.
- `ft.Size(w,h)` / `ft.Rect(...)` (geometry); `ft.Vector` (complex-based 2D).
- `ft.Key` / `ft.ValueKey(value)` / `ft.ScrollKey` — control identity for
  `key=` and `scroll_to(scroll_key=...)`.
- Exceptions: `FletException`, `FletUnsupportedPlatformException`,
  `FletUnimplementedPlatformException`, `FletPageDisconnectedException`.
- Base events: `Event(control, data, name, page)`, `ControlEvent`,
  handler aliases `EventHandler/ControlEventHandler`.

### 11. Theming (`controls/theme.py`, 44 classes)

```python
ft.Theme(color_scheme=ColorScheme(...), text_theme=TextTheme(...),
          visual_density, use_material3=True, page_transitions=...,
          appbar_theme=AppBarTheme(...), ... )  # one per control family
page.theme = light; page.dark_theme = dark; page.theme_mode = ft.ThemeMode.SYSTEM
```

`ColorScheme` (~40 M3 slots: `primary on_primary surface on_surface error
...`); per-control themes (`ButtonTheme OutlinedButtonTheme TextButtonTheme
FilledButtonTheme IconButtonTheme CardTheme ChipTheme DialogTheme
BottomSheetTheme NavigationBarTheme NavigationRailTheme NavigationDrawerTheme
SliderTheme SwitchTheme CheckboxTheme RadioTheme BadgeTheme DividerTheme
SnackBarTheme BannerTheme DatePickerTheme TimePickerTheme DropdownTheme
ListTileTheme TooltipTheme ExpansionTileTheme ProgressIndicatorTheme
PopupMenuTheme SearchBarTheme SearchViewTheme SegmentedButtonTheme IconTheme
DataTableTheme TabBarTheme ScrollbarTheme BottomAppBarTheme AppBarTheme
FloatingActionButtonTheme`); `TextTheme` (per-`TextThemeStyle` overrides);
`SystemOverlayStyle`; `PageTransitionsTheme`.
Any `Container.theme/dark_theme/theme_mode` scopes a subtree theme.

### 12. Auth (`auth/`)

`Authorization` (abstract) / `AuthorizationService` (OAuth impl behind
`page.login`); `OAuthProvider` + presets `GoogleOAuthProvider`,
`GitHubOAuthProvider`, `AzureOAuthProvider`, `Auth0OAuthProvider`;
`OAuthToken` (access/refresh/id, expiry, scopes); `User` / `Group`
(dict subclasses with profile claims).

### 13. PubSub (`pubsub/`)

`page.pubsub` (`PubSubClient` over process-wide `PubSubHub`):
`subscribe(topic, handler)`, `unsubscribe`, `send(topic, message)`,
`send_all(message)` — fan-out across sessions of one server process.

### 14. Testing (`testing/`, `pytest_plugin.py`, `security/`)

```python
t = ft.Tester()  # registered service in tests
await t.pump(duration=None) / t.pump_and_settle(...)
await t.find_by_text(text) / find_by_text_containing(pattern) / find_by_key(key)
     / find_by_tooltip(value) / find_by_icon(icon) -> Finder
finder.first() / .last() / .at(i)
await t.tap(f) / mouse_click(f) / right_mouse_click(f) / mouse_double_click(f)
await t.tap_at(offset) / ..._at(...) / drag(f, offset) / drag_from(start, offset)
await t.long_press(f) / enter_text(f, text) / mouse_hover(f)
await t.take_screenshot(name) -> bytes
await t.teardown(timeout=10)
FletTestApp(...) / DisposalMode  # Flutter-side integration controller
```

`flet.pytest_plugin` (the `flet` pytest11 entry point) wires fixtures for
the above. `flet.security`: `encrypt/decrypt(plain_text, secret_key)` and
`encrypt_aes_gcm_256/decrypt_aes_gcm_256`.

### 15. Declarative extras & internals worth knowing

- `ft.create_context` contexts double as providers when CALLED:
  `MyCtx(value, lambda: Child())` nests a provider (used by Router
  internals; available to app code for scoped state).
- `Session` / `SessionStore` (`messaging/`) — per-session k/v store
  (`page.session`); `DataChannel` — raw byte channels for controls.
- `fastapi/` — `FletApp/FletOAuth/FletStaticFiles/FletUpload/app/app_manager`
  for serving Flet as ASGI.
- `utils/` (38 exports): platform checks (`is_mobile/is_ios/is_android/
  is_windows/is_macos/is_linux/is_pyodide/is_embedded/is_asyncio`),
  `get_free_tcp_port/get_local_ip`, `slugify`, `random_string`, `sha1`,
  `calculate_file_hash`, `open_in_browser`, `which`, file-tree helpers,
  `deprecated/deprecated_class` decorators, validation `V` builders.
- `controls/object_patch.py` + `messaging/protocol.py` — the diff/sync wire
  layer; not app-facing, but explains why whole-value assignment +
  `.update()` is the flush model.

---

## App usage & correctness

Scope: all of `src/**/*.py` (91 distinct `ft.*` names used) and
`tests/test_all_screens_render.py`, `test_render.py`, `test_routes.py`,
`test_tab_crashes.py`. Zero live references to non-existent `ft.*` names.

### (a) Correct usage (verified against source signatures)

- **Router + views** (`src/app_shell.py`, `src/main.py:726-734`):
  `ft.Router(_ROUTES, not_found=HomeScreen, manage_views=True)` mounted via
  `page.render_views(...)`; route components return `ft.View`; view-name →
  route map + `page.navigate(route)` (sync, correct) in `main.py:349-372`.
  `use_controller()` inside `@ft.component` views — correct.
- **Reactive state** (`src/core/state.py:114-160`): `@ft.observable`
  `AppState` with whole-value writes; `create_context` × 3
  (`AppStateCtx`, `ControllerMethodsCtx`, `ServiceCtx`) with
  `use_context` accessors — all correct patterns.
- **Services/GC** (`src/main.py:199-211`, `src/services/media_io.py:24-33`):
  `UrlLauncher/Clipboard/Wakelock/Connectivity/FilePicker/Share` appended to
  `page.services` with `not in` guards — exactly what 1.0 requires.
- **Background tasks**: `page.run_task(coro_fn, *args)` throughout
  (`main.py:227,370,415,582,686,694-697,711-722`); comment at `main.py:408-411`
  correctly notes sync fns/lambdas raise `TypeError` (confirmed
  `page.py:848-849`).
- **SnackBars** (`src/core/notify.py:20-46`): `ft.SnackBar(content,
  behavior=FLOATING, duration=<int ms>)` + `page.show_dialog(snack)` —
  correct: `SnackBar` IS a `DialogControl` (`snack_bar.py:155`; same pattern
  at `page.py:1028`), `DurationValue = Duration | int` (int = ms), and the
  pop-and-retry guard correctly refuses to pop non-SnackBar dialogs.
- **Gestures** (`src/screens/onboarding_screen.py:62-69,109-110`):
  `GestureDetector(on_horizontal_drag_end=...)` with
  `e: ft.DragEndEvent` / `e.primary_velocity` — field confirmed
  (`events.py:314`).
- **Swipe-delete** (`src/screens/history_screen.py:76+`):
  `Dismissible(key=ValueKey, content, background, ...)` with padding on the
  `Container`, not the `Row` — correct (see history below).
- **Inputs** (`src/screens/convert_screen.py:151-198`): M3 `Dropdown` +
  `DropdownOption(key, text)` + `on_select` reading `e.control.value`;
  `Chip(label, selected, on_select)`; `Slider(value, min, max, divisions,
  on_change)` — all match signatures.
- **Badge workaround** (`src/app_shell.py:87-110`): `Stack` + `Container` +
  `Margin(left=16, top=-4, ...)` — valid (`MarginValue` accepts negatives;
  no validator on `Margin` fields).
- **Icons**: all 7 `ft.Icons.*` names used (`HOME_OUTLINED HOME_ROUNDED
  HISTORY_ROUNDED SETTINGS_OUTLINED SETTINGS_ROUNDED ADD REMOVE ...`)
  verified present in `icons.json` (8825 entries).
- **Theme** (`src/core/theme.py`, `main.py:186-187,283-287`):
  `Theme/ColorScheme/NavigationBarTheme`, `ThemeMode.SYSTEM/LIGHT/DARK`,
  `page.theme/dark_theme/theme_mode` — correct.
- **Platform/connectivity** (`main.py:213-229,243-257`):
  `ConnectivityType.NONE` comparison, `PagePlatform.*.is_mobile()`-style
  gating (`types.py:843`), `FilePickerFileType.MEDIA` + bytes fallback
  (`media_io.py`), `ShareFile.from_path` (`media_io.py:137`),
  `save_file(src_bytes=...)` with the >100MB RAM guard — all correct.
- **Lifecycle**: `page.on_error/on_platform_brightness_change/on_disconnect/
  on_close` (`main.py:175,183,703-708`) — all real page events.

### (b) Misuse / bugs found

No live wrong-signature or removed-API calls remain — the two historical
crashes are already fixed and pinned by tests. Items are ordered by
actionability:

1. **`ft.Positioned` does not exist in Flet 1.0 — fixed, keep the guard.**
   `src/app_shell.py:90-92` carries the workaround (badge via `Stack` +
   margins) and `tests/test_tab_crashes.py:7,50` pins the regression. Do NOT
   reintroduce `Positioned` in the rewrite; `Stack` has only
   `controls/clip_behavior/alignment/fit` (`stack.py:94-115`).
2. **`ft.Row`/`ft.Column` accept NO `padding` kwarg — fixed, keep the guard.**
   `tests/test_tab_crashes.py:9` and the comment at
   `src/screens/history_screen.py:84-86` document the `TypeError` that froze
   History. Padding belongs on wrapping `Container`s (app-wide pattern is
   already correct).
3. **`AppStateCtx` is created but never provided/consumed**
   (`src/core/state.py:160`). No `use_context(AppStateCtx)` exists anywhere;
   screens read the `state` singleton directly (which works via observable
   subscription inside components). Either wrap the tree in
   `AppStateCtx(state, ...)` for testability or delete the line — dead API
   surface in the rewrite's reference state file.
4. **`ft.View` defaults to `padding=Padding.all(10)`** (`view.py:119`;
   constructor default at field line). `_dashboard_view`
   (`src/app_shell.py:141-161`) and `_tool_view` (`src/app_shell.py:164-180`)
   never override it, so every route carries a 10px outer gutter on top of
   `page.padding = 0` (`src/main.py:188`). Verify this gutter is intended;
   set `padding=0` on the `View`s if full-bleed is wanted.
5. **Tests reach into private Router internals**
   (`tests/test_routes.py:8`: `from flet.components.router import
   _match_routes, _normalize_path`). Works, but any 1.x refactor of the
   private matcher breaks the suite — prefer public coverage via `Renderer`
   (as `test_render.py`/`test_tab_crashes.py` already do) plus route smoke
   tests through `Tester`.
6. **Icon typos fail silently.** `Icons` is a lazy proxy whose `_missing_`
   hook mints a dummy member instead of raising (`icons.py:15-22`), so a
   misspelled `ft.Icons.*` renders blank with no error. The rewrite should
   add a test asserting every `ft.Icons.*`/`ft.CupertinoIcons.*` referenced
   in `src` exists in `icons.json`/`cupertino_icons.json`.

### (c) Underuse — what the app never touches (91 of ~537 names used)

The app leans on ~15 controls + `use_state`/`use_ref`/`use_effect` and
ignores whole subsystems. Ranked adoption list is in the next section.

---

## Underused APIs to adopt

1. **`ft.use_dialog()`** — declarative dialog portal (`dialog | None` per
   render, auto-cleanup on unmount). Replaces the imperative
   `show_dialog`/`pop_dialog` juggling in `main.py:398-404` (media-error
   dialog), `main.py:654-660` (update dialog), and the retry logic in
   `notify.py:39-45`. Preserves nested `TextField` focus across re-renders.
2. **`Control.badge: ft.Badge`** — EVERY control accepts a `Badge`
   (`control.py:101`). Delete the hand-rolled `Stack`+`Container` counter in
   `app_shell.py:87-110` and attach `ft.Badge(label=..., ...)` to the Jobs
   tab icon directly.
3. **`ft.SharedPreferences`** — platform-native k/v (`set/get/contains_key/
   remove/get_keys/clear`, all async). Natural home for `theme_mode`,
   `terms_accepted`, and the settings dict currently hand-rolled in
   `StorageService`.
4. **`ft.HapticFeedback`** — selection/light/medium/heavy haptics. A media
   studio should buzz on job start/complete/fail and on primary CTA presses.
5. **`ft.RangeSlider`** (only 1 use app-wide) — the Cut/trim screen's
   start+end pair is the textbook range-slider case (`start_value/end_value`
   with cross-validated `V` rules built in).
6. **`ft.ReorderableListView`** (`OnReorderEvent`) — the Join queue is
   order-sensitive but has no reorder UI today.
7. **`ft.use_memo` / `ft.use_callback`** — zero uses. Memoize derived lists
   (history rows, probe/stream tables, filter graphs) so observable flips
   elsewhere don't rebuild them.
8. **`on_mounted` / `on_unmounted` / `on_updated`** — zero uses. Own the
   terminal-screen log subscription, connectivity listener, and ad-banner
   attach/detach lifecycles instead of fire-and-forget `run_task`s.
9. **Route `loader=` + `ft.use_route_loader_data()`** — move PyAV probing off
   the click path (`main.py:392`) into route loaders so tool screens render
   with data (or a typed loading state) instead of probe-then-navigate.
10. **`View.can_pop / on_confirm_pop / fullscreen_dialog` + `Route(modal=True)`**
    — result-screen and update-dialog flows should be real modal routes
    (slide-up presentation, structural back-pop) instead of pushed views and
    imperative dialogs.
11. **`ft.Tester` + `Finder`** (`pump/pump_and_settle`, `find_by_text/key/
    icon`, `tap/enter_text/drag`, `take_screenshot`) — today's tests drive
    `Renderer` directly; `Tester` gives black-box widget tests including the
    onboarding swipe and the Dismissible delete.
12. **`ft.TemplateRoute` + `page.query: QueryString` / `page.url`** — the
    hand-rolled `_VIEW_ROUTES` map (`main.py:333-347`) can't parse deep-link
    params (`ffmpeg://app/...`); template matching + query accessors can.
13. **`ft.SearchBar`, `ft.AutoComplete`, `ft.DataTable`, `ft.ExpansionTile`**
    — history search, terminal command completion, probe/streams tables, and
    collapsible probe sections are currently bespoke `TextField`/`Column`
    code that these controls replace.
14. **`ft.is_route_active()`** — nav/tab highlighting without mirroring
    `state.selected_tab`/`active_view` by hand.
15. **`page.pubsub`** — job progress fan-out and cross-view invalidation
    without threading `page.update()` through every callback.

---

## Gotchas

- **No `ft.Positioned`; no `padding` on `Row`/`Column`.** Both raise at
  construction and froze whole tabs pre-fix. Position inside `Stack` with
  `Container(alignment/margin)` or `LayoutControl.offset`; pad with a
  wrapping `Container`.
- **Dialogs ONLY via `page.show_dialog()` / `page.pop_dialog()`.**
  `SnackBar`, `AlertDialog`, `Banner`, `BottomSheet`, pickers are all
  `DialogControl`s — never append them to `page.overlay` or `views`, and
  there is no `page.open_snack_bar` / `page.launch_url` / `page.set_clipboard`
  in 1.0 (all confirmed absent; use `UrlLauncher`/`Clipboard` services).
- **`SnackBar.duration` takes ms-int or `Duration`** (`DurationValue =
  Duration | int`); default is 4000ms, not seconds.
- **`page.navigate()` is sync; `page.push_route()` is async.**
  `page.run_task()` takes ONLY coroutine functions (`TypeError` otherwise —
  no lambdas, no sync fns).
- **Services die if unregistered.** Anything not in `page.services` can be
  GC'd mid-session (transport drops its handle). The app's `not in` guards
  are the pattern to keep.
- **Observable = whole-value assignment.** `state.jobs = [...]` notifies;
  `state.jobs.append(...)` / `state.settings[k] = v` do NOT (unless the field
  holds an `ObservableList`/`ObservableDict`). Same for `use_state`: the
  setter uses `==` — assigning an equal value is a silent no-op.
- **`use_effect(setup, dependencies=None)` runs on mount only** — `None`
  does NOT mean "every render" (that's `on_updated(fn)` with no deps).
- **Deprecated M3 form-field props**: `Dropdown`/`TextField`
  `border_radius/border_color/border_width/focused_border_*` are deprecated
  since 1.0.0, removal 1.3.0 — use `border=OutlineInputBorder(...)` /
  `{ControlState.FOCUSED: ...}` instead. The app correctly avoids them.
- **`Colors`/`CupertinoColors` are str enums** — they compose with plain hex
  strings (`with_opacity(0.12, PRIMARY)`), and `Margin/Padding/BorderRadius`
  fields accept bare numbers (`PaddingValue = Number | Padding`).
- **`Animation` shorthand**: `animate=True` (1000ms linear) or an int
  (ms) anywhere `AnimationValue` appears.
- **`View` defaults**: `padding=Padding.all(10)`, `spacing=10`,
  `route="/"`, `can_pop=True` — set explicitly on every route view.
- **Old navigation is gone**: `page.views` manipulation by hand,
  `on_route_change`-string-switching, and `ft.Positioned` are pre-1.0
  patterns — `Router(manage_views=True)` + `render_views` owns the stack now.
