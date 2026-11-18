# Speech timing advice

The cue review timing check can estimate a line before generating it. It first looks for at least three accepted cue observations from the same saved review configuration and voice reference. Each observation must match the current text, accepted audio hash and reference hash; the accepted audio bytes are checked too. Replacement candidates retain separate observations until accepted.

For eligible observations, the estimate divides the new line's Unicode letter/mark/number count by the median observed count per second. Observations below 0.4 seconds or four units are excluded. These are conservative evidence floors, not a statistical confidence interval or a universal speech model. Fewer than three compatible samples leaves calibration unavailable; a provider's existing duration estimator may still be used where supported.

The pipeline captures generated speech duration before ReFlow mastering and timing fitting for cloned-speech paths. This is not a measurement of human delivery: a provider may already have paced its output. The estimate cannot predict pauses, emotion, pronunciation or character quality. Do not compare durations across different scripts or configurations as though the rate were universal. The UI reports its basis and warns that delivery varies.

Checking advice does not rewrite text, accept a take or alter the saved manifest. Its fit flag is only a prediction. Actual generated timing and listening review remain necessary. Editing text or changing reference/configuration prevents incompatible evidence from calibrating the result. Non-cloned voice-conversion paths do not currently provide these observations.

Verification uses synthetic audio and review manifests, including raw-duration capture before fitting, insufficient evidence, invalid observations, reference mismatch and preservation of accepted evidence during regeneration. Real-engine and scene-quality acceptance remain separate work.
