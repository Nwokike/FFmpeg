# Ability matrix

_Wheel: av 19.0.2 · FFmpeg 9.0.2 · build cbcc9a8fb0e4 · generated 2026-11-14 10:56 UTC · 794/1095 abilities green, 0 failed, 301 skipped_

One row per ability; the test id is the ability. Run `uv run python scripts/ability_report.py` to regenerate.

## Skips

| Ability | Why |
|---|---|
| `test_video_encoder[libwebp]` | libwebp: no container in this wheel carries it |
| `test_video_encoder[a64multi]` | a64multi: no container in this wheel carries it |
| `test_video_encoder[a64multi5]` | a64multi5: no container in this wheel carries it |
| `test_video_encoder[alias_pix]` | alias_pix: no container in this wheel carries it |
| `test_video_encoder[apng]` | apng: no container in this wheel carries it |
| `test_video_encoder[av1_amf]` | av1_amf: hardware-only (13) and this machine has no such device |
| `test_video_encoder[av1_nvenc]` | av1_nvenc: hardware-only (2) and this machine has no such device |
| `test_video_encoder[av1_qsv]` | av1_qsv: hardware-only (5) and this machine has no such device |
| `test_video_encoder[bitpacked]` | bitpacked: no container in this wheel carries it |
| `test_video_encoder[bmp]` | bmp: no container in this wheel carries it |
| `test_video_encoder[dnxhd]` | dnxhd: parameter-constrained codec refused every standard set — mov 1440x1080: Invalid argument: 'avcodec_open |
| `test_video_encoder[fits]` | fits: no container in this wheel carries it |
| `test_video_encoder[flashsv2]` | flashsv2: no container in this wheel carries it |
| `test_video_encoder[h263_v4l2m2m]` | h263_v4l2m2m: a null/wrapper pass-through, nothing to probe |
| `test_video_encoder[h264_amf]` | h264_amf: hardware-only (13) and this machine has no such device |
| `test_video_encoder[h264_nvenc]` | h264_nvenc: hardware-only (2) and this machine has no such device |
| `test_video_encoder[h264_qsv]` | h264_qsv: hardware-only (5) and this machine has no such device |
| `test_video_encoder[h264_v4l2m2m]` | h264_v4l2m2m: a null/wrapper pass-through, nothing to probe |
| `test_video_encoder[hdr]` | hdr: no container in this wheel carries it |
| `test_video_encoder[hevc_amf]` | hevc_amf: hardware-only (13) and this machine has no such device |
| `test_video_encoder[hevc_nvenc]` | hevc_nvenc: hardware-only (2) and this machine has no such device |
| `test_video_encoder[hevc_qsv]` | hevc_qsv: hardware-only (5) and this machine has no such device |
| `test_video_encoder[hevc_v4l2m2m]` | hevc_v4l2m2m: a null/wrapper pass-through, nothing to probe |
| `test_video_encoder[libwebp_anim]` | libwebp_anim: no container in this wheel carries it |
| `test_video_encoder[mjpeg_qsv]` | mjpeg_qsv: hardware-only (5) and this machine has no such device |
| `test_video_encoder[mpeg2_qsv]` | mpeg2_qsv: hardware-only (5) and this machine has no such device |
| `test_video_encoder[mpeg4_v4l2m2m]` | mpeg4_v4l2m2m: a null/wrapper pass-through, nothing to probe |
| `test_video_encoder[msrle]` | msrle: palette-only output (pal8) — needs a pal8 source |
| `test_video_encoder[pam]` | pam: no container in this wheel carries it |
| `test_video_encoder[pbm]` | pbm: no container in this wheel carries it |
| `test_video_encoder[pcx]` | pcx: no container in this wheel carries it |
| `test_video_encoder[pdv]` | pdv: no container in this wheel carries it |
| `test_video_encoder[pfm]` | pfm: no container in this wheel carries it |
| `test_video_encoder[pgm]` | pgm: no container in this wheel carries it |
| `test_video_encoder[pgmyuv]` | pgmyuv: no container in this wheel carries it |
| `test_video_encoder[phm]` | phm: no container in this wheel carries it |
| `test_video_encoder[ppm]` | ppm: no container in this wheel carries it |
| `test_video_encoder[qoi]` | qoi: no container in this wheel carries it |
| `test_video_encoder[roqvideo]` | roqvideo: no container in this wheel carries it |
| `test_video_encoder[smc]` | smc: palette-only output (pal8) — needs a pal8 source |
| `test_video_encoder[sunrast]` | sunrast: no container in this wheel carries it |
| `test_video_encoder[vbn]` | vbn: no container in this wheel carries it |
| `test_video_encoder[vc2]` | vc2: parameter-constrained codec refused every standard set — mp4 1440x1080: Invalid argument: 'avcodec_send_f |
| `test_video_encoder[vnull]` | vnull: a null/wrapper pass-through, nothing to probe |
| `test_video_encoder[vp8_v4l2m2m]` | vp8_v4l2m2m: a null/wrapper pass-through, nothing to probe |
| `test_video_encoder[vp9_qsv]` | vp9_qsv: hardware-only (5) and this machine has no such device |
| `test_video_encoder[wbmp]` | wbmp: no container in this wheel carries it |
| `test_video_encoder[wrapped_avframe]` | wrapped_avframe: no container in this wheel carries it |
| `test_video_encoder[xbm]` | xbm: no container in this wheel carries it |
| `test_video_encoder[xface]` | xface: no container in this wheel carries it |
| `test_video_encoder[xwd]` | xwd: no container in this wheel carries it |
| `test_video_encoder[zmbv]` | zmbv: palette-only output (bgr0) — needs a pal8 source |
| `test_audio_encoder[adpcm_adx]` | adpcm_adx: no container in this wheel carries it |
| `test_audio_encoder[adpcm_argo]` | adpcm_argo: no container in this wheel carries it |
| `test_audio_encoder[adpcm_ima_alp]` | adpcm_ima_alp: no container in this wheel carries it |
| `test_audio_encoder[adpcm_ima_amv]` | adpcm_ima_amv: no container in this wheel carries it |
| `test_audio_encoder[adpcm_ima_apm]` | adpcm_ima_apm: no container in this wheel carries it |
| `test_audio_encoder[adpcm_ima_ssi]` | adpcm_ima_ssi: no container in this wheel carries it |
| `test_audio_encoder[adpcm_ima_ws]` | adpcm_ima_ws: no container in this wheel carries it |
| `test_audio_encoder[anull]` | anull: a null/wrapper pass-through, nothing to probe |
| `test_audio_encoder[aptx]` | aptx: no container in this wheel carries it |
| `test_audio_encoder[aptx_hd]` | aptx_hd: no container in this wheel carries it |
| `test_audio_encoder[comfortnoise]` | comfortnoise: no container in this wheel carries it |
| `test_audio_encoder[g723_1]` | g723_1: native crash (-11) contained by the process boundary |
| `test_audio_encoder[g726]` | g726: native crash (-11) contained by the process boundary |
| `test_audio_encoder[g726le]` | g726le: no container in this wheel carries it |
| `test_audio_encoder[pcm_bluray]` | pcm_bluray: no container in this wheel carries it |
| `test_audio_encoder[pcm_dvd]` | pcm_dvd: no container in this wheel carries it |
| `test_audio_encoder[pcm_s16be_planar]` | pcm_s16be_planar: no container in this wheel carries it |
| `test_audio_encoder[pcm_s16le_planar]` | pcm_s16le_planar: no container in this wheel carries it |
| `test_audio_encoder[pcm_s24daud]` | pcm_s24daud: no container in this wheel carries it |
| `test_audio_encoder[pcm_s24le_planar]` | pcm_s24le_planar: no container in this wheel carries it |
| `test_audio_encoder[pcm_s32le_planar]` | pcm_s32le_planar: no container in this wheel carries it |
| `test_audio_encoder[pcm_s64be]` | pcm_s64be: no container in this wheel carries it |
| `test_audio_encoder[pcm_s8_planar]` | pcm_s8_planar: no container in this wheel carries it |
| `test_audio_encoder[pcm_u16be]` | pcm_u16be: no container in this wheel carries it |
| `test_audio_encoder[pcm_u16le]` | pcm_u16le: no container in this wheel carries it |
| `test_audio_encoder[pcm_u24be]` | pcm_u24be: no container in this wheel carries it |
| `test_audio_encoder[pcm_u24le]` | pcm_u24le: no container in this wheel carries it |
| `test_audio_encoder[pcm_u32be]` | pcm_u32be: no container in this wheel carries it |
| `test_audio_encoder[pcm_u32le]` | pcm_u32le: no container in this wheel carries it |
| `test_audio_encoder[pcm_vidc]` | pcm_vidc: no container in this wheel carries it |
| `test_audio_encoder[real_144]` | real_144: native crash (-11) contained by the process boundary |
| `test_audio_encoder[roq_dpcm]` | roq_dpcm: no container in this wheel carries it |
| `test_audio_encoder[sbc]` | sbc: no container in this wheel carries it |
| `test_muxer[3g2]` | 3g2: Invalid argument: 'avcodec_open2("h263", {})' returned 22; last error log: [h263] The specified picture s |
| `test_muxer[3gp]` | 3gp: Invalid argument: 'avcodec_open2("h263", {})' returned 22; last error log: [h263] The specified picture s |
| `test_muxer[a64]` | a64: raw stream written, not self-describing ([Errno 1094995529] Invalid data found when processing input: '/t |
| `test_muxer[ac4]` | ac4: no encodable default codec in this wheel |
| `test_muxer[aea]` | aea: no encodable default codec in this wheel |
| `test_muxer[alsa]` | alsa: a raw/pseudo target with no file extension |
| `test_muxer[amr]` | amr: no encodable default codec in this wheel |
| `test_muxer[amv]` | amv: Invalid argument: 'avcodec_open2("adpcm_ima_amv", {})' returned 22; last error log: [adpcm_ima_amv] 22050 |
| `test_muxer[apv]` | apv: no encodable default codec in this wheel |
| `test_muxer[argo_asf]` | argo_asf: a raw/pseudo target with no file extension |
| `test_muxer[argo_cvg]` | argo_cvg: no encodable default codec in this wheel |
| `test_muxer[asf]` | asf: Invalid argument: 'avcodec_open2("wmav2", {})' returned 22; last error log: [wmav2] bitrate too low: got  |
| `test_muxer[asf_stream]` | asf_stream: Invalid argument: 'avcodec_open2("wmav2", {})' returned 22; last error log: [wmav2] bitrate too lo |
| `test_muxer[ass]` | ass: no encodable default codec in this wheel |
| `test_muxer[avif]` | avif: [Errno 1313558101] Unknown error occurred: 'avcodec_open2("av1_amf", {})'; last error log: [av1_amf] Fai |
| `test_muxer[avm2]` | avm2: a raw/pseudo target with no file extension |
| `test_muxer[avs2]` | avs2: no encodable default codec in this wheel |
| `test_muxer[avs3]` | avs3: no encodable default codec in this wheel |
| `test_muxer[bit]` | bit: no encodable default codec in this wheel |
| `test_muxer[cavsvideo]` | cavsvideo: no encodable default codec in this wheel |
| `test_muxer[codec2]` | codec2: no encodable default codec in this wheel |
| `test_muxer[codec2raw]` | codec2raw: no encodable default codec in this wheel |
| `test_muxer[crc]` | crc: a raw/pseudo target with no file extension |
| `test_muxer[dash]` | dash: [Errno 1313558101] Unknown error occurred: 'avcodec_open2("h264_amf", {})'; last error log: [h264_amf] F |
| `test_muxer[data]` | data: no encodable default codec in this wheel |
| `test_muxer[daud]` | daud: Invalid argument: '/tmp/pytest-of-maikel/pytest-58/ability196/mux_daud.daud' returned 22; last error log |
| `test_muxer[dirac]` | dirac: Invalid argument: 'avcodec_send_frame()' returned 22 |
| `test_muxer[dnxhd]` | dnxhd: Invalid argument: 'avcodec_open2("dnxhd", {})' returned 22; last error log: [dnxhd] Frame size: 1440x10 |
| `test_muxer[dts]` | dts: no encodable default codec in this wheel |
| `test_muxer[dv]` | dv: [Errno 1094995529] Invalid data found when processing input: '/tmp/pytest-of-maikel/pytest-58/ability200/m |
| `test_muxer[evc]` | evc: no encodable default codec in this wheel |
| `test_muxer[f32be]` | f32be: a raw/pseudo target with no file extension |
| `test_muxer[f32le]` | f32le: a raw/pseudo target with no file extension |
| `test_muxer[f64be]` | f64be: a raw/pseudo target with no file extension |
| `test_muxer[f64le]` | f64le: a raw/pseudo target with no file extension |
| `test_muxer[fbdev]` | fbdev: a raw/pseudo target with no file extension |
| `test_muxer[ffmetadata]` | ffmetadata: no encodable default codec in this wheel |
| `test_muxer[fifo]` | fifo: no encodable default codec in this wheel |
| `test_muxer[film_cpk]` | film_cpk: Invalid argument: '/tmp/pytest-of-maikel/pytest-58/ability204/mux_film_cpk.cpk' returned 22; last er |
| `test_muxer[filmstrip]` | filmstrip: [Errno 1094995529] Invalid data found when processing input: '/tmp/pytest-of-maikel/pytest-58/abili |
| `test_muxer[framecrc]` | framecrc: a raw/pseudo target with no file extension |
| `test_muxer[framehash]` | framehash: a raw/pseudo target with no file extension |
| `test_muxer[framemd5]` | framemd5: a raw/pseudo target with no file extension |
| `test_muxer[g722]` | g722: Invalid argument: 'avcodec_open2("g722", {})' returned 22; last error log: [g722] mono |
| `test_muxer[g723_1]` | g723_1: Invalid argument: 'avcodec_open2("g723_1", {})' returned 22; last error log: [g723_1] mono |
| `test_muxer[g726]` | g726: a raw/pseudo target with no file extension |
| `test_muxer[g726le]` | g726le: a raw/pseudo target with no file extension |
| `test_muxer[gsm]` | gsm: no encodable default codec in this wheel |
| `test_muxer[gxf]` | gxf: Invalid argument: '/tmp/pytest-of-maikel/pytest-58/ability212/mux_gxf.gxf' returned 22; last error log: [ |
| `test_muxer[h261]` | h261: Invalid argument: 'avcodec_open2("h261", {})' returned 22; last error log: [h261] The specified picture  |
| `test_muxer[h263]` | h263: Invalid argument: 'avcodec_open2("h263", {})' returned 22; last error log: [h263] The specified picture  |
| `test_muxer[h264]` | h264: [Errno 1313558101] Unknown error occurred: 'avcodec_open2("h264_amf", {})'; last error log: [h264_amf] F |
| `test_muxer[hash]` | hash: a raw/pseudo target with no file extension |
| `test_muxer[hds]` | hds: a raw/pseudo target with no file extension |
| `test_muxer[hevc]` | hevc: [Errno 1313558101] Unknown error occurred: 'avcodec_open2("hevc_amf", {})'; last error log: [hevc_amf] F |
| `test_muxer[hls]` | hls: [Errno 1313558101] Unknown error occurred: 'avcodec_open2("h264_amf", {})'; last error log: [h264_amf] Fa |
| `test_muxer[iamf]` | iamf: Invalid argument: '/tmp/pytest-of-maikel/pytest-58/ability218/mux_iamf.iamf' returned 22; last error log |
| `test_muxer[ico]` | ico: Invalid argument: '/tmp/pytest-of-maikel/pytest-58/ability219/mux_ico.ico' returned 22; last error log: [ |
| `test_muxer[ilbc]` | ilbc: no encodable default codec in this wheel |
| `test_muxer[image2]` | image2: Invalid argument: '/tmp/pytest-of-maikel/pytest-58/ability220/mux_image2.tiff' returned 22; last error |
| `test_muxer[image2pipe]` | image2pipe: a raw/pseudo target with no file extension |
| `test_muxer[ivf]` | ivf: [Errno 1313558101] Unknown error occurred: 'avcodec_open2("av1_amf", {})'; last error log: [av1_amf] Fail |
| `test_muxer[jacosub]` | jacosub: no encodable default codec in this wheel |
| `test_muxer[lc3]` | lc3: no encodable default codec in this wheel |
| `test_muxer[lrc]` | lrc: no encodable default codec in this wheel |
| `test_muxer[mcc]` | mcc: no encodable default codec in this wheel |
| `test_muxer[md5]` | md5: a raw/pseudo target with no file extension |
| `test_muxer[microdvd]` | microdvd: no encodable default codec in this wheel |
| `test_muxer[mkvtimestamp_v2]` | mkvtimestamp_v2: a raw/pseudo target with no file extension |
| `test_muxer[mlp]` | mlp: no encodable default codec in this wheel |
| `test_muxer[mmf]` | mmf: Invalid argument: '/tmp/pytest-of-maikel/pytest-58/ability230/mux_mmf.mmf' returned 22; last error log: [ |
| `test_muxer[mxf]` | mxf: [Errno 1] Operation not permitted: '/tmp/pytest-of-maikel/pytest-58/ability241/mux_mxf.mxf'; last error l |
| `test_muxer[mxf_d10]` | mxf_d10: a raw/pseudo target with no file extension |
| `test_muxer[mxf_opatom]` | mxf_opatom: Invalid argument: 'avcodec_open2("dnxhd", {})' returned 22; last error log: [dnxhd] Frame size: 14 |
| `test_muxer[null]` | null: a raw/pseudo target with no file extension |
| `test_muxer[obu]` | obu: [Errno 1313558101] Unknown error occurred: 'avcodec_open2("av1_amf", {})'; last error log: [av1_amf] Fail |
| `test_muxer[oma]` | oma: Invalid argument: '/tmp/pytest-of-maikel/pytest-58/ability248/mux_oma.oma' returned 22; last error log: [ |
| `test_muxer[oss]` | oss: a raw/pseudo target with no file extension |
| `test_muxer[pdv]` | pdv: [Errno 733130664] Experimental feature: 'avcodec_open2("pdv", {})'; last error log: [pdv] The encoder 'pd |
| `test_muxer[psp]` | psp: Invalid argument: '/tmp/pytest-of-maikel/pytest-58/ability251/mux_psp.psp' returned 22; last error log: [ |
| `test_muxer[rawvideo]` | rawvideo: raw stream written, not self-describing (Invalid argument: '/tmp/pytest-of-maikel/pytest-58/ability2 |
| `test_muxer[rcwt]` | rcwt: no encodable default codec in this wheel |
| `test_muxer[roq]` | roq: Invalid argument: 'avcodec_open2("roq_dpcm", {})' returned 22; last error log: [roq_dpcm] Audio must be 2 |
| `test_muxer[rso]` | rso: [Errno 1094995529] Invalid data found when processing input: '/tmp/pytest-of-maikel/pytest-58/ability255/ |
| `test_muxer[rtp]` | rtp: a raw/pseudo target with no file extension |
| `test_muxer[rtp_mpegts]` | rtp_mpegts: a raw/pseudo target with no file extension |
| `test_muxer[rtsp]` | rtsp: a raw/pseudo target with no file extension |
| `test_muxer[s16be]` | s16be: a raw/pseudo target with no file extension |
| `test_muxer[s24be]` | s24be: a raw/pseudo target with no file extension |
| `test_muxer[s24le]` | s24le: a raw/pseudo target with no file extension |
| `test_muxer[s32be]` | s32be: a raw/pseudo target with no file extension |
| `test_muxer[s32le]` | s32le: a raw/pseudo target with no file extension |
| `test_muxer[sap]` | sap: a raw/pseudo target with no file extension |
| `test_muxer[scc]` | scc: no encodable default codec in this wheel |
| `test_muxer[segment]` | segment: no encodable default codec in this wheel |
| `test_muxer[smoothstreaming]` | smoothstreaming: a raw/pseudo target with no file extension |
| `test_muxer[spx]` | spx: no encodable default codec in this wheel |
| `test_muxer[srt]` | srt: no encodable default codec in this wheel |
| `test_muxer[stream_segment,ssegment]` | stream_segment,ssegment: no encodable default codec in this wheel |
| `test_muxer[streamhash]` | streamhash: a raw/pseudo target with no file extension |
| `test_muxer[sup]` | sup: no encodable default codec in this wheel |
| `test_muxer[tee]` | tee: no encodable default codec in this wheel |
| `test_muxer[truehd]` | truehd: no encodable default codec in this wheel |
| `test_muxer[ttml]` | ttml: no encodable default codec in this wheel |
| `test_muxer[u16be]` | u16be: a raw/pseudo target with no file extension |
| `test_muxer[u24be]` | u24be: a raw/pseudo target with no file extension |
| `test_muxer[u24le]` | u24le: a raw/pseudo target with no file extension |
| `test_muxer[u32be]` | u32be: a raw/pseudo target with no file extension |
| `test_muxer[u32le]` | u32le: a raw/pseudo target with no file extension |
| `test_muxer[uncodedframecrc]` | uncodedframecrc: a raw/pseudo target with no file extension |
| `test_muxer[vc1]` | vc1: no encodable default codec in this wheel |
| `test_muxer[vc1test]` | vc1test: no encodable default codec in this wheel |
| `test_muxer[vcd]` | vcd: a raw/pseudo target with no file extension |
| `test_muxer[vidc]` | vidc: a raw/pseudo target with no file extension |
| `test_muxer[video4linux2,v4l2]` | video4linux2,v4l2: a raw/pseudo target with no file extension |
| `test_muxer[vvc]` | vvc: no encodable default codec in this wheel |
| `test_muxer[webm_chunk]` | webm_chunk: no encodable default codec in this wheel |
| `test_muxer[webm_dash_manifest]` | webm_dash_manifest: no encodable default codec in this wheel |
| `test_muxer[webvtt]` | webvtt: no encodable default codec in this wheel |
| `test_muxer[whip]` | whip: a raw/pseudo target with no file extension |
| `test_container[video:mp4]` | mp4: [Errno 1313558101] Unknown error occurred: 'avcodec_open2("av1_amf", {})'; last error log: [av1_amf] Fail |
| `test_container[video:mkv]` | mkv: [Errno 1313558101] Unknown error occurred: 'avcodec_open2("av1_amf", {})'; last error log: [av1_amf] Fail |
| `test_container[video:mov]` | mov: [Errno 1313558101] Unknown error occurred: 'avcodec_open2("av1_amf", {})'; last error log: [av1_amf] Fail |
| `test_container[video:webm]` | webm: [Errno 1313558101] Unknown error occurred: 'avcodec_open2("av1_amf", {})'; last error log: [av1_amf] Fai |
| `test_container[video:m4a]` | m4a: [Errno 1313558101] Unknown error occurred: 'avcodec_open2("h264_amf", {})'; last error log: [h264_amf] Fa |
| `test_container[video:3g2]` | 3g2: Invalid argument: 'avcodec_open2("h263", {})' returned 22; last error log: [h263] The specified picture s |
| `test_container[video:3gp]` | 3gp: Invalid argument: 'avcodec_open2("h263", {})' returned 22; last error log: [h263] The specified picture s |
| `test_container[video:avif]` | avif: [Errno 1313558101] Unknown error occurred: 'avcodec_open2("av1_amf", {})'; last error log: [av1_amf] Fai |
| `test_container[video:drc]` | drc: Invalid argument: 'avcodec_send_frame()' returned 22 |
| `test_container[video:f4v]` | f4v: [Errno 1313558101] Unknown error occurred: 'avcodec_open2("h264_amf", {})'; last error log: [h264_amf] Fa |
| `test_container[video:gxf]` | gxf: Invalid argument: '/tmp/pytest-of-maikel/pytest-58/ability295/container_gxf.gxf' returned 22; last error  |
| `test_container[video:h261]` | h261: Invalid argument: 'avcodec_open2("h261", {})' returned 22; last error log: [h261] The specified picture  |
| `test_container[video:h263]` | h263: Invalid argument: 'avcodec_open2("h263", {})' returned 22; last error log: [h263] The specified picture  |
| `test_container[video:h264]` | h264: [Errno 1313558101] Unknown error occurred: 'avcodec_open2("h264_amf", {})'; last error log: [h264_amf] F |
| `test_container[video:hevc]` | hevc: [Errno 1313558101] Unknown error occurred: 'avcodec_open2("hevc_amf", {})'; last error log: [hevc_amf] F |
| `test_container[video:ismv]` | ismv: [Errno 1313558101] Unknown error occurred: 'avcodec_open2("av1_amf", {})'; last error log: [av1_amf] Fai |
| `test_container[video:ivf]` | ivf: [Errno 1313558101] Unknown error occurred: 'avcodec_open2("av1_amf", {})'; last error log: [av1_amf] Fail |
| `test_container[video:mxf]` | mxf: [Errno 1] Operation not permitted: '/tmp/pytest-of-maikel/pytest-58/ability310/container_mxf.mxf'; last e |
| `test_container[video:obu]` | obu: [Errno 1313558101] Unknown error occurred: 'avcodec_open2("av1_amf", {})'; last error log: [av1_amf] Fail |
| `test_container[video:pdv]` | pdv: [Errno 733130664] Experimental feature: 'avcodec_open2("pdv", {})'; last error log: [pdv] The encoder 'pd |
| `test_container[video:psp]` | psp: [Errno 1313558101] Unknown error occurred: 'avcodec_open2("av1_amf", {})'; last error log: [av1_amf] Fail |
| `test_container[video:rm]` | rm: Invalid argument: 'avcodec_open2("rv10", {})' returned 22; last error log: [rv10] width and height must be |
| `test_container[audio:amv]` | amv: Invalid argument: 'avcodec_open2("adpcm_ima_amv", {})' returned 22; last error log: [adpcm_ima_amv] 22050 |
| `test_container[audio:asf]` | asf: Invalid argument: 'avcodec_open2("wmav2", {})' returned 22; last error log: [wmav2] bitrate too low: got  |
| `test_container[audio:cpk]` | cpk: Invalid argument: '/tmp/pytest-of-maikel/pytest-58/ability375/container_cpk.cpk' returned 22; last error  |
| `test_container[audio:daud]` | daud: Invalid argument: '/tmp/pytest-of-maikel/pytest-58/ability376/container_daud.302' returned 22; last erro |
| `test_container[audio:dv]` | dv: [Errno 1094995529] Invalid data found when processing input: '/tmp/pytest-of-maikel/pytest-58/ability379/c |
| `test_container[audio:g723_1]` | g723_1: Invalid argument: 'avcodec_open2("g723_1", {})' returned 22; last error log: [g723_1] mono |
| `test_container[audio:gxf]` | gxf: Invalid argument: '/tmp/pytest-of-maikel/pytest-58/ability389/container_gxf.gxf' returned 22; last error  |
| `test_container[audio:iamf]` | iamf: Invalid argument: '/tmp/pytest-of-maikel/pytest-58/ability390/container_iamf.iamf' returned 22; last err |
| `test_container[audio:mmf]` | mmf: Invalid argument: '/tmp/pytest-of-maikel/pytest-58/ability399/container_mmf.mmf' returned 22; last error  |
| `test_container[audio:mxf]` | mxf: [Errno 1] Operation not permitted: '/tmp/pytest-of-maikel/pytest-58/ability404/container_mxf.mxf'; last e |
| `test_container[audio:psp]` | psp: Invalid argument: '/tmp/pytest-of-maikel/pytest-58/ability413/container_psp.psp' returned 22; last error  |
| `test_container[audio:roq]` | roq: Invalid argument: 'avcodec_open2("roq_dpcm", {})' returned 22; last error log: [roq_dpcm] Audio must be 2 |
| `test_container[audio:rso]` | rso: [Errno 1094995529] Invalid data found when processing input: '/tmp/pytest-of-maikel/pytest-58/ability417/ |
| `test_container[audio:wma]` | wma: Invalid argument: 'avcodec_open2("wmav2", {})' returned 22; last error log: [wmav2] bitrate too low: got  |
| `test_extract_subtitles[ass]` | ass: covered by the container/subs assets |
| `test_extract_subtitles[webvtt]` | webvtt: covered by the container/subs assets |
| `test_video_encoder_option_applies[libsvtav1]` | libsvtav1: Invalid argument: 'avcodec_open2("libsvtav1", {\'crf\': \'30\', \'b\': \'500000\'})' returned 22; l |
| `test_video_encoder_option_applies[libwebp]` | libwebp: no container in this wheel carries it |
| `test_video_encoder_option_applies[a64multi]` | a64multi: no container in this wheel carries it |
| `test_video_encoder_option_applies[a64multi5]` | a64multi5: no container in this wheel carries it |
| `test_video_encoder_option_applies[alias_pix]` | alias_pix: no container in this wheel carries it |
| `test_video_encoder_option_applies[amv]` | amv: [Errno 733130664] Experimental feature: 'avcodec_send_frame()'; last error log: [amv] Heights which are n |
| `test_video_encoder_option_applies[apng]` | apng: no container in this wheel carries it |
| `test_video_encoder_option_applies[av1_amf]` | av1_amf: hardware-only (13) and this machine has no such device |
| `test_video_encoder_option_applies[av1_nvenc]` | av1_nvenc: hardware-only (2) and this machine has no such device |
| `test_video_encoder_option_applies[av1_qsv]` | av1_qsv: hardware-only (5) and this machine has no such device |
| `test_video_encoder_option_applies[bitpacked]` | bitpacked: no container in this wheel carries it |
| `test_video_encoder_option_applies[bmp]` | bmp: no container in this wheel carries it |
| `test_video_encoder_option_applies[dnxhd]` | dnxhd: Invalid argument: 'avcodec_open2("dnxhd", {\'b\': \'500000\'})' returned 22; last error log: [dnxhd] Fr |
| `test_video_encoder_option_applies[dvvideo]` | dvvideo: Invalid argument: 'avcodec_open2("dvvideo", {\'b\': \'500000\'})' returned 22; last error log: [dvvid |
| `test_video_encoder_option_applies[fits]` | fits: no container in this wheel carries it |
| `test_video_encoder_option_applies[flashsv2]` | flashsv2: no container in this wheel carries it |
| `test_video_encoder_option_applies[h261]` | h261: Invalid argument: 'avcodec_open2("h261", {\'b\': \'500000\'})' returned 22; last error log: [h261] The s |
| `test_video_encoder_option_applies[h263]` | h263: Invalid argument: 'avcodec_open2("h263", {\'b\': \'500000\'})' returned 22; last error log: [h263] The s |
| `test_video_encoder_option_applies[h263_v4l2m2m]` | h263_v4l2m2m: a null/wrapper pass-through, nothing to probe |
| `test_video_encoder_option_applies[h264_amf]` | h264_amf: hardware-only (13) and this machine has no such device |
| `test_video_encoder_option_applies[h264_nvenc]` | h264_nvenc: hardware-only (2) and this machine has no such device |
| `test_video_encoder_option_applies[h264_qsv]` | h264_qsv: hardware-only (5) and this machine has no such device |
| `test_video_encoder_option_applies[h264_v4l2m2m]` | h264_v4l2m2m: a null/wrapper pass-through, nothing to probe |
| `test_video_encoder_option_applies[hdr]` | hdr: no container in this wheel carries it |
| `test_video_encoder_option_applies[hevc_amf]` | hevc_amf: hardware-only (13) and this machine has no such device |
| `test_video_encoder_option_applies[hevc_nvenc]` | hevc_nvenc: hardware-only (2) and this machine has no such device |
| `test_video_encoder_option_applies[hevc_qsv]` | hevc_qsv: hardware-only (5) and this machine has no such device |
| `test_video_encoder_option_applies[hevc_v4l2m2m]` | hevc_v4l2m2m: a null/wrapper pass-through, nothing to probe |
| `test_video_encoder_option_applies[libwebp_anim]` | libwebp_anim: no container in this wheel carries it |
| `test_video_encoder_option_applies[mjpeg_qsv]` | mjpeg_qsv: hardware-only (5) and this machine has no such device |
| `test_video_encoder_option_applies[mpeg2_qsv]` | mpeg2_qsv: hardware-only (5) and this machine has no such device |
| `test_video_encoder_option_applies[mpeg4_v4l2m2m]` | mpeg4_v4l2m2m: a null/wrapper pass-through, nothing to probe |
| `test_video_encoder_option_applies[msrle]` | msrle: palette-only output (pal8) — needs a pal8 source |
| `test_video_encoder_option_applies[pam]` | pam: no container in this wheel carries it |
| `test_video_encoder_option_applies[pbm]` | pbm: no container in this wheel carries it |
| `test_video_encoder_option_applies[pcx]` | pcx: no container in this wheel carries it |
| `test_video_encoder_option_applies[pdv]` | pdv: no container in this wheel carries it |
| `test_video_encoder_option_applies[pfm]` | pfm: no container in this wheel carries it |
| `test_video_encoder_option_applies[pgm]` | pgm: no container in this wheel carries it |
| `test_video_encoder_option_applies[pgmyuv]` | pgmyuv: no container in this wheel carries it |
| `test_video_encoder_option_applies[phm]` | phm: no container in this wheel carries it |
| `test_video_encoder_option_applies[ppm]` | ppm: no container in this wheel carries it |
| `test_video_encoder_option_applies[qoi]` | qoi: no container in this wheel carries it |
| `test_video_encoder_option_applies[roqvideo]` | roqvideo: no container in this wheel carries it |
| `test_video_encoder_option_applies[rv10]` | rv10: Invalid argument: 'avcodec_open2("rv10", {\'b\': \'500000\'})' returned 22; last error log: [rv10] width |
| `test_video_encoder_option_applies[rv20]` | rv20: [Errno 1163346256] Not yet implemented in FFmpeg, patches welcome: '/tmp/pytest-of-maikel/pytest-58/abil |
| `test_video_encoder_option_applies[smc]` | smc: palette-only output (pal8) — needs a pal8 source |
| `test_video_encoder_option_applies[sunrast]` | sunrast: no container in this wheel carries it |
| `test_video_encoder_option_applies[vbn]` | vbn: no container in this wheel carries it |
| `test_video_encoder_option_applies[vnull]` | vnull: a null/wrapper pass-through, nothing to probe |
| `test_video_encoder_option_applies[vp8_v4l2m2m]` | vp8_v4l2m2m: a null/wrapper pass-through, nothing to probe |
| `test_video_encoder_option_applies[vp9_qsv]` | vp9_qsv: hardware-only (5) and this machine has no such device |
| `test_video_encoder_option_applies[wbmp]` | wbmp: no container in this wheel carries it |
| `test_video_encoder_option_applies[wrapped_avframe]` | wrapped_avframe: no container in this wheel carries it |
| `test_video_encoder_option_applies[xbm]` | xbm: no container in this wheel carries it |
| `test_video_encoder_option_applies[xface]` | xface: no container in this wheel carries it |
| `test_video_encoder_option_applies[xwd]` | xwd: no container in this wheel carries it |
| `test_video_encoder_option_applies[zmbv]` | zmbv: palette-only output (bgr0) — needs a pal8 source |

## Sections

| Section | Green | Failed | Skipped |
|---|---|---|---|
| Video encoders | 116 | 0 | 110 |
| Audio encoders | 38 | 0 | 33 |
| Muxers | 67 | 0 | 120 |
| Containers | 70 | 0 | 36 |
| Filters | 468 | 0 | 0 |
| Extract targets | 10 | 0 | 2 |
| Tools | 9 | 0 | 0 |
| Probe truth | 14 | 0 | 0 |
| Options reach encoders | 55 | 0 | 58 |
| Self-test & job shape | 1 | 0 | 0 |
