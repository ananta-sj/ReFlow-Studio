# Publishing source and automatic previews

The current checkout is `C:\Projects\Reflow Studio\Github\ReFlow-Studio`, on
`main`. The former large native installation is not required to publish source.
Do not create another branch unless you deliberately want one.

## Push with GitHub Desktop

1. Add/select this existing repository and confirm Current Branch is `main`.
2. Review Changes. Keep `PRIVATE-RECOVERY`, settings, models, runtimes, recordings,
   outputs and generated build directories excluded. Do not force-add them.
3. Commit the reviewed changes to `main`, then click **Push origin**.
4. Open the repository's Actions tab and watch **Build native desktop candidates**.
5. After source plus all four platform jobs pass, **Update Development Preview**
   publishes/updates the rolling testing pre-release automatically.

Suggested commit for this workflow update:
`Automate cross-platform development preview releases`.

No commit or push was performed while preparing this update. Your normal GitHub
Desktop account handles your push; Actions uses its own built-in repository token.
You do not need to enter a personal token into the workflow or this chat.

## What gets released

The automatic pre-release contains Windows x64, Linux x64, both Mac architectures,
clean source, checksums and a build manifest. It is a desktop preview, not the
former fuller Windows AI-engine bundle. No model weights, local installed engines,
voices, credentials or FFmpeg binaries are uploaded. Reliable unattended episode
quality is not established by packaging or smoke-test success.

The preview remains separate from stable/RC2 releases. A `v*` tag still creates
candidate artifacts, but does not publish a stable release automatically. Markdown
and specified documentation-only pushes normally skip rebuilding. Use Actions →
Run workflow on `main` when you deliberately need a manual preview rebuild.

See [development preview details](DEVELOPMENT_PREVIEW.md) for triggers, recovery,
required permissions and testing limitations. Source exports remain available via
`python packaging/create_source_archive.py`; `--manifest-only` refreshes the local
source inventory without generating a ZIP when a suitable Python is installed.

`PRIVATE-RECOVERY` is a private local backup, not source to publish. Its metadata
archive does not restore model weights, installed runtimes or missing review audio.
