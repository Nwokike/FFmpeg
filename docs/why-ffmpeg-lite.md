# Why this project is called FFmpeg Lite

The name is a capability promise: everything FFmpeg can do on *your* device,
and nothing that would fail after you press the button.

## The reason

The app runs on Flet's official mobile FFmpeg wheels (`av` + `flet-libffmpeg`
from [pypi.flet.dev](https://pypi.flet.dev), built by Flet's Mobile Forge).
That wheel uses FFmpeg's **LGPL recipe** — no GPL codec libraries, no bundled
TLS. On Android it therefore ships **without**:

- **H.264 / HEVC / VP9 / AV1 encoding** (decoding and lossless stream copy
  work — only *encoding* is missing)
- **MP3 encoding**
- **An HTTPS handler inside FFmpeg** — the app fetches HTTPS/HLS bytes itself
  with `httpx` and hands them to PyAV, so network streams still work

Desktop wheels are richer, but the product decision is **mobile-first: desktop
exposes the same surface as mobile** (ads fund the app, and phones are where
it ships). Every screen is driven by a live probe of the installed engine
(`src/core/engine_probe.py`): what the wheel cannot do is hidden — never
offered and broken.

Shipping as plain "FFmpeg" would promise the full codec suite the mobile
build cannot deliver. **FFmpeg Lite** says what users actually get: the full
FFmpeg *workflow* — convert, cut, join, extract, filters, audio, streams,
probe — on the codecs the device engine provides.

## Path to the full suite (v2)

No app rewrite is needed:

1. The screens already read the runtime capability probe — no hardcoded
   codec lists anywhere in the UI.
2. The missing piece is upstream: a richer `flet-libffmpeg` wheel (GPL
   encoders + TLS) in Flet's Mobile Forge index. When Flet ships it, bump the
   dependency pin, drop the "Lite" name, and the extra options appear by
   themselves.
3. Until then, capability requests belong upstream at
   [flet-dev/flet issues](https://github.com/flet-dev/flet/issues).

**The rule when editing gates:** never show a control the probe says will
fail on the target device.
