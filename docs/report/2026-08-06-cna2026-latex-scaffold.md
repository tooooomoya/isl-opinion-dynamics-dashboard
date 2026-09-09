# 2026-08-06 — Complex Networks 2026 (CNA) LaTeX scaffold created

## Decision
Created `../LaTex-CNA2026/` (sibling to this repo) as the LaTeX scaffold for the
Complex Networks 2026 submission, reusing last year's `../LaTex-CNA/` template
infrastructure (`svproc.cls`, `spmpsci.bst`, `.latexmkrc`, `.vscode/`).

## Verification
Downloaded the current official template
(`https://complexnetworks.org/wp-content/uploads/2023/08/CNALatexTemplate.zip`,
unchanged since 2023) and diffed it against last year's `LaTex-CNA/`:
- `svproc.cls` — byte-identical.
- `spmpsci.bst` — identical apart from whitespace/indentation (functionally
  the same).

So reusing last year's template files for this year's submission is confirmed
safe, not just an assumption.

## Venue facts (from https://complexnetworks.org/ and /submission/, checked 2026-08-06)
- Submission deadline: **2026-09-02, 23:59 AoE**.
- Acceptance notification: 2026-10-01. Camera ready: 2026-10-08. Registration: 2026-10-15.
- Full paper: 8–10 pages recommended, **12 pages max including bibliography**.
- Extended abstract track (separate template): 2–3 pages recommended, 4 max.
- Format: Springer proceedings (svproc), published in Springer's *Studies in
  Computational Intelligence* series.
- Submission system: Microsoft CMT, `https://cmt3.research.microsoft.com/COMPLEXNETWORKS2026`.
  Requires abstract, 1 primary + up to 4 secondary subject areas, ≥3 keywords in CMT metadata.

## Scope of what was created (scaffold only, per user instruction)
- `main.tex`: package preamble carried over from last year (incl. `\add`/`\erase`
  track-change macros), section skeleton (Introduction / Related Work / Model /
  Experimental Design / Results / Discussion / Conclusion), all content as `TODO`.
- `refs.bib`: intentionally empty — bibliography curation deferred. Last year's
  `../LaTex-CNA/refs.bib` is a reuse candidate (opinion dynamics / bounded
  confidence / echo chamber literature likely overlaps).
- `figures/`, `out/`: empty directories.
- No content was ported from `docs/wssit2026-TomoyaTakeda.tex` (this year's base
  manuscript, per `docs/research-direction.md`) or from last year's CNA paper —
  writing the actual paper content is separate future work.

## Why
North star (`docs/research-direction.md`) names Complex Networks 2026 as the
submission target, with `docs/wssit2026-TomoyaTakeda.tex` as the base
manuscript. Confirmed build: `pdflatex` compiles `main.tex` cleanly to a 1-page
PDF with the current empty content.
