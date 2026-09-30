# Why this project is called FFmpeg Lite

The name describes the product's supported capability surface: the FFmpeg workflows we can reliably expose on the target device, using the FFmpeg build that is actually shipped with the app.

## The reason

The app uses Flet's prebuilt mobile binary wheels (`av` + `flet-libffmpeg`) from [pypi.flet.dev](https://pypi.flet.dev).

The mobile FFmpeg build we currently depend on has a more limited codec/feature set than the FFmpeg installations commonly available on desktop. In particular, the Android build does not provide the encoders we need for some common video codecs, including H.264, HEVC, VP9, and AV1, and it does not provide MP3 encoding.

The app also does not rely on FFmpeg for HTTPS transport on mobile. It fetches HTTPS/HLS data itself with `httpx` and passes the resulting stream data to PyAV.

Desktop installations may provide a richer FFmpeg feature set, but the product intentionally uses **mobile as the capability floor**. Desktop exposes the same user-facing surface so that a project created on one platform behaves consistently on another.

Every feature surface is driven by a live probe of the installed engine (`src/core/engine_probe.py`). Capabilities that the installed engine cannot provide are hidden rather than exposed as controls that are expected to fail at runtime.

That is the reason for the **FFmpeg Lite** name. The app still provides the FFmpeg workflow — conversion, cutting, joining, extraction, filtering, audio processing, stream handling, and probing — but only for capabilities supported by the engine actually installed on the target platform.

## Path to a fuller suite

No application rewrite is intended to be necessary.

1. The screens read the runtime capability probe and intersect it with curated display tables (`video_choices` in Convert, `audio_formats` in Extract/Audio). A capability that the probe verifies but that is not present in a display table remains hidden. When widening exposure, update the probe's `PREFERRED_*` lists, the engine alias/label tables, and the relevant screen display table together.

2. The remaining limitations are primarily upstream packaging/build limitations. If a future Flet mobile FFmpeg build provides the missing encoders/features, updating the dependency can make those capabilities available to the app without changing the overall architecture.

3. Until then, requests for additional mobile FFmpeg capabilities belong upstream in the [Flet issue tracker](https://github.com/flet-dev/flet/issues).

## The rule when editing capability gates

Never show a control when the runtime probe says the target engine cannot support it.

And never assume that a probe-verified capability is automatically user-visible: every exposed capability must also be intentionally included in the corresponding screen's display table.
