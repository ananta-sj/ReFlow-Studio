# Reflow licensing discussion — decision pending

The user requested a discussion before choosing a license. No license has been assigned to Reflow's original code, and the existing Python license is preserved.

## The owner's code decision

| Direction | What it allows or requires | Product consideration |
| --- | --- | --- |
| [MIT](https://choosealicense.com/licenses/mit/) | Permissive reuse, modification and commercial distribution with retained copyright/license notices; downstream works can use other terms | Suitable if broad reuse and community adoption matter and you accept other people selling or closing their forks |
| [Apache 2.0](https://choosealicense.com/licenses/apache-2.0/) | Permissive reuse plus an explicit contributor patent grant and requirements for notices and marking modifications | A permissive option with more explicit patent/contribution terms; downstream proprietary products remain possible |
| [GPLv3](https://choosealicense.com/licenses/gpl-3.0/) | Distribution of covered modifications/combined works carries source and same-license obligations under its terms; commercial use is permitted | Consider if distributed improvements should remain available under the same license; compatibility with the actual combined software must be checked |
| Proprietary terms | Terms for the code you own would be prepared around the intended product and distribution rights | Consider if controlling redistribution of your code matters; third-party components retain their own terms and obligations |

Open-source licensing and charging money are separate choices. None of these licenses alone provides a business model or grants rights to someone else's code, model weights, voice recordings or input media. Confirm which portions of the project you own or have a license to redistribute before assigning terms to the whole repository. GitHub's [repository licensing guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository) explains the role of an explicit license.

The useful next discussion is what you want other developers and businesses to be allowed to do with Reflow: reuse it freely, distribute improvements with source, or obtain your permission for proprietary redistribution. There is no license recommendation recorded yet because that product direction is undecided.

## The bundled-component decision

Choosing Reflow's license does not finish the distribution review. The current bundle contains a GPL-enabled FFmpeg build; its precise binary configuration and the absence of bundled notices are captured in the dependency inventory. Prepare the corresponding notices/source/distribution material according to the actual build and [FFmpeg's guidance](https://ffmpeg.org/legal.html).

The vendored Wav2Lip README contains research/personal/non-commercial restrictions. Model publishers can impose conditions separate from the inference library's license. Review each selected model and runtime before making commercial-use or unrestricted-redistribution claims. Downloading weights on demand is not evidence that those conditions no longer apply.

The audited core has 255 installed distribution records, including duplicates. Its generated inventory records declared license metadata and discovered notice-file hashes. Duplicate metadata and overwritten files must be resolved before treating that inventory as the final package manifest. Optional environments, frontend bundled components, engine source trees and downloaded weights need corresponding final inventories. Current inventory status is **not cleared for publication**.

## Work needed after the decision

1. Confirm the license and copyright holder for Reflow's owned code.
2. Keep Python's license in a clearly identified third-party location rather than losing or presenting it as Reflow's own grant.
3. Collect notices and source/distribution requirements for the exact released runtime and binary set.
4. Record model terms, access requirements and any commercial-use restrictions beside the available engine routes.
5. Ensure the README, release notes, package contents and download page describe the same scope and conditions.

See [the release iteration](WINDOWS_RELEASE_ITERATION_2026-10-12.md) and [dependency inventory](validation/2026-10-12-release-dependency-inventory.json). No publication, license replacement or external communication has occurred in this discussion.
