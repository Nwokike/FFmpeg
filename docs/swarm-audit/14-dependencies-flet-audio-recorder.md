# flet-audio-recorder 1.0.3 — audit reference

`AudioRecorder(ft.Service)`: field `configuration`; events
`on_state_change`, `on_upload` (file_name/progress/bytes_uploaded/error),
`on_stream` (raw PCM16BITS chunks only: `chunk/sequence/bytes_streamed`).
Methods: `start_recording(output_path, configuration, upload) -> bool`
(ValueError: non-web file-mode needs output_path; streaming needs
PCM16BITS); `is_recording/is_paused`; `stop_recording() -> path|URL|None
(streaming)`; `cancel/pause/resume_recording`;
`is_supported_encoder(encoder)` (note: no short `is_supported`);
`get_input_devices() -> list[InputDevice(id,label)]`;
`has_permission()` (requests if needed).
`AudioRecorderState`: STOPPED/RECORDING/PAUSED (+ event).
`AudioEncoder` (9): AACLC/AACELD/AACHE/AMRNB/AMRWB/OPUS/FLAC/WAV/PCM16BITS.
`AndroidAudioSource` (11): DEFAULT/MIC/VOICE_UPLINK/VOICE_DOWNLINK/
VOICE_CALL/CAMCORDER/VOICE_RECOGNITION/VOICE_COMMUNICATION/REMOTE_SUBMIX/
UNPROCESSED/VOICE_PERFORMANCE. `AndroidRecorderConfiguration(use_legacy/
mute_audio/manage_bluetooth/audio_source)`. `IosAudioCategoryOption` (8):
MIX_WITH_OTHERS/DUCK_OTHERS/ALLOW_BLUETOOTH/DEFAULT_TO_SPEAKER/
INTERRUPT_SPOKEN_AND_MIX/ALLOW_BLUETOOTH_A2DP/ALLOW_AIRPLAY/
OVERRIDE_MUTED_MIC. `IosRecorderConfiguration(options=[...])`.
`AudioRecorderConfiguration(encoder=WAV, suppress_noise, cancel_echo,
auto_gain, channels=2, sample_rate=44100, bit_rate=128000, device,
android_configuration, ios_configuration)`.
`AudioRecorderUploadSettings(upload_url, method=PUT, headers, file_name)`
— raw PCM16 bytes, no WAV container.

## Used by app (capture_screen + main wiring)

`AudioRecorder()` + `page.services.append`; lifecycle
(`is_recording`+`cancel` teardown, `stop_recording`, `is_recording`
guard, pause/resume + `is_paused` verify); `has_permission`;
`is_supported_encoder` with WAV fallback; `_codec_for` maps
pcm16→WAV/opus→OPUS/aac→AACLC; rate/ch/ext presets;
`AudioRecorderConfiguration(encoder/channels/sample_rate/bit_rate)`;
`start_recording(output_path=bare filename)` — direct file mode only.
`on_stream` always None; `_on_mic_stream/_write_wav/_pcm_rms`/chunk
refs/meter all inert.

## Unused

Input-device picker (`get_input_devices` never called, `device=` never
set, no UI). Streaming path (`on_stream` never wired, PCM16BITS never
selected → meter permanent 0, auto-stop never fires). Upload path
(`on_upload`/UploadSettings/`start_recording(upload=)` never used).
State events (UI polls instead of subscribing). 6 of 9 encoders unused
(AACELD/AACHE/AMRNB/AMRWB/FLAC/PCM16 — chips offer 4 presets).
`suppress_noise/cancel_echo/auto_gain` all default False; all
Android source options + iOS category options untouched; per-call config
only, never service-level default.
