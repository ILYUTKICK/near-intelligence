# Licensing scope and third-party notices

## Original project code

The [MIT License](LICENSE) applies to the original NEAR Intelligence source
code, application, tooling, tests and associated developer documentation.
Copyright (c) 2026 NEAR Intelligence contributors.

This grant does not replace third-party licenses or grant rights to research
datasets, provider outputs, third-party content, artwork or trademarks. Public
repository access is not evidence of permission to redistribute those materials.

## Software dependencies and container images

Third-party packages and base container images retain their own copyright
notices and licenses. Installing them through the committed pnpm/uv lockfiles or
pulling a pinned image does not relicense them under this project's MIT License.
Retain their applicable notices and comply with their licenses when redistributing
packages, compiled applications or images. The project license is not a claim
that every dependency has the same license.

## Bundled fonts

The application includes Inter and Newsreader font files under the SIL Open
Font License, Version 1.1. The full license texts and copyright notices are
retained beside the font files:

| Font family | Copyright notice | Full license |
| --- | --- | --- |
| Inter | Copyright 2020 The Inter Project Authors | [OFL-Inter.txt](apps/web/src/styles/fonts/OFL-Inter.txt) |
| Newsreader | Copyright 2020 The Newsreader Project Authors | [OFL-Newsreader.txt](apps/web/src/styles/fonts/OFL-Newsreader.txt) |

See [font provenance and conversion notes](apps/web/src/styles/fonts/LICENSE-NOTES.md).
These fonts remain under OFL 1.1; the project's MIT License does not supersede it.

## Research data and third-party content

Research uses separately identified provider material and saved observations.
The repository does not grant a dataset redistribution license or rights to
third-party website captures, source material or provider outputs. Attribution,
public accessibility and a recorded input hash do not by themselves establish
redistribution rights. Retain the provider's original terms and source labels;
unresolved rights remain unresolved.

The raw historical archive and production database are not included in a source
clone. A permitted data handoff must be reviewed separately from the code license.
See [source verification and rights status](docs/SOURCE_VERIFICATION.md) and
[data provisioning](docs/SELF_HOSTING.md#research-data-and-models).

## Artwork, mockups and marks

Illustrations, design concepts, screenshots and legacy mockups are not relicensed
under the project's MIT License. No general redistribution permission for legacy
mockups or external design references is asserted here. Recorded generation or
capture provenance describes how an asset was made; it is not a replacement for
any rights review needed for a particular reuse.

Available provenance includes the
[Overview artwork record](docs/verification/ni-086/ASSETS.md),
[generated concept notes](product-plan/near-intelligence-v1/README.md) and
[synthetic application screenshot record](docs/verification/ni-075/README.md).

Project, provider and other product names, logos and trademarks retain their
respective ownership. The MIT License does not grant trademark rights or imply
endorsement by NEAR, providers or other third parties.
