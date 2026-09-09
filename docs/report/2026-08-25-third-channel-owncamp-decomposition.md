# 2026-08-25 — Third-channel (own-camp crowding) quantification for the extreme-camp mechanism

Follow-up to `2026-08-19-cna2026-3rd-full-review.md` §3.4 ("The direct channel is dismissed
qualitatively, and a third channel is unaccounted for"), which spot-checked 2 of 16 cells and found
own-camp feed volume also rises under M-silent. This entry extends that check to the full 16-cell
grid (`results/2026-08-14_lmp_feedmech_structural_9b`, 15 seeds/cell, trailing window (38000,40000]),
prompted by a CNA2026-5th.tex Discussion review session.

## What was computed

Per cell (P_u x VCR, 16 cells), control vs M-silent, extreme camp readers (bins 0/4) pooled:
- `d_own` = Delta(own-camp same-sign author-class count in feed) = feedAuthorClass0CountMean_0 +
  feedAuthorClass4CountMean_4, M-silent minus control.
- `d_ne` = Delta(near-extreme same-sign author-class count), matching the NE-E-influx figure's
  definition (feedAuthorClass1CountMean_0 + feedAuthorClass3CountMean_4).
- `q_own`, `q_ne` = instantaneous per-class comfort probability in the control arm
  (feedComfortClass{a}CountMean_r / feedAuthorClass{a}CountMean_r) -- NOT the same quantity as
  `cRateMean` (confirmed by spot-check: `cRateMean` is EMA-smoothed with memory across accesses;
  pooled feedComfortClass/feedAuthorClass ratio at a single step was ~0.95 vs reported `cRateMean`
  ~0.76 at the same step/cell -- so this is a first-order/instantaneous quantity, not the smoothed
  driver of posting probability).
- `contrib_own = d_own * q_own`, `contrib_ne = d_ne * q_ne` -- first-order approximation of each
  channel's contribution to the increase in comfortable-post count, and `own_share_of_total =
  contrib_own / (contrib_own + contrib_ne)`.

Script: throwaway, not checked in (`/private/tmp/.../scratchpad/third_channel_check.py`), reusing
`lmp_feedmech_stage1`/`lmp_feedmech_structural_9b`/`lmp_feedmech_grid4x4` helpers. No new simulation.

## Findings

1. **Own-camp feed volume rises under M-silent in all 16 cells** (`d_own` +0.145 to +0.394
   posts/feed), not just the 2 cells the 08-19 review spot-checked. Same direction as `d_ne` (+0.260
   to +0.872), i.e. removing the hub frees up feed slots that both near-extreme *and* own-camp
   followed accounts fill -- a compositional/slot-competition effect, not a network-gating (openness)
   effect.

2. **`q_own` is not uniformly ~1**, correcting the 08-19 review's simplifying assumption
   ("own-camp content is ~100% comfortable"). It ranges from ~0.50 at VCR=0.10 to ~0.99 at VCR=0.20:
   at a narrow comfort radius, even same-broad-camp (same bin) members are often outside each
   other's VCR, since the bin pools a range of opinions.

3. **First-order contribution share (`own_share_of_total`) is regime-dependent**: at low VCR (0.10,
   0.13 -- the *facilitating* regime, where the paper's sign-reversal is negative and is the more
   novel/headline half of the result), the own-camp channel dominates, contributing **59-85%** of the
   first-order comfortable-content increase, exceeding the near-extreme-mediated channel the paper's
   two-layer account attributes the whole effect to. Only at high VCR (0.17, 0.20 -- the *suppressing*
   regime) does the near-extreme channel become dominant (55-70%), where the paper's current account
   is better supported.

## Caveat

This is a first-order/instantaneous decomposition (`Delta(count) x instantaneous q`), not a rerun of
the actual EMA-driven `c_i(t)` dynamics that determine posting probability (Eq. 4 in the paper). It is
suggestive of relative channel magnitude, not a rigorous per-agent causal decomposition. A definitive
version would need to trace each agent's actual comfort-fraction update sequence under both arms.

## Correction (same day, later pass) — the real mechanism is follow-network erosion, not slot competition or an echo-chamber feedback loop

Prompted by two sharp follow-up questions in the same session:

1. "Is the feed actually at max capacity in control?" -- **No.** `feedCapacity=15`
   (`ExperimentConfig.java:179`), but realized extreme-camp feed size (`S_fd`) is only 2.0-2.4 across
   all 16 cells (control). The "slot competition" framing proposed earlier in this session assumed a
   capacity constraint that does not hold; retracted.

2. "Maybe the number of agents pinned at the top of the distribution is growing" (user's hypothesis,
   prompted by a recollection of network-structure exploration). Tested two readings of "pinned at the
   top" directly on `degrees/agent_snapshot_final.csv` (per-agent, `isTarget==0` i.e. non-hub, binned
   into opinion classes via `(opinion+1)/0.4` matching `Agent.java:259-261`), 15 seeds/cell:
   - **Ceiling comfort-rate count** (`avgComfortRate>=0.95`) among extreme-camp agents: at
     `pu=.05,vcr=.1` (facilitating), control=48.5 vs M-silent=46.3 (**decreases**, tracking the known
     negative aggregate effect); at `pu=.05,vcr=.2` (suppressing), control=123.9 vs M-silent=128.9
     (increases, tracking the known positive aggregate effect). Same sign as the already-known
     `cRateMean` effect -- no new information, this hypothesis as stated does not hold.
   - **Follower-count (in-degree) concentration**: extreme-camp `followerCount` stays tiny in both arms
     (mean 1.0-1.6, max 15-19, Gini~0.75-0.79 in both arms) -- no emergent "extreme-camp members become
     hubs" effect either.

3. **What actually explains it: `followeeCount` (out-degree, how many accounts an extreme agent
   follows) is ~2.3-2.4x higher under M-silent than control, uniformly across the grid**:

   | pu, vcr | control | M-silent | ratio |
   |---|---|---|---|
   | 0.05, 0.10 | 2.87 | 6.51 | 2.27x |
   | 0.08, 0.13 | 2.71 | 6.41 | 2.37x |
   | 0.11, 0.17 | 2.76 | 6.55 | 2.37x |
   | 0.15, 0.20 | 2.84 | 6.80 | 2.39x |

   Initial HK out-degree is 15 (m=15). Control-arm extreme agents have lost >80% of their initial ties
   by t=40,000; M-silent-arm agents have lost roughly half as much. The ratio is essentially invariant
   to both `P_u` and `VCR`, unlike `q_own`/`q_ne` (which are strongly VCR-dependent) -- consistent with
   a mechanism that gates *how much* content arrives (follow-network size), separate from the mechanism
   that gates *whether* arriving content registers as comfortable (VCR, per the existing "comfort
   layer").

   **Proposed causal story**: an active moderate hub is opinion-distant from extreme agents and posts
   at high volume, so extreme agents' feeds are frequently exposed to clearly out-of-tolerance content.
   Each such exposure can trigger the tie-eviction rule (evict the first out-of-tolerance followed
   author -- not necessarily the hub itself, since the rule doesn't target a specific author). Over
   40,000 steps this repeatedly strips ties to *other* followed accounts too, not just to the hub,
   producing a much more eroded follow network in control than in M-silent. Since realized feed size is
   bottlenecked by followee count (never by `feedCapacity=15`), a ~2.4x larger follow network mechanically
   delivers proportionally more content from *every* author class at once (own-camp and near-extreme
   alike) -- explaining why `d_own`, `d_ne`, and `d_sfd` are all positive and roughly VCR-invariant,
   and why `d_own` does not track the extreme camp's own per-capita posting-rate difference (it isn't
   caused by "posting more" -- it's caused by "each reader following more sources").

   This reframes and strengthens the existing "openness layer" (`docs/report` and the paper's Discussion
   describe it narrowly as "wider BC admits more near-extreme sources"): the effect is not specific to
   near-extreme admission -- it is a general follow-network-size effect that also mechanically inflates
   own-camp content. It also directly quantifies and extends review B5 (`2026-08-19-cna2026-3rd-full-review.md`):
   not only does the *hub's own* in-edge count diverge between arms (already noted there) -- the *reading*
   extreme agents' out-degree diverges by ~2.4x, which is arguably the more important structural fact
   for explaining the feed-composition results in Fig. 2.

   **Not yet verified**: the specific claim that eviction events target *other* followed accounts
   (not just the hub) as a side effect of hub exposure -- this is the mechanistically plausible
   explanation given the eviction rule's description in review B5, but hasn't been traced through
   per-event logs. Would need eviction-event-level data (not currently in the aggregate CSVs) to confirm
   directly rather than infer from the aggregate followeeCount gap.

## Scoping decision: arm-vs-P_u separability deferred to the journal extension

User pushback (correct): the claim "the BC/followeeCount gap depends on the arm itself, independent of
`P_u`" is currently only supported by eyeballing that the followeeCount ratio (~2.3-2.4x) looks similar
across the tested `P_u`/`VCR` grid -- it has not been established with a formal arm x `P_u` interaction
test (e.g. two-way ANOVA / interaction term on `followeeCount` or `bc`). Since every data point is
already at some (arm, `P_u`) pair, this is in principle testable with the existing 16-cell x 2-arm x 15-seed
data, but doing it properly is more effort than the CNA2026 short paper warrants.

**Decision**: do not chase this formal separability claim for CNA2026. Describe the finding only as an
observed empirical pattern (followeeCount rises substantially under M-silent, consistently across the
tested grid), without asserting a clean "arm main effect, no `P_u` interaction" statistical claim. Revisit
with a proper interaction test if/when this line of work moves to a journal-length extension.

## Implication for the paper

The current `CNA2026-5th.tex` Discussion (openness layer + comfort layer, both near-extreme-mediated)
does not mention the own-camp/slot-competition channel at all. Per the above, this is not a minor
omission for the low-VCR facilitating-regime cells specifically -- the channel not currently in the
text may be the dominant one there. Recommended next step if this is to be reflected in the paper:
add one sentence noting the compositional/slot-competition channel and scope the near-extreme-mediated
two-layer account explicitly to the high-VCR (suppressing) regime, or run the exact per-agent
decomposition before making a magnitude claim in either direction. Not yet applied to the tex file --
pending user decision on whether/how to incorporate.
