# Font licensing and provenance

Both families are self-hosted to avoid external font-service calls at runtime
(DESIGN_SYSTEM.md: "Avoid externally blocking font calls"). No font subsetting
was applied — the full glyph sets and variable axes are preserved.

| File | Family | Source | License |
| --- | --- | --- | --- |
| Newsreader-Variable.woff2 | Newsreader (opsz 6–72, wght 200–800) | google/fonts `ofl/newsreader/Newsreader[opsz,wght].ttf` at commit `8b0a1d0f5983` (2026-03-12), downloaded 2026-11-05 | SIL OFL 1.1 ([OFL-Newsreader.txt](OFL-Newsreader.txt)) |
| Newsreader-Italic-Variable.woff2 | Newsreader Italic | same source, `Newsreader-Italic[opsz,wght].ttf` at the same commit | SIL OFL 1.1 ([OFL-Newsreader.txt](OFL-Newsreader.txt)) |
| Inter-Variable.woff2 | Inter (opsz 14–32, wght 100–900) | google/fonts `ofl/inter/Inter[opsz,wght].ttf` at commit `0b58fb370093` (2026-03-03), downloaded 2026-11-05 | SIL OFL 1.1 ([OFL-Inter.txt](OFL-Inter.txt)) |

The committed `.woff2` files are lossless Brotli containers of the downloaded
`.ttf` variable fonts, converted locally with fontTools (brotli) on
2026-11-05; the source TTFs are not committed. SIL OFL 1.1 permits
self-hosting, embedding in applications and redistribution (including the
bundled license files, retained here unchanged). Reserved font names
(Newsreader, Inter) survive the container conversion unmodified.

CSS variables: `--font-serif` (Newsreader — editorial hero/research titles),
`--font-sans` (Inter — app UI), with Georgia/system-ui fallbacks declared in
[tokens.css](../tokens.css).


## Comic Lab fonts — NI-099

Rubik (regular/bold), Golos Text (regular/bold), and IBM Plex Mono (medium) are self-hosted WOFF2 conversions of the Google Fonts files used in the owner-approved Comic Lab guide. Conversion uses FontTools without changing glyph designs. Original SIL Open Font License texts and copyright notices are retained in rubik-OFL.txt, golostext-OFL.txt, and ibmplexmono-OFL.txt.

Official sources: https://github.com/google/fonts/tree/main/ofl/rubik · https://github.com/google/fonts/tree/main/ofl/golostext · https://github.com/google/fonts/tree/main/ofl/ibmplexmono.
