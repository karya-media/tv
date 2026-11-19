# IPTV stream validation improvements

Work is in progress on the `improve-iptv-stream-validation` branch. The HTTP
validator now treats HEAD as a preliminary check and requires a bounded GET
response with readable, non-HTML bytes before marking a stream online. Retry
attempts use a configurable delay; M3U `#EXTVLCOPT` user-agent, referrer,
origin, and cookie settings are carried into validation requests.

The `StreamValidationHistory` repository stores URL-keyed results atomically
and supports quarantine after repeated definitive OFFLINE results. TIMEOUT,
DNS, SSL, geo-restricted, and other uncertain outcomes do not advance the
quarantine count. ONLINE automatically resets it.

FFprobe analysis is available through `ValidateStreamsUseCase` when a
`MediaAnalyzer` is supplied. JSON/CSV reports include probe and HTTP byte
metadata. The remaining pipeline wiring, playlist filtering, deployment
safety, docs, and full test/CI verification are still to be completed.
