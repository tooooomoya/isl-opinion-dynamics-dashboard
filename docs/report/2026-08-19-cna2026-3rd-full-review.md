# 2026-08-19 — Full critical review of `tex/CNA2026/CNA2026-3rd.tex`

Scope: whole-paper review of the completed 3rd draft against the Complex Networks & Their
Applications 2026 (CNA2026) 12-page constraint. Covers (1) overall assessment, (2) submission
blockers, (3) scientific/logical soundness, (4) mathematical rigor, (5) network-science venue fit,
(6) English/terminology/operational-definition line edits, (7) page-budget plan.

Every claim below that concerns "what the code actually does" was checked against `src/` and against
the surviving run output in `results/2026-08-14_lmp_feedmech_structural_9b/` (15 seeds/cell), not
inferred from prior reports.

---

## 0. Overall assessment

**The paper has a real, non-obvious, mechanistically-explained result** — a sign reversal in the
downstream effect of moderate-hub vocality on the extreme camp, with a crossing point that moves
with the unfollow propensity, plus a two-gate (exposure/expression) explanation that is consistent
with the underlying feed-composition data. That is a publishable core for this venue.

**The manuscript as it stands, however, is not submittable**, for one dominant reason: *the
Experimental Design section describes a different experiment from the one the figures report*
(2x3 grid in text, 4x4 grid in both figures), and several other statements about the model do not
match the code that produced the results. These are correctness/reproducibility defects, not style.
They are all cheap to fix.

Ranking of what actually threatens acceptance, in order:

1. Text/figure/code mismatches (§2) — a reviewer who opens the linked GitHub repo will find them.
2. Non-stationarity at t=40,000 (§3.1) — "converged/steady-state" is currently asserted and is false
   in the data; the measured effect is still growing, and growing at a `p_u`-dependent rate, which
   is exactly the contrast the headline claim rests on.
3. Complete absence of statistical inference (§3.2) — roughly half the extreme-camp cells are not
   distinguishable from zero at n=15, including the cells that locate the sign crossing.
4. Venue fit (§5) — no structural/network-level outcome is measured anywhere in a paper submitted to
   a network-science conference, and the brokerage framing (Granovetter/Burt/Freeman) is never
   operationalized.

---

## 1. Submission blockers (must fix, mechanical)

**B1. §4 describes the wrong factorial design.**
Text: `κ ∈ {0.1, 0.15, 0.2}` × `P_u ∈ {0.05, 0.15}` = "six parameter cells", "6×2 = 12 conditions".
Both figures, and `scripts/lmp_feedmech_grid4x4.py`, are `P_u ∈ {0.05, 0.08, 0.11, 0.15}` ×
`κ ∈ {0.10, 0.13, 0.17, 0.20}` = 16 cells, 32 conditions, 480 runs. The Discussion already cites the
correct `n=480` "sixteen cells", so the paper contradicts itself internally.

**B2. The whole body is typeset in colour.** `\Blue` at l.111 runs until `\Black` at l.547, and the
abstract/Related-Work paragraphs are `\Dgreen`. Remove the track-change colouring (and the stale
`\ignore{...}` abstract at l.105) before submission.

**B3. 13 pages, limit is 12.** The overflow is 6 reference entries onto p.13; ~20 lines of body cuts
suffice (see §6).

**B4. Hub opinions are *not* held fixed.** §3.4 states the hub's opinion is "held fixed thereafter by
exempting it from Eq. (1)". In the code, `pin_opinion_ids`
(`OpinionDynamics.java:222-227`) performs a **one-time t=0 reset** of `intrinsicOpinion` and
`opinion`, then calls `setTarget()`, which only excludes the agent from *metrics*
(`Agent.getTarget()` is read at `OpinionDynamics.java:319/391` for reporting). Hubs keep the
population stubbornness `μ=0.82` and keep running Eq. (1). Measured at t=40,000 over the 15 seeds of
cell `p_u=0.05, κ=0.1` (control):

| pinned target | mean drift | max abs drift | share drifted >0.01 |
|---|---|---|---|
| −1.0 | +0.004 | 0.117 | 8.7% |
| −0.4 | +0.011 | 0.074 | 24.0% |
|  0.0 | −0.001 | 0.054 | 9.7% |
| +0.4 | −0.010 | 0.108 | 50.0% |
| +1.0 | −0.003 | 0.108 | 7.3% |

The magnitudes are small, so no result is invalidated — but the description is wrong and must be
corrected to: "pinned once at t=0; thereafter hubs remain subject to Eq. (1), and their high
stubbornness (μ=0.82) keeps them within ≈0.12 of the assigned position."

**B5. Silencing does not hold the hub's follow relationships constant.** §3.4/§4 claim "its follow
relationships evolve identically" and therefore "the isolated difference between the two conditions
is whether the moderate hubs actually post and repost". A silenced hub emits no posts, so no agent
can encounter it in a feed, so no agent can *newly follow* it (`Agent.follow()` builds candidates
strictly from feed posts) and no agent can content-block it. Its in-edges therefore diverge
immediately and by construction. `ExperimentConfig.java:458-464` documents the converse risk
explicitly ("Silence does not guarantee the pre-silence follower base survives intact... must be
checked empirically"). Correct framing: the manipulation is the hub's *vocal activity*; all
structural consequences (audience, tie churn, ε) are **downstream effects of the treatment**, not
quantities held fixed. The estimand is a total effect, not a ceteris-paribus effect. This actually
*strengthens* the paper's "upstream regulator" story — but only if stated correctly.

**B6. Results text contradicts Fig. 1's caption and the analysis script.**
Text: "difference in per-step per-capita posting counts... averaged over steps [39000, 40000]".
Caption and `lmp_feedmech_paper_figures.py:64-96`: **paired Cohen's d** (`mean(diff)/sd(diff)`, i.e.
d_z) over the trailing window `WINDOW=2000`, i.e. steps **(38000, 40000]**. Fix both the statistic
and the window. Values like −3.87 are obviously not posting counts.

**B7. Fig. 2's denominator is not stated.** The share is normalised by each extreme agent's
*realised* feed size, which converges to ~2–5 posts, **not** by the capacity `S_fd = 15`. Without
that sentence a reader will divide by 15 and conclude the influx is negligible. (This was fixed in
`2nd.tex`'s caption on 2026-08-18 but the wording is missing from `3rd.tex`.) Measured realised feed
sizes at t=40,000 (mean posts per feed read):

| reader camp | control (p_u=.05, κ=.1) | M-silent |
|---|---|---|
| extreme (bins 0/4) | 1.90 / 2.15 | 2.24 / 2.29 |
| near-extreme (1/3) | 6.16 / 5.42 | 5.48 / 4.99 |
| moderate (2) | 9.48 | **1.03** |

**B8. Betts et al. is mis-cited.** §2 says "a neutral influencer's effect on polarization inverts
depending on **its own** tolerance for disagreeing views". The cited abstract says it varies with
"the tolerance for opposing beliefs **in the society**" (and with the influencer's reach). This
inverts the locus of the moderator, and it matters, because *society-level tolerance* is precisely
what this paper's own `κ`/`P_u` sweep is. Fix the sentence — and then use the corrected version to
position the contribution (§3.7). Also verify the year: the entry says 2023 but `series = {WSC '22}`.

---

## 2. What was verified as correct (so it can be defended)

- Eq. (1) matches `Agent.updateMyself()` (FJ blend of intrinsic opinion with the mean of *in-tolerance*
  feed posts only; strict `<`; opinion frozen when no post is in tolerance).
- Eq. (2)/(3) match the graded bc relaxation (`Agent.java:411-418`), including the δ≫γ asymmetry.
- Eq. (4) matches the graded post-probability relaxation; `Const.POST_COST = 0.0`, so the extra
  post-cost term in `makePost()` is inert.
- Follow/eviction rule matches (`evict_beta = -1` ⇒ legacy argmax-disagreement eviction, exactly as
  described). Unfollow/block matches, including the "first out-of-tolerance followed author, else
  block one random out-of-tolerance non-followed author" ordering.
- The feed *is* purely reverse-chronological in these runs: `alpha=0` in `BASE_TOKENS` disables the
  For-You stream entirely (`algoSlots = floor(0·15) = 0`). The model's algorithmic-feed machinery
  (`feedAlgoShare=0.7, hop=4, exp decay λ=0.11, τ=30`) is off. **This is worth one explicit sentence
  in §3.3** — it is a deliberate scoping choice, and stating it pre-empts "why is there no
  recommender?".
- Reposts are content- and attribution-preserving (`relay_enabled=false` ⇒ verbatim opinion, original
  author id). This is *load-bearing* for Fig. 2 — "near-extreme-authored" counts relayed content by
  its original author — and the sentence stating it is currently commented out (l.433-436). Restore it.
- The Discussion's three feed-share numbers are accurate: moderate-hub content is 73–80% of a moderate
  agent's feed, 25–28% (p_u=.05) / 44–47% (p_u=.15) of a near-extreme agent's, and 0.3–3.5% of an
  extreme agent's. The "≈50% → ≈30%" comfort drop for the moderate camp is right **at κ=0.1**
  (0.527→0.295); at κ=0.2 it is 0.900→0.578. Scope the claim to κ.
- The sign story matches the per-agent comfort rates in every checked cell: extreme-camp `cRateMean`
  falls under M-silent at κ=0.1 (0.325→0.322, 0.368→0.358) and rises at κ=0.2 (0.665→0.698,
  0.698→0.718), matching the negative/positive d in Fig. 1.

---

## 3. Scientific and logical issues

### 3.1 The system is not converged at t = 40,000 — and the effect is still growing

Fig. 2's caption says "Converged, steady-state share"; the Discussion says "converged
ε_i(t)". The data say otherwise. Cell `p_u=0.15, κ=0.1`, extreme camp, 8 seeds, successive windows:

| window | control cRate(E) | M-silent cRate(E) | gap |
|---|---|---|---|
| 10–20k | 0.3268 | 0.3173 | 0.0095 |
| 20–30k | 0.3434 | 0.3288 | 0.0146 |
| 30–35k | 0.3543 | 0.3359 | 0.0184 |
| 35–40k | 0.3616 | 0.3412 | 0.0204 |

Both arms are still rising monotonically, and **the arm gap is still widening** at the point of
measurement. `bcExtremityCorrelation` likewise drifts throughout (control −0.477 → −0.502 → −0.514;
M-silent +0.078 → +0.090 → +0.096). Addendum 3 of the 2026-08-15 report already found the same
pattern for tie counts and noted it is `p_u`-dependent ("transient, then locked in" at p_u=0.05;
"transient, then amplified" at p_u=0.15).

Why this is the most serious scientific issue: the headline claim is that **`P_u` shifts the κ
crossing point**. If the effect size at p_u=0.15 is still growing at t=40,000 while p_u=0.05's has
plateaued, then part of the measured crossing shift is a *transient-timing* difference, not an
equilibrium property. The paper currently asserts equilibrium language that the data do not support.

This is also mechanistically predictable, not a surprise (see §4.4): γ_ε = 10⁻⁴ per access with
P_a = 0.1 gives an ε-recovery half-life of ≈69,000 steps — longer than the entire 40,000-step run —
and blocks are never released (`blockedUserList` is set-only). The model contains two near-irreversible
ratchets, so a 40,000-step horizon is a transient by construction.

**Minimum fix (cheap, honest):** delete "converged"/"steady-state"; say "measured over the final
2,000 steps of a 40,000-step run, at which point the contrast is still growing in the high-`P_u`
cells". **Better fix:** one extra panel, or three numbers per row, showing the outcome measured at
t=20k / 30k / 40k, demonstrating the sign structure is already established and only the magnitude
grows. **Best fix (if time permits):** rerun one κ-column at 80,000 steps.

### 3.2 No statistical inference anywhere

With n=15 paired seeds, the two-sided 5% threshold on paired d_z is 2.145/√15 = **0.554**. Reading
Fig. 1's extreme panel, the following cells are *not* distinguishable from zero: (κ=.13, p_u=.05)
−0.25; (.17,.08) +0.11; (.17,.11) +0.06; (.20,.11) +0.19; (.13,.15) −0.40; (.17,.15) −0.16;
(.20,.15) +0.01. That is 7 of 16 cells — **and they are exactly the cells that locate the crossing**.

The claim is still defensible, but it has to be made at the level of the *row trend*, not the cell:
- In d units the crossing is bracketed between κ=0.13 and κ=0.17 for p_u = 0.05, 0.08 and 0.11, and
  between 0.17 and 0.20 for p_u=0.15 — so "the crossing shifts with `P_u`" is really a 2-level
  contrast at this resolution.
- In *raw rate* units the interpolated crossing is monotone across all four rows
  (0.141, 0.160, 0.167, 0.198 — Addendum 6, F1). **Report these four numbers.** They are the single
  strongest quantitative statement available and they are currently only in the internal log.

Concrete recommendations: (a) overlay the zero contour on the extreme panel of Fig. 1; (b) add the
interpolated κ* per row as a 4-number inset or table line; (c) state the n=15 significance threshold
once, and mark non-significant cells (e.g. hollow annotation); (d) soften "This confirms that `P_u`
governs where this regime shift occurs" to "is consistent with".

### 3.3 The Kendall's τ is over-pooled

"τ=0.30, p<10⁻¹⁷, n=480 pooled over all sixteen cells and seeds" pools 15 seeds × 16 cells × 2 arms.
Those 480 observations are not independent (seeds are shared across cells; arms are paired within
seed), so the p-value is badly inflated; and `P_u` takes only 4 distinct values, so τ's tie
correction matters. Either report the within-stratum τ range you already have (0.29–0.38) as the
headline, or fit a mixed model with a seed random effect. Also, "a monotonic trend across every cell"
overstates Addendum 6/F2, which found 15 of 16 column-sequences monotone with one noise-scale
reversal. Say "15 of 16".

### 3.4 The direct channel is dismissed qualitatively, and a third channel is unaccounted for

§6 argues the extreme camp's effect "cannot be explained by either of the two direct mechanisms
above, because a moderate hub's own content comes to occupy no more than a few percent of an extreme
agent's feed". Since moderate content is essentially never comfortable for an extreme agent, removing
a share s of uniformly-uncomfortable content mechanically raises the comfort fraction by
≈ c·s/(1−s). At (p_u=.05, κ=.2), s ≈ 0.7–1.0% and c ≈ 0.67, giving ≈ +0.7pp against an observed
+3.3pp — i.e. the "negligible" direct channel is worth roughly a fifth of the effect. At
(p_u=.15, κ=.2), s ≈ 2.6–2.8% predicts ≈ +1.9pp while the observed change is −1.3pp. **Do the
one-line arithmetic in the paper rather than waving it away**; the argument survives, but only if the
direct term is netted out explicitly.

Moreover, the treatment does not only inject near-extreme content. Author-class composition of
extreme readers' feeds (counts per feed read, bins 0 and 4 pooled, t=40k):

| cell | arm | own-camp (a0+a4) | near-extreme (a1+a3) | moderate (a2) | total |
|---|---|---|---|---|---|
| p_u=.05, κ=.2 | control | 4.283 | 0.467 | 0.033 | 4.785 |
| | M-silent | 4.522 | 0.780 | 0.003 | 5.306 |
| p_u=.15, κ=.1 | control | 3.969 | 0.120 | 0.121 | 4.210 |
| | M-silent | 4.329 | 0.988 | 0.005 | 5.322 |

Silencing the moderate hubs raises **own-camp** volume by 6–9% as well, and own-camp content is
≈100% comfortable. The paper's two-layer account attributes the whole comfort shift to near-extreme
influx; a proper per-agent decomposition Δc = Σ_a Δ(share_a)·q_a (q_a = class-a comfort probability)
would show how much each author class contributes. (Caveat: the table above is a ratio of means;
the model-relevant quantity is the per-agent mean `cRateMean_i`, so run the decomposition per agent.)

### 3.5 The "openness layer" conflates the modulator with the gate

§6 says the openness mechanism "is governed by `P_u`". But `P_u` is exogenous and constant within a
cell; what actually differs *between arms* (which is what Fig. 2 shows) is the endogenous ε of
extreme agents, which widens when moderate hubs are silenced because their uncomfortable content is
no longer diluting the in-tolerance fraction that drives Eq. (2). The paper explains `P_u → ε` and
then jumps to the arm contrast without stating the arm→ε link, even though the 2026-08-15 report
quantified it (bc gap +0.0137 at p_u=.05, +0.0369 at p_u=.15, i.e. ~2.6× larger). State the layer as:
*ε is an endogenous exposure gate driven by two things — the exogenous pruning rate `P_u` and the
treatment itself — and `P_u` sets the gain of that feedback loop.*

### 3.6 Calibration claims vs. what the calibration actually achieved

§4: "Most of the parameter values... were fixed by a joint parameter sweep against several empirical
targets... thereby enable the model to reproduce realistic polarized posting dynamics" and "The two
parameters swept as experimental factors below, `P_u` and κ, are excluded from this calibration".

Both halves need correction:
- κ **was** a calibrated dimension. `ExperimentConfig.java:310-313` records that the search pinned it
  at its box's upper edge, κ ≈ 0.45–0.5, repeatedly and "consistent, not a fluke". The paper sweeps
  κ ∈ [0.10, 0.20] — entirely below the empirically best-fitting value — and justifies the 0.2 cap by
  the modelling constraint κ ≤ ε_floor. That is a defensible modelling choice, but it should be stated
  as one, not as "excluded from calibration". As written, a reviewer who reads the repo finds that the
  regime the paper demonstrates is not the regime the calibration preferred.
- `p_u` was likewise fixed during calibration (pinned at the box edge, 0.1), which happens to sit
  inside the swept range — fine, but again not "excluded".
- The adopted v15 point did **not** clear its targets: SF1 = 1.148 ± 0.130 vs target [1.19, 1.26];
  Q_sign_repost = 0.417 vs 0.48. Either add a two-line "target vs achieved" statement, or soften
  "reproduce realistic polarized posting dynamics" to "approximately matches" with the residuals named.
  (Note also the standing caveat that Conover et al.'s modularity is activity-filter-inflated and
  therefore not directly comparable to an unfiltered simulated Q.)

### 3.7 Positioning against Betts et al. is never made explicit

Once B8 is fixed, Betts et al. becomes *very* close prior work: a neutral influencer whose
polarization effect inverts with society-level tolerance. The paper needs one explicit
differentiation sentence in §1 or §2. The honest and defensible deltas are: (i) the outcome is
**expressed** behaviour (posting), not latent opinion; (ii) the network is **adaptive and
heavy-tailed**, so exposure is endogenous rather than fixed; (iii) the reversal is located in a
**downstream, non-adjacent** population the hub barely reaches directly, and is explained by a
two-gate mechanism rather than observed as a parameter dependence. Say this.

---

## 4. Mathematical rigor

**M1. Eq. (1) has the same time index on both sides.** `O_i(t) = μ O_i(0) + (1−μ)·(mean over posts
with |O(p_j) − O_i(t)| < ε_i(t))` is not well-formed as a difference equation. Write the LHS as
O_i(t+1) (or define an explicit in-place update at access). Same issue in spirit for `p_j`, which
indexes a *post* by an agent subscript: use `p ∈ F_i(t)` with opinion `O(p)`, since one author can
contribute several posts.

**M2. Eq. (3) contains two stray commas** — `\delta_{\epsilon},\big(...\big)` renders as "δ, (…)"
where multiplication is meant. Use `\,` or nothing.

**M3. Time index inconsistency.** §3.2 states every rule fires "once per access rather than once per
step", but Eqs. (2)–(4) are written with `t+1`, and `t` was defined as the discrete simulation step.
Introduce a per-agent access counter (e.g. `τ_i`) or say explicitly that `t+1` denotes the agent's
next access.

**M4. Two irreversibility scales are unstated and they set the horizon.** γ_ε = 10⁻⁴ per access ⇒
recovery half-life ≈ 6,931 accesses ≈ 69,300 steps > run length; δ_ε = 0.5 ⇒ decline half-life ≈ 1
access. And `block()` never clears. The paper presents Eq. (3) as a symmetric-in-form relaxation with
"a distinct, stable equilibrium"; with these constants the upward branch is effectively frozen on the
simulated horizon. State the two timescales in Table 2 terms (e.g. "≈1 access vs ≈7·10³ accesses")
and connect them to §3.1's non-stationarity.

**M5. The comfort fraction is computed over a very small realised feed.** `c_i(t)` is measured over
2–5 posts for extreme agents (Table in B7). With 2 posts, c_i ∈ {0, ½, 1}: the "graded, distinct
stable equilibrium vocality" argument holds only for the *expected* target; the realised target is a
3-level random variable smoothed by η=0.1 (time constant 10 accesses). Also note that Eq. (4) depends
on the comfortable **fraction** and not on volume — an agent seeing 1 comfortable post reaches the
same equilibrium vocality as one seeing 10. Given that the treatment changes feed *volume* by up to
9× (moderate camp: 9.48 → 1.03), this volume-insensitivity is a substantive modelling assumption
that deserves one explicit sentence and a place in the limitations.

**M6. The crossing condition can be derived, not just described.** The paper's verbal argument is
already an inequality. For an extreme agent at opinion `O_E` with gate ε, the admitted near-extreme
band is `(O_E − ε, 0.6)` (for O_E > 0), so widening ε extends admission *moderate-ward*, exactly as
the text says; and the admitted content is comfortable iff it lies in `(O_E − κ, O_E + κ)`. The
comfort fraction moves up or down according to whether the arriving content's comfort probability
`q(κ, ε)` exceeds the incumbent comfort fraction `c_E` — i.e. the sign flips at `q(κ*, ε) = c_E`.
Writing those two lines converts the Discussion from a description into a **prediction** that the
measured κ* per row can be checked against, and it explains the κ*–`P_u` coupling (larger ε lowers q
at fixed κ, so κ* must rise). This is the single highest-value addition available and costs ~8 lines.

**M7. Label the effect size correctly.** `mean(diff)/sd(diff)` is Cohen's **d_z** (paired), not
Cohen's d; d_z is not comparable to between-group d and is inflated by the pairing. Say "paired d_z"
and give at least one raw-units number so readers can judge practical magnitude.

**M8. State the per-capita denominator.** Camp membership is endogenous and time-varying; the scripts
divide by the *time-matched windowed* camp population (`pop_counts_nonhub_windowed`), not by an
end-of-run snapshot. Say so, and report that camp sizes do not differ materially between arms
(otherwise the rate difference is partly compositional).

---

## 5. Network-science evaluation (venue fit)

**N1. The generator is not Holme–Kim as cited.** `m=15, p_t=0.05` are Holme–Kim's parameters, but
`A_0 = 4` is an **initial-attractiveness** term (Dorogovtsev–Mendes–Samukhin), and it is what produces
the quoted γ = 2 + A₀/m = 2.267. Cite the initial-attractiveness source alongside Holme–Kim, define
A₀ and p_t in one clause each, and say how directedness is imposed (each arriving node emits m=15
follow edges ⇒ out-degree fixed, in-degree heavy-tailed). Also disambiguate "mean degree ⟨k⟩=15"
(mean out-degree = mean in-degree = 15; 15,000 edges at t=0).

**N2. γ is analytic, not measured, and the *converged* network is never characterised.** The footnote
reports t=0 statistics only. By t=20,000 the graph has lost ~37% of its edges (15,000 → ~9,430). For
a network venue, the converged graph is the object of interest. Report at least: edge count,
in-degree distribution/exponent, and one polarization-structure measure (sign assortativity, or the
sign modularity `Q_sign_repost` already in the metrics stream) per `P_u` level.

**N3. No structural outcome is measured anywhere.** This is the biggest venue-fit gap. The entire
results section is behavioural (posting rates, feed shares). The "openness layer" is asserted through
an agent-level parameter (ε) rather than a network quantity, even though the natural network
observable — the number/share of near-extreme→extreme follow edges, or the `bc_inclusion` gate metric
already computed — exists in the run output. **Adding one panel showing NE→E tie structure across the
grid would do more for acceptance than any other single change.**

**N4. The brokerage framing is never operationalized.** §2 sets up weak ties, structural holes and
betweenness centrality; betweenness then appears once, in a footnote, as a t=0 descriptive statistic.
Meanwhile the internal 2026-08-18 check found the hub pool's betweenness percentile *collapses to 0*
for a subset of hubs by t=20,000 while in-degree stays high — a genuinely interesting fact that would
justify the framing. Either use it (one sentence: "the pinned hubs remain high-in-degree but lose
shortest-path mediation as the graph rewires, which is precisely why their influence must be read as
upstream regulation rather than transmission") or cut the betweenness definition to save space.

**N5. Are the hubs still hubs at t=40,000?** An obvious reviewer question, already answered in the
internal log (in-degree rank percentile mean 96.9 → 93.4; minimum 94 → 50). One sentence.

**N6. Single topology, single N, single hub-pool size.** All conclusions rest on one generator at one
parameter point with N=1000 and N_hub=60 (6% of the population pinned; 2% moderate hubs). The
codebase already has BA / WS / DCSBM / LFR generators. Even a one-cell replication on a second
generator, reported in two sentences, would substantially blunt the "is this an artifact of
Holme–Kim?" objection.

**N7. "Two-layer homophily" is the wrong name for layer 2.** Layer 1 (ε-gated tie retention) is
homophilous rewiring in the standard sense. Layer 2 (κ-gated expression) is not homophily at all —
it is a perceived-climate/expression threshold, i.e. spiral-of-silence. Calling it "perceptual
homophily" will draw fire at a network venue. Recommend renaming the layers consistently everywhere
as an **exposure gate** and an **expression gate**, and retitling accordingly (the title's "homophily"
is the term the Discussion never actually uses).

---

## 6. Terminology, operational definitions and English

### 6.1 Terminological inconsistency (fix globally — currently four naming schemes)

| location | naming |
|---|---|
| title | "two-layer homophily" |
| abstract | "openness" / "comfort" |
| §1 | "structural homophily" / "perceptual homophily" |
| §6, §7 | "openness layer" / "comfort layer" |

Pick one pair (recommended: **exposure gate** / **expression gate**, or keep openness/comfort) and use
it in the title, abstract, introduction, discussion and conclusion.

### 6.2 "Mediate" is used to mean "suppress"

§5: "moderate hubs facilitate the extreme camp's posting... and **mediate** it in the opposite
environment"; also "mediator". In this literature "mediation" means transmission through an
intermediate variable — which is exactly what the paper's *own* mechanism is (near-extreme agents
mediate the hub's effect on extremes). Using "mediate" for "suppress" is actively confusing here. The
2026-08-18 pass already agreed on **facilitating / suppressing regime**; §5 was missed.

### 6.3 Undefined-on-first-use terms

- **"vocality"** (§1, l.143) — define at first use: "vocality (an agent's propensity to post)".
- **"conduit"** (§6 final line) — never defined; either define or say "direct transmitter".
- **"same-signed"** (Fig. 2 caption) — define: near-extreme-authored posts whose opinion has the same
  sign as the focal extreme agent's.
- **"regime shift"** (abstract) — used before the two regimes are named.
- **camps pool both signs** — state explicitly that near-extreme and extreme each pool the ± bins.
- **blocking's effect** — the paper says agents block, but never says what a block *does*
  (`AdminOptim.java:410` filters blocked authors' posts out of the feed, permanently and
  irreversibly). This is load-bearing for the openness layer and must be defined.

### 6.4 Line-level corrections

| line | current | fix |
|---|---|---|
| 105 | stale `\ignore{...}` abstract | delete |
| 111/547 | `\Blue` … `\Black` | delete all colour macros |
| 131 | "emerge by the sharing activity" | "emerge from" |
| 226 | "The resarch on" | "Research on" |
| 307 | "bounded-confidence threshold" (lowercase in table) | capitalise consistently |
| 494 | `$P_r^{\text{repost}}$` | `$P_r^{\text{out}}$` |
| 496 | `$\maxfollower$ = 43.9` | 43 (the code casts to int / compares ≥43.86) — report an integer |
| 558 | "mimicing" | "mimicking" |
| 570 | "highliging" | "highlighting" |
| 571 | "thereby enable the model" | "thereby enabling the model" |
| 616 | "each 5 camp" | "each of the three camps" |
| 650 | "Steadily, the moderate camp boosts" | "Consistently, …" |
| 656 | "does not show a linear result" | "is not monotone in κ" |
| 658 | "it crosses the sign of its effect" | "its effect changes sign" |
| 711 | "alignes" | "aligns" |
| 718 | "thereby silencing them drives" | comma splice — split the sentence |
| 743 | "openness determines what expose to an extreme agent" | "what an extreme agent is exposed to" |
| 747 | "operates through ε rather than around itself" | unclear — rewrite |
| 752 | "is not processed unifromly" | "does not apply uniformly" |
| 773 | "agents are more likely to expose to out-of-tolerance content" | "to be exposed to" |
| 855 | "the model’s" (U+2019) | ASCII apostrophe |

### 6.5 Bibliography hygiene

- `clifford1973` renders as "CLIFFORD, P., SUDBURY, A." (all-caps in the .bib) — fix casing.
- `deffuant2000` author field is mojibake ("Gﾃｩrard Weisbuch") — repair the é.
- `cha2010` has no venue/pages; `conover2011` has no venue (ICWSM); `hegselmann2002` has no
  pages/number — all render as bare "(year)" entries.
- `helfm2023` is cited as an arXiv preprint; use the published version if one exists.
- `betts2023` year vs `WSC '22` — reconcile.
- **Missing citation:** Friedkin & Johnsen for the stubbornness/intrinsic-opinion anchor in Eq. (1) —
  the equation is an FJ model with a bounded-confidence filter and should say so.
- **Missing citation:** initial attractiveness (DMS) for A₀ (see N1).
- §3.2's expression-threshold rule (Eq. 4) carries **no citation**, although §2 already sets up
  spiral-of-silence; cite Noelle-Neumann/Krassa at the rule itself.
- §1's "The role and effect of these hubs have been well studied, particularly from the perspective of
  information diffusion" has no citation.

---

## 7. Page-budget plan (13 → 12, with room to add)

Cuts (~35 lines, ≈0.9 page):
- §3.1 adjacency-matrix sentence (A is never used again): −3 lines.
- §2 betweenness-definition sentence (unless N4 is adopted): −3 lines.
- §5's "Equivalently, reversing the contrast…" restatement: compress to one sentence, −6 lines.
- §6's final paragraph re-states the mechanism a third time in complementary form: compress, −10 lines.
- §7 duplicates the abstract almost sentence-for-sentence: compress, −8 lines.
- Table 1 (3 rows) folds into Table 2: −5 lines.

Additions worth the recovered space, in priority order:
1. The four interpolated crossing points κ* (§3.2) — 2 lines, biggest evidentiary gain.
2. The q(κ,ε) ≷ c_E threshold derivation (§4/M6) — ~8 lines, turns description into prediction.
3. Non-stationarity honesty + one horizon check (§3.1) — 3 lines.
4. The arm→ε link with its two numbers (§3.5) — 3 lines.
5. One structural/network outcome panel or paragraph (§5/N3) — the venue-fit fix.
6. A real limitations sentence-set: single topology, single N, κ below its calibrated value, 1-D
   opinion, homogeneous κ and μ, transient horizon.

---

## 8. Priority-ordered action list

**Before anything else (correctness):** B1, B4, B5, B6, B7, B8.
**Then (defensibility):** §3.1 non-stationarity language, §3.2 significance + κ* numbers, §3.3 τ
re-analysis, §3.6 calibration honesty, §6.2 mediate→suppress.
**Then (venue fit / upside):** N3 structural panel, M6 derivation, §3.7 Betts positioning, N1/N2
generator description, N6 second-generator robustness if time allows.
**Last (mechanical):** B2 colour, B3 page count, §6.4 line edits, §6.5 bibliography.

---

## 9. ADDENDUM (same day) — the horizon check, run after the review above

Measured directly on the surviving 9b/4x4 output: the **headline outcome itself**
(extreme-camp per-capita posting rate, M-silent − control, per-seed paired, n=15) at four windows.

| cell | 10–15k | 20–25k | 30–35k | 38–40k |
|---|---|---|---|---|
| `p_u=0.05, κ=0.1` | **+0.01644** (d_z +0.69) | −0.00395 (−0.28) | −0.01141 (−0.83) | −0.01409 (−0.79) |
| `p_u=0.15, κ=0.1` | −0.01062 (−0.50) | −0.01992 (−0.83) | −0.02819 (−1.15) | −0.02957 (−1.13) |

Two things follow, and they upgrade §3.1 from "language problem" to "substantive claim about the
result":

1. **At `p_u=0.05, κ=0.1` the effect changes sign during the run.** At steps 10–15k the contrast is
   *positive* (d_z = +0.69, nominally significant in the opposite direction); it crosses zero around
   step ~20–25k and only reaches the reported −0.014 late. The "facilitating regime" the paper reports
   at this corner **does not exist at t=15,000**. The reported sign is therefore a property of the
   measurement horizon, not only of (`P_u`, κ).
2. **Magnitudes are still growing at t=40,000 in both rows**, and growing faster at high `P_u`
   (−0.011 → −0.030 vs +0.016 → −0.014). Since the paper's headline is that `P_u` shifts κ*, and κ* is
   read off these magnitudes, **κ* is currently a function of measurement time as well as of `P_u`**.

Consequence for the paper: either (a) run one κ-column to 80k–100k steps and show κ* has stabilised,
or (b) report the outcome at two or three horizons and frame the claim as "the ordering of κ* across
`P_u` rows is established by t≈30k and preserved thereafter" — which the table above does support at
κ=0.1 — rather than as an equilibrium property. What is **not** defensible is the current wording
("converged", "steady-state") combined with a single terminal window.

**Correction to a first reading of these numbers.** `popCountByClass_i` is *not* the camp's
population: it is `feedClassAgentCount[i]` (`OpinionDynamics.java:568-578`), the number of non-hub
agents who **accessed the platform and read a feed on that step**. It sums to ≈94 = 940 non-hub
agents × P_a = 0.1. The outcome is therefore a well-formed posts-per-accessor-per-step rate (posts are
also only produced by accessors), and the extreme camp is ≈21.4/94 ≈ **23% of the non-hub population
(≈214 agents)**, not 21 agents. No estimator bug — but the paper should say which denominator it uses,
because the two readings differ by a factor of 10.

**The extreme-camp result is not compositionally confounded** — accessing-agent counts are equal
across arms in every window (21.5 vs 21.3 at `p_u=0.05`; 21.4 vs 21.4 at `p_u=0.15`). One sentence in
§4 pre-empts the obvious reviewer question.

**But the moderate and near-extreme panels are.** Per-step accessing counts by class, trailing window:

| cell | arm | extreme− | near-ext− | moderate | near-ext+ | extreme+ |
|---|---|---|---|---|---|---|
| `p_u=.05, κ=.1` | control | 10.9 | 20.9 | **29.8** | 21.7 | 10.5 |
| | M-silent | 10.8 | 23.4 | **25.1** | 24.2 | 10.4 |
| `p_u=.15, κ=.1` | control | 10.8 | 20.7 | **30.5** | 21.4 | 10.6 |
| | M-silent | 10.8 | 23.4 | **25.2** | 24.0 | 10.5 |

Silencing the moderate hubs shrinks the moderate camp by **~16%** and grows each near-extreme camp by
**~12%**, while leaving the extreme camps untouched. Two consequences:

1. **Interpretive caveat for Fig. 1's first two panels.** Camps are not fixed sets of agents. Part of
   "the moderate camp posts less under M-silent" and "the near-extreme camp posts more" is that the
   near-extreme camp under M-silent now contains ex-moderates sitting just past the 0.2 boundary — a
   different population, not the same population behaving differently. Per-capita normalisation fixes
   the size change, not the composition change. State this, and ideally re-run the two direct-effect
   panels on agents classified by their **intrinsic** opinion O_i(0) (fixed by construction) as a
   robustness check — that version is confound-free and the data to compute it already exist.
2. **This is an unreported finding worth claiming.** A 16% contraction of the moderate camp is an
   opinion-level effect, not merely an expression-level one. The paper deliberately scopes itself to
   vocality, but "silencing moderate hubs de-moderates the opinion distribution itself" independently
   supports the upstream-regulator thesis and costs one sentence plus one row of numbers.
