# Release test matrix — v1.0.0 device pass

Execute on hardware against the tag build. Fill Pass/Fail/Notes + device +
build at the bottom; paste the whole table back — failures become work items.

Legend: P = pass, F = fail, N = notes ref (numbered below the table).

## A. Tool × media kind (convert a real file through each)

| # | Tool | Video (mp4/h264) | Audio (mp3/m4a) | Image (jpg/png) | P/F | N |
|---|------|------------------|-----------------|-----------------|-----|---|
| A1 | Convert | | | | | |
| A2 | Compress (16/25/10/5MB) | n/a (video only) | n/a | | | |
| A3 | Cut (copy + re-encode) | | n/a | n/a (gated) | | |
| A4 | Extract audio/frames/gif/subs | | audio only | frames/gif only | | |
| A5 | Filters (EQ/denoise/sharpen/wm) | | n/a (gated) | frame ops only | | |
| A6 | Audio Studio (loudness/bitrate/ch) | audio-bearing file | | n/a (gated) | | |
| A7 | Join (cut + crossfade) | | n/a (rejected) | n/a (rejected) | | |
| A8 | Dossier (remux + report share) | | | | | |
| A9 | Terminal command (convert + cut) | | | | | |

## B. Phone-failure regressions (must all pass)

| # | Regression | Steps | P/F | N |
|---|-----------|-------|-----|---|
| B1 | Cut/Result page-first crash | Open Cut then Result cold; no `Control.page` errors in log | | |
| B2 | Mic pause counter | Record mic, pause 10s, resume — MM:SS frozen while paused | | |
| B3 | Tile over-offer | Compress/Cut tiles offer camera-video only; audio tools mic-only | | |
| B4 | LGPL probe list | Engine Info shows LGPL set, no H.264/MP3 encode offered anywhere | | |
| B5 | Result effect crash | Finish 2 jobs back-to-back; preview swaps cleanly | | |
| B6 | Join fps differ | Join same-camera clips (29.97 + 30.00); crossfade allowed | | |

## C. Streams + HLS + back + consent

| # | Case | Steps | P/F | N |
|---|------|-------|-----|---|
| C1 | HLS master URL | Record a master-variant `.m3u8`; variant resolves, segments land | | |
| C2 | HLS encrypted | EXT-X-KEY stream refuses naming encryption | | |
| C3 | HLS error page | Bad segment URL refuses naming the error page | | |
| C4 | HLS cap | Oversize stream refuses with size+cap; override downloads | | |
| C5 | System back | Tool → dashboard → tab → Home → swallowed (never closes) | | |
| C6 | Consent revoke | Settings → Ad Privacy Choices → withdraw → banners collapse now | | |
| C7 | UMP first run | Fresh install, EEA geography → consent form shows, ads gate on it | | |
| C8 | Capture photo/video/mic | Each take probes, stages, returns to requesting tool | | |
| C9 | Permissions | Deny → rationale; permanent → Settings; restricted → admin copy | | |

## D. AAB inspection outputs (paste from the CI step)

- minSdkVersion:
- versionCode (== build number):
- AdMob APPLICATION_ID present:
- usesCleartextTraffic:

## E. Device + build

- Device(s):
- Build (tag + AAB):
- Date:
- Tester:

## Notes

(numbered notes referenced above)
