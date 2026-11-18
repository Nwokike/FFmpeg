"""Design tokens for FFmpeg — consistent spacing, typography, and geometry."""

from __future__ import annotations

# Spacing scale
SPACE_2XS = 2
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16
SPACE_XL = 24
SPACE_2XL = 32

# Corner radius
RADIUS_SM = 8
RADIUS_MD = 12
RADIUS_LG = 16
RADIUS_XL = 24
RADIUS_FULL = 999

# Typography sizes
FONT_2XS = 10
FONT_XS = 11
FONT_SM = 12
FONT_MD = 14
FONT_LG = 16
FONT_XL = 20
FONT_2XL = 24
FONT_3XL = 28

# Icon sizes
ICON_SM = 16
ICON_MD = 20
ICON_LG = 24
ICON_XL = 32
ICON_HERO = 48

# Animation durations (milliseconds)
ANIM_FAST = 150
ANIM_NORMAL = 250
ANIM_SLOW = 400

# Layout constants — recurring control geometry.
BUTTON_H = 48
STAGE_H = 240
PREVIEW_SM_H = 180
THUMB_STRIP_H = 160
RING_SM = 18
RING_MD = 22
DIALOG_W = 520
DIALOG_H = 420

# Window-size classes (Material 3) — drive the adaptive navigation chrome.
WINDOW_COMPACT_MAX = 599.0  # <= bottom NavigationBar
WINDOW_MEDIUM_MAX = 839.0  # <= icon NavigationRail; above -> sidebar
SIDEBAR_RAIL_WIDTH = 72  # collapsed sidebar
SIDEBAR_EXPANDED_WIDTH = 264  # labelled sidebar
CONTENT_MAX_W = 1100  # reading column cap on expanded windows
