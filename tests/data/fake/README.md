# Fake responses for error cases: FAKE, not real model output

These hand-written files imitate Groq error responses and unusable answers (rate limit, wrong key, cut-off answer, broken references). Each one is marked `"fake": true` with the FAKE label. Tests pass them to `FakeTransport`. Nothing here was recorded from the API.
