REFLOW STUDIO - WINDOWS PORTABLE

Release target: Windows portable. Linux and macOS remain experimental.
The bundled core Python is 3.10.11 (64-bit). Optional engines may use separate
Python environments. The package contains runtime libraries and FFmpeg; model
weights and personal settings are excluded from a fresh distribution.

GETTING STARTED

1. Extract the entire package to a folder your account can write to.
   Do not run from inside a ZIP. Paths with spaces are supported.
2. Double-click Launch_Reflow.bat.
3. If a runtime DLL is missing, use the bundled VC_redist.x64.exe when present.
   Windows also needs a working WebView2 runtime to display the interface.
4. Select a workflow, source file, source/target languages, voice and processor.
   Inspect the selected engine's readiness in Marketplace before rendering.
5. Install required optional packages or download models deliberately. Opening
   the UI does not install packages or download every model. A selected engine
   can download its weights on first use; internet and disk space are required.
   Gated models require the publisher's access approval and local authentication.
6. For standard audio/video dubbing, use dialogue review when a translation
   cannot fit its timing. Check the wording, audition takes and accept fitting
   takes before exporting. Keep a copy of your original input.

PIPELINE AND LIMITS

The workflow runs preprocessing, transcription, translation, speech generation,
timing/mixing and export, with optional visual stages where supported. Nodes
configure this fixed stage order; arbitrary graph execution is not implemented.
Multiple voice nodes alternate cues; automatic speaker identification is not
implemented. Parallel workers prepare cues within bounded limits. Heavy shared
model inference can remain serialized; worker count does not guarantee speedup.

Translation follows the engine selected in Marketplace (for example NLLB or
IndicTrans2). Speech follows the selected speech engine and voice profile.
IndicTrans2 translates text; it does not generate audio. Engine availability,
language support and output quality vary by route and installed models.

Assisted dialogue review is optional and explicitly configured for a local
compatible service or an API. Reflow does not automatically discover Ollama,
install a manager model or select Llama. Remote use requires explicit configuration
and applicable consent. Suggestions remain subject to human review and acceptance.

Resource estimates are approximate and are not calibrated speed guarantees.
CPU inference can be slow. Monitor progress and hardware usage; optional stages
and long files can add substantial time, memory and disk requirements.

RECOVERY AND TROUBLESHOOTING

Only one desktop instance may open a given portable folder at a time. Close the
existing window (including a minimized tray window) before relaunching it.
After interruption, review the recovery prompt. Restored batches start paused;
resume deliberately. Dismissing the prompt preserves the recovery record.

Missing frontend: this package is incomplete; obtain a complete portable build.
Missing model/package: check the chosen engine's readiness and setup guidance.
Permission denied: move the extracted package to a writable folder.
Missing media executable: confirm the bundled ffmpeg folder was extracted.
For support, preserve the relevant log and error message. Remove private media,
credentials and personal information before sharing a diagnostic report.

RELEASE STATUS AND LICENSES

See docs/RELEASE_READINESS_2026-10-04.md in the source workspace for the evolving
validation record. Test counts alone do not certify all engines, languages or
media. Consult each model/runtime publisher's license and access conditions;
the application's license does not grant rights to third-party models or media.
Do not interpret experimental Linux/macOS launchers as tested portable releases.
