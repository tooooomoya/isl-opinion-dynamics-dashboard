# Research Direction — Algorithmic Curation & the Attention Economy

> **Standing north-star note.** Captures the current research goal at the level of detail actually
> decided so far. This repo's objective changed on 2026-10-01 — see
> `docs/report/2026-10-01-attention-economy-pivot.md` for the full rationale and literature context.
> The prior CNA2026 moderate-conduit/Type-1-Type-2 frame below this point is **superseded** and kept
> only as historical background on the base model (`docs/wssit2026-TomoyaTakeda.tex`,
> `docs/journal.tex`). Do not treat it as this repo's goal.

## 0. Objective (minimal statement — intentionally not fully specified yet)

What is the effect of algorithmic feed curation (Trend-style global ranking vs. personalized
"For You" ranking) on the **attention economy** of a social platform — i.e. on how concentrated
users' attention becomes, on who creates vs. who merely consumes/supports, and on whether users
settle into a narrow, self-reinforcing focus ("Oshikatsu" / parasocial fandom as the motivating
case, generalizing beyond pop-idol fandom to e.g. political fandom).

## 1. Core reinterpretation of the model (decided)

- **Main variable: opinion → attention.** Replaces the 1-D opinion scalar with a representation of
  *what/whom a user's attention is directed toward* (exact representation — vector over
  topics/creators vs. scalar per-target weights vs. something else — **not yet decided**, see
  `docs/report/2026-10-01-attention-economy-pivot.md` §"open questions").
- **Stubbornness stays, reinterpreted as intensity.** Instead of a fixed per-agent trait, it becomes
  a dynamic variable that builds up endogenously from repeated consumption + reward (habit/addiction-
  like reinforcement), with some chance of exploring away from the current focus. Exact functional
  form **not yet decided**.
- **Agent actions: {create, consume, idle}** (support/boost may be folded into consume or split out —
  **not yet decided**), chosen via a utility/game-theoretic rule rather than fixed per-step behavior.

## 2. Why this is meant to be distinct from existing algo-effect studies

Existing literature (GNN-based and linear-algebra/filter-bubble studies of recommender effects) treats
user preference as given or slowly drifting. The intended novelty here is **endogenous intensity**:
commitment to a focus is *produced* by the history of consumption and reward (not handed to agents as
a parameter), which is closer to economic habit-formation/rational-addiction framing than to standard
opinion-dynamics stubbornness. See the report entry for full discussion, open risks (tautology risk,
conflating taste vs. attention-allocation, stubbornness doing two jobs at once, validation targets).

## 3. Status

Direction agreed in principle (2026-10-01). Model design (state representation, intensity dynamics,
utility/action rule, feed algorithms to compare, validation targets) is **open** — see the report entry
for the list of decisions still needed before implementation starts.
