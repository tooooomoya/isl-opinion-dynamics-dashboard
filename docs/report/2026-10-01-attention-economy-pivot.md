# 2026-10-01 — Objective pivot: attention economy / Oshikatsu

## Decision

Drop the inherited CNA2026 objective (moderate-conduit / Type-1 vs Type-2 polarization,
`docs/research-direction.md` pre-2026-10-01 version) as this repo's goal. New objective: study the
effect of algorithmic feed curation (Trend-style global ranking vs. personalized "For You" ranking)
on the **attention economy** — attention concentration, create-vs-consume/support behavior, and
lock-in to a narrow focus — motivated by the Japanese "Oshikatsu" fandom phenomenon
("self-expression outsourcing": people meet their self-expression need by finding and supporting a
representative instead of creating themselves) and its generalization to political fandom.

Trigger: user's professor noted the current "For You" implementation in this model behaves like a
Trend feed (global popularity) rather than a personalized one — that gap is itself part of the new
object of study, not just a bug to fix.

This supersedes `docs/research-direction.md`'s prior content; see that file's new version for the
current (minimal, partially open) statement of the objective.

## Reinterpretation of model primitives (agreed in principle)

- **Opinion scalar → attention representation.** What a user's attention is directed toward, instead
  of a position on an issue axis.
- **Stubbornness → intensity**, made *endogenous*: it should emerge from repetition of similar
  consumption + reward (habit/reinforcement), not be an assigned per-agent constant. Occasional
  exploration away from current focus.
- **Agent actions → {create, consume, idle}**, chosen by a utility-based / game-theoretic rule.

## Why (literature framing, for reviewer-facing novelty)

Existing algo-effect studies (GNN-based, linear-algebra/filter-bubble) mostly treat user preference as
exogenous or slowly drifting. The candidate novelty is making **intensity/commitment endogenous** —
built up from consumption-reward history, closer to economic habit-formation / rational-addiction
framing (Becker & Murphy 1988) than to standard opinion-dynamics stubbornness (Friedkin-Johnsen).
Related work to position against: strategic-creator/recommender equilibrium models (Ben-Porat &
Tennenholtz; Hron et al. 2022; Jagadeesan et al. 2023), limited-attention/competing-memes models (Weng
et al. 2012; Lorenz-Spreen et al. 2019), empirical diversity-under-personalization studies (Anderson et
al. 2020 Spotify; Waller & Anderson Reddit), parasocial interaction (Horton & Wohl 1956).

## Open risks flagged (not yet resolved)

1. **Tautology risk**: if consumption always raises intensity and intensity always suppresses
   exploration, everyone locks in by construction regardless of the algorithm — need an opposing
   force (satiation, decay, novelty-seeking, supply running out) so "does/when does lock-in happen"
   is an actual result, not a built-in assumption.
2. **Attention vector conflates two things**: slowly-changing *taste* (what a user likes) vs. fast
   *attention allocation* (a limited budget spent across targets, naturally a simplex). Keeping them
   separate lets the model distinguish "taste changed" from "attention got captured."
3. **Stubbornness/intensity doing two jobs**: anchoring (resistance to change) vs. activity level
   (how much one consumes/supports). Candidate resolution: intensity = inverse temperature in a
   softmax choice over content (high = exploit/stubborn, low = explore); activity level kept as a
   separate quantity if needed.
4. **Action set missing "support"**: Oshikatsu is active support (like/repost/promote/pay), which is
   also the channel that feeds reward back to creators and closes the loop. Candidate: {create,
   support, consume, idle} (or fold support into consume — open).
5. **Validation targets lost** with the opinion-polarization metrics (modularity, assortativity).
   Candidates to pick from: participation inequality (1/9/90 rule), heavy-tailed attention-to-creator
   distribution, falling consumption entropy over a user's tenure, shrinking attention half-life over
   time (cf. Lorenz-Spreen 2019).
6. **Scope creep**: endogenous intensity + create/consume game + multiple feed algorithms + political
   application, all at once, would make results impossible to attribute. Plan to build a minimal core
   (intensity + feed condition only) before adding the creation choice, then politics.

## Status / next decisions needed

Not yet decided (tracked for the next working session, see chat log 2026-10-01):
state representation for attention, exact intensity dynamics (reward/decay/exploration functional
form), whether taste and attention-allocation are separate state variables, the action/utility rule,
which feed algorithms to implement and compare (chronological baseline, Trend, For You via real
collaborative filtering), and validation stylized facts to target.
