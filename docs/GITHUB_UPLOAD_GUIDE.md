# Which files to upload to GitHub

Use the prepared **source-only folder**, not the working project root:

`release-assets/github-source-upload/ReflowStudio-source/`

Its contents are also in `release-assets/ReflowStudio-source-RC2.zip`. Extract
that ZIP to obtain the same source-only tree. Do not upload the ZIP as the
repository's application code: GitHub needs the extracted files to find the
README and Actions workflow.

## Upload these contents

Upload everything **inside** the source-only folder, including:

- `.github/` — contains `workflows/build.yml`; keep that exact location.
- `.gitignore` and `.gitattributes` — keep the dot-prefixed files.
- `assets/`, `bridge/`, `core/`, `dev/`, `docs/`, `frontend/`, `packaging/`.
- `main.py`, `config.py`, `requirements.txt`, `README.md`, `README.txt` and the
  other root source/launcher/license files included in that folder.
- `SOURCE_MANIFEST.json` — records what the source export contains.

`core/Wav2Lip/models/` is real Python source and belongs in the repository.
It must not be confused with the top-level `models/` folder of downloaded weights.

The export already excludes application EXEs, built ZIPs, installed Python/engine
runtimes, node_modules, built frontend files, downloaded model weights, private
media, personal settings, credentials, logs and Git metadata. Nested vendor
repositories are exported as ordinary source files with their notices; their
private `.git` directories are excluded.

## Recommended: use Git if available in your terminal

The source tree has more than 100 files. GitHub's browser uploader accepts up to
100 files at once, so Git is easier for uploading the complete tree. This guide
does not install GitHub Desktop or any other tool. If `git` is not available in
your terminal, use the browser method below or arrange your Git setup separately.

1. Open PowerShell in the project's `release-assets` folder. Use a **new clone**
   so the existing GitHub history is preserved and the working project is not
   affected:

   ```powershell
   git clone https://github.com/ananta-sj/ReFlow-Studio.git GitHub-upload
   ```

2. In File Explorer, open `github-source-upload/ReflowStudio-source`. Copy all
   its contents into the new `GitHub-upload` folder. Replace matching source
   files when prompted. Keep the new clone's `.git` directory; the clean export
   contains no `.git` directory to replace it.

3. Back in the same PowerShell window, review the files:

   ```powershell
   git -C GitHub-upload status --short
   ```

4. Commit and upload the reviewed source:

   ```powershell
   git -C GitHub-upload add --all
   git -C GitHub-upload diff --cached --stat
   git -C GitHub-upload commit -m "Add updated ReFlow Studio source and native builds"
   git -C GitHub-upload push origin main
   ```

   Git may ask you to sign in. These commands are instructions for you; no
   clone, commit or push was performed by the packaging task.

5. On GitHub, check that `main.py`, `README.md` and
   `.github/workflows/build.yml` are at the repository root paths, rather than
   inside an extra `ReflowStudio-source/` wrapper folder.

If you prefer the browser, upload extracted source files in batches of no more
than 100 files, preserving the same folder structure. Do not omit `.github`.

## Application downloads go in Releases

The corrected application download is:

`dist/ReflowStudio-Windows-Executable-RC2-2026-10-31.zip`

The prepared split-download set is:

`dist/github-windows-download-RC2/`

For a future GitHub Release, attach both `.part` files, the
`Assemble-ReflowStudio.cmd` script, its instructions, manifest and checksums as
release assets. These generated downloads do **not** belong in the source
repository's ordinary file tree. Keep all application companion files in the
download; publishing `ReflowStudio.exe` alone is insufficient.

The updated downloads remain test candidates. Finish the fresh-PC checks and
application/component licensing decisions before treating them as a public
release. Linux/macOS Actions outputs are desktop previews, not validated full
engine bundles. Nothing has been uploaded or published by this task.

References: [GitHub file upload instructions](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository)
and [Release asset limits](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases).
