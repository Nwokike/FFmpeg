# flet 1.0.3 core — audit reference

Installed: `.venv/Lib/site-packages/flet`, `ft.__version__==1.0.3`.
NOT in core (separate wheels, also installed): Video, Audio, Camera,
AudioRecorder, Ads, PermissionHandler, Charts, Maps, WebView, Lottie,
Rive, Geolocator. This doc covers core only.

## Relevant surface (verified in wheel)

Material: AlertDialog, AppBar, AutoComplete, Badge, Banner, BottomAppBar,
BottomSheet, Button family, Card, Checkbox, Chip (`selected`+`on_select`
⊕`on_click` invariant; `on_select` internally toggles), CircleAvatar,
Container (`padding/bgcolor/border_radius/ink/on_click/visible/margin/
alignment`), ContextMenu, DataTable, DatePicker/TimePicker, Dialog
(`modal/on_dismiss`), Dismissible (ValueKey, backgrounds, `on_dismiss`),
Divider, Dropdown (+Option, `value/options/on_select`), ExpansionTile,
FilledButton/OutlinedButton/TextButton/IconButton
(`content/icon/height/disabled/tooltip`), FloatingActionButton,
Icon, ListTile, ListView (`spacing/expand/auto_scroll/
build_controls_on_demand`), Markdown (+ExtensionSet, `on_tap_link`
`Any`), MenuBar, NavigationBar (+Destination `icon/selected_icon/label/
badge`, `selected_index` settable post-construction),
NavigationDrawer, PopupMenuButton, ProgressBar (value None =
indeterminate, documented clamp 0–1), ProgressRing, Radio, RangeSlider
(server-side validators: start≥min, ≤end; end≤max — violations raise
ValueError in `before_update`), ReorderableListView, ResponsiveRow
(`columns=12`, breakpoints XS0/SM576/MD768/LG992/XL1200/XXL1400,
`col` ResponsiveNumber), SearchBar, SegmentedButton (+Segment;
re-tap on sole selected does NOT deselect, `on_change` NOT called;
empty `selected` rejected unless `allow_empty_selection`),
Slider, SnackBar (DialogControl; `content/bgcolor/duration/action`;
`show_dialog` raises only on same-instance `==` — dataclass
value-equality, not when another dialog open), Switch, Tabs, Text
(`value/size/weight/max_lines/overflow/selectable/font_family`),
TextField (`value/hint_text/prefix_icon/dense/on_change/on_submit/
autofocus`), Tooltip, VerticalDivider.
Core: Column/Row (Row has NO padding kwarg), Stack, GridView,
GestureDetector (`on_horizontal_drag_end`, DragEndEvent.primary_velocity),
Draggable, DragTarget, Image (`src: str|bytes`, `color/color_blend_mode`),
Audio intentionally NOT core, ShaderMask, BackdropFilter.
Services (page.services, plain `list[Service]`; `Service.__post_init__`
→ `ServiceRegistry.register_service` + `__internal_update()` is the
real mount channel, NOT `page.services.append`): Clipboard (async `set`),
UrlLauncher (async `launch_url`, no `page.launch_url`), Share
(`share_files`→`ShareResult(status)` SUCCESS|DISMISSED|UNAVAILABLE;
`ShareFile.from_path/from_bytes`), FilePicker (`pick_files` returns
`list[FilePickerFile]`; `.bytes` only with `with_data=True`;
`save_file` returns None on cancel; `FileType.MEDIA/IMAGE`),
HapticFeedback, Wakelock (register via services, not append),
Connectivity, Storage, Geolocator NOT core, Auth (`page.login/logout`,
OAuth providers — unused by app), Ads NOT core.
Reactive: `@ft.component`, `use_state` (setter no-op on equal;
accepts value-or-updater), `use_ref`, `use_effect(setup, deps, cleanup)`
(`[]` = mount-only; setup may return cleanup; returning a Future is
ignored), `use_context` (subscribes whole Observable object — NO
field-level tracking), `@ft.observable` (either decorator order;
plain-class supported; `ObservableList/Dict` DO publish on
`append/__setitem__` — but mutating a nested `Job` inside notifies Job,
not AppState), `create_context`, `ft.context.page` (raises RuntimeError
outside app — never returns None), `page.render(fn)` (replaces
views[0].controls + starts scheduler), `page.run_task(coro_fn)`
(requires coroutine function; returns Future; raises on closed loop),
`page.update(*controls)` → `session.patch_control` loop,
`page.show_dialog/pop_dialog` (pop returns topmost-or-None, sets
open=False + update), `View(route/controls/can_pop default True —
route "not currently used by framework")`, `ValueKey`, `Control.page`
raises RuntimeError until mounted (exact message confirmed),
`page.platform_brightness: Optional[Brightness]` (None until host
reports), `page.theme/dark_theme/theme_mode`, `Theme/ColorScheme/
NavigationBarTheme`, `Colors.with_opacity(opacity, color)` (the
documented alpha API — NOT hex suffix), `Animation(duration ms)`.

## Used by app (spot inventory)

Single-view shell (AppShell branches on `active_view`/`active_tab`,
views stays length 1, `views[0].can_pop=False`), NavigationBar +
Badge destinations, SafeArea, ResponsiveRow adaptive grid, Dismissible
history cards, SegmentedButton (theme/A-B compare), RangeSlider
(cut window), Slider family, Chip pickers, Switch, TextField search,
AlertDialog confirms, SnackBar toasts (via notify guard), ListView
screens + auto_scroll terminal pane, GestureDetector onboarding swipe,
Image bytes icons (SRC_IN tint), FilePicker MEDIA/IMAGE + save_file,
Clipboard/UrlLauncher services, Share, Connectivity→is_online,
PermissionHandler/Camera/Video/Audio/Recorder/Ads service mounts,
`page.run_task` bridging, `asyncio.to_thread` for probe/encode,
observable AppState + contexts.

## Unused opportunities

Charts (size/duration stats in probe/history), DataTable/Grid
(stream tables instead of cards), SearchBar (history filter with
built-in semantics), ExpansionTile (per-stream detail, engine-info
sections), BottomSheet variants (share/save sheets), HapticFeedback
(shutter/success ticks), Share `ShareFile.from_bytes` (large-file
mobile save), FilePicker `with_data=True` fallback (fixes mobile
content-URI picks), `on_submit`/autofocus (terminal Enter-to-run),
`build_controls_on_demand` (terminal log virtualization),
`auto_scroll_animation=0` (terminal follow), `Markdown` images policy
(tracking-pixel vector — images bypass link allowlist), `show_close_icon`/
`behavior=FLOATING` SnackBar variants, `ReorderableListView` (join
ordering instead of ↑/↓ buttons — design choice, control exists).
`Auth/page.login` correctly unused (no accounts). Router/TemplateRoute
correctly unused (single-view by design; repath dormant).
