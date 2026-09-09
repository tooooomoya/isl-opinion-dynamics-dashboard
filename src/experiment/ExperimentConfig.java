package experiment;

import agent.Agent;

/**
 * Configuration for a single simulation run of the neutral-influencer / repost-hub study.
 * Drives both Exp A (channel isolation: small fixed neutral set, vary {@code channel})
 * and Exp B (number x size: vary {@code nNeutral} and {@code sizeStrategy}).
 *
 * The intervention pool is the top-K hubs by follower count on the initial network
 * (fixed pool size every run, so the controlled factorial stays balanced across seeds).
 *
 * Parsed from CLI args as space-separated {@code key=value} tokens, e.g.:
 *   seed=0 extreme=sym n_neutral=3 size=largest channel=both topk=15
 * A bare numeric first token is also accepted as the seed (backward compatibility).
 */
public class ExperimentConfig {
    public enum ExtremeMode { NONE, SYM, ASYM }
    public enum SizeStrategy { LARGEST, SMALLEST }

    // ---- Run identity ----
    public int seed = 0;
    // Network-generation seed; sentinel MIN_VALUE = fall back to `seed` (legacy single-seed
    // behavior). See resolvedNetSeed() below.
    public int netSeed = Integer.MIN_VALUE;

    // ---- Intervention design (Exp A: channel isolation; Exp B: number x size) ----
    public ExtremeMode extreme = ExtremeMode.NONE;
    public int nNeutral = 0;
    public SizeStrategy sizeStrategy = SizeStrategy.LARGEST;
    public Agent.ChannelMode channel = Agent.ChannelMode.BOTH;
    public int poolTopK = 15;          // intervention pool = top-K hubs by follower count
    public double asymDirection = 1.0; // sign of the single extreme hub in ASYM mode

    // ---- Network structure & generation ----
    // config-driven initial network (was a comment-block edit in setNetwork()).
    // 2026-07-10: default switched to hk (Holme-Kim network).
    // 2026-07-16: HK generator params (m/A/pt) recalibrated against Kwak et al. 2010's Twitter
    // follow-graph stylized facts (systematic-A/B calibration plan, Stage 1a — see
    // docs/report/calibration-sweep-results.md). This supersedes the old (3,1,0.3) literals that
    // were originally picked only to match journal.tex's (Latex-Journal-June) baseline, not
    // validated against real data. NB journal.tex is a separate, out-of-scope paper (CLAUDE.md) —
    // if it needs the old baseline, pass hk_m=3 hk_a=1 hk_pt=0.3 explicitly rather than relying on
    // this shared default, since this default now belongs to this paper's calibration.
    public String networkType = "hk"; // dcsbm|ba|hk|ws|dms|cnn|lfr|random|read
    public int sbmK = 4;                 // DC-SBM communities
    public double sbmPin = 0.08;         // DC-SBM intra-community affinity
    public double sbmPout = 0.002;       // DC-SBM inter-community affinity
    public double sbmGamma = 2.3;        // DC-SBM Pareto in-degree exponent
    public int sbmDeg = 50;              // DC-SBM target average in-degree
    public String readPath = "results/temp/step_1000.gexf"; // network=read source .gexf
    // Holme-Kim generator params. gamma = 2 + hkA/hkM targets Kwak et al. 2010's follow-graph
    // exponent ~2.276; hkPt controls clustering coefficient (target ~0.072, same source).
    // m=15/A=4 chosen over the better-fitting m=25 (Stage 1a grid) for compute-cost reasons —
    // Stage-1b/2 production-scale runs compound the initial density; m=20/m=25 are deferred to a
    // final robustness check, not dropped. pt=0.05 still leaves clustering ~2x the 0.072 target
    // (known, accepted limitation of the m=15 choice — docs/report/calibration-sweep-results.md).
    public int hkM = 15;      // out-edges per new node
    public int hkA = 4;       // initial attractiveness; gamma = 2 + hkA/hkM
    public double hkPt = 0.05; // triad-formation probability (clustering knob)
    // Joint Stage 1+bc+Stage 2 calibration (2026-07-18, docs/report/2026-07-18-joint-stage-
    // calibration.md): supersedes the separate Stage 1b/1c/1d (follow-graph only) and Stage
    // 2b/c/d (repost-network only) results above, which were invalidated by the bc mean-reversion
    // redesign (bc gates unfollowing, so it feeds follow-graph shape too — the two stages can't be
    // calibrated independently anymore). GP-BO over all 10 params jointly against combined
    // Gini=0.8/gamma_fit=2.276/opinionAssortativity floor 0.6/Q_sign_repost=0.48 loss, screen +
    // widen-and-rerun (3 dims pinned the first box's edges) + 5-seed confirmation, then rounded.
    // out_of_bc_repost_prob held fixed at 0.0 throughout (not swept).
    // 2026-07-22: app-pol baseline v5 calibration (out_of_bc_repost_prob fixed at 0.01,
    // init_dist=empirical fixed -- both experiment-specific treatment choices, NOT adopted as
    // defaults here; see docs/report/2026-07-21-conduit-experiment-design.md). SF1 excluded from
    // the round-level search loss (n=5 measurement noise exceeds the target window width -- see
    // same report), selected post-hoc via a 20-seed top-5 comparison instead; bin7 fit uses a
    // corrected per-capita-rate metric (v2-v4 compared raw totals against a per-capita target, a
    // bug). maxFollowCapacity pinned at its search box's lower edge for the third calibration in a
    // row (v2: 15, v4/v5: 5) -- still unresolved where this parameter actually wants to settle;
    // flagged, not fixed by this adoption. Structural facts solid (Gini/Q/assort); SF1 landed
    // 1.027+/-0.078 (n=20) vs. target [1.19,1.26] -- a real, un-closed gap even after this
    // calibration's two fixes (metric correction + vocalComfortRadius as a new free dimension).
    // 2026-07-23: app-pol baseline v9 calibration (round7/pt5) -- postProb mechanism replaced
    // (comfortPpFactor's ratchet -> postProbRelaxRate's graded relaxation, see Agent.java), fresh
    // 96-point BO search, plus a 6-candidate re-selection pass that fixed a bc_corr-ceiling scoring
    // bug in the original top-5 (docs/report/2026-07-21-conduit-experiment-design.md, "v9 top-K
    // re-selection"). round7/pt5 is the closest-to-target-SF1 candidate found across both passes
    // (102 points total) -- adopted here at the user's request for dashboard inspection, NOT
    // because it clears both structural targets: SF1=1.097+/-0.151 (target [1.19,1.26], still
    // short) and bc_extremity_corr=-0.097+/-0.095 (ceiling -0.1, misses by a hair). No point in
    // either pass cleared both simultaneously at n=20 -- see that report entry for the full
    // candidate table and what it implies about vocalComfortRadius's deferred density-bias fix.
    // 2026-07-24: app-pol baseline v12 calibration (round0/pt4) -- bc_corr loss term fixed from a
    // ceiling-clamp to a target(-0.3)-based linear credit (docs/report/2026-07-21-conduit-
    // experiment-design.md, "v12: bc_extremity_corr loss term fixed"). round0/pt4 was NOT among
    // v12's top-5 round_loss candidates (loss=5.32 vs the top-5's 2.4-3.7) but at n=3 looked
    // attractive on SF1 (1.222+/-0.074, in target range, unusually tight) and gini (0.804, on
    // target); bc_corr (-0.151) and Q_sign_repost (0.399) were mediocre, not standout. Adopted here
    // at the user's request for dashboard inspection after an n=10 re-check, NOT as v12's winning
    // candidate (that remains round_loss=3.697, SF1=1.044+/-0.343, bc_corr=-0.227+/-0.150 -- see the
    // v12 completion entry in the design doc; no point across v9/v11/v12 has cleared both targets).
    // 2026-07-25: app-pol baseline v13 calibration (candidate 4, the selected top-5 winner) -- FIRST
    // point across the entire v9-v13 series (~350 points evaluated) to jointly clear SF1-in-range
    // AND bc_extremity_corr<=-0.3 at n=20: SF1=1.238+/-0.145 (target [1.19,1.26]), bc_corr=
    // -0.541+/-0.100. Enabled by the graded-relaxation bc mechanism redesign (see bcDecRate/
    // bcRecoveryRate below) -- single-seed inspection confirmed a genuinely monotonic bc-vs-
    // opinion-extremity relationship (moderates mean bc=0.973, extremists mean bc=0.730), not just a
    // coincidental aggregate correlation. CAVEAT: bcDecRate, bcRecoveryRate, vocalComfortRadius, and
    // pU are ALL boundary-pinned at their v13 search-box edges, identically across all 5 top-K
    // candidates (not just this one) -- see docs/report/2026-07-21-conduit-experiment-design.md,
    // "Calibration v13 completed." bcDecRate=1.0 specifically means zero-inertia decline (one
    // net-uncomfortable step completely overwrites bc, no smoothing) -- a much stronger claim than
    // the negativity-dominance citations (Vallone 1985; Baumeister 2001, both about differential
    // weighting, not literal single-event resets) actually support. Adopted here for dashboard
    // inspection at the user's request, NOT as a scientifically finalized calibration -- the box
    // needs widening (bc_recovery lower, vocal_comfort_radius/p_u upper) and re-running before these
    // exact values should be treated as final.
    // 2026-07-25: app-pol baseline v15 calibration (SF1-selected candidate, time-constrained
    // "SF1+bin7 only" scope cut with bc_dec/bc_recovery/p_u/stub/alpha fixed from cross-era
    // variance review -- see docs/report/2026-07-21-conduit-experiment-design.md, "Calibration v15
    // launched"). SF1=1.148+/-0.130 (target [1.19,1.26], short by 0.077 but closest of v15's top-5),
    // bc_corr=-0.570 (clears -0.3 well), gini=0.867, assort=0.896 -- but Q_sign_repost=0.417 (target
    // 0.48) and bin7 W1=0.434 both still short, essentially unimproved from v13 despite the search
    // targeting bin7 exclusively (the SF1-closest candidate is NOT the best-bin7 candidate among
    // v15's top-5 -- #2/#4 had better bin7 fits at worse SF1; see design doc table). Adopted at the
    // user's request given the project deadline, not a fully closed calibration.
    public double maxFollowCapacity = 43.8638;  // was 43.6286 (v13 candidate 4's point)
    public double followProb = 0.01;         // was 0.01 (v13 candidate 4's point)

    // ---- Feed / algorithmic exposure ----
    // Joint calibration (2026-07-18, same run as maxFollowCapacity/followProb above). alpha/hop
    // are calibration-time anchors, not fixed experimental values -- research-direction.md's primary
    // swept factors are alpha/hop themselves; see the "calibration-time anchors" note in
    // docs/report/2026-07-15-calibration-decisions.md before treating these as permanent.
    // hop=1 was the top point across all 5 best candidates found (not a fluke of one point) --
    // read as "For-You surfaces buzz within your own 1-hop network" (velocity still re-ranks by
    // engagement within that pool, so this is not equivalent to the legacy chronological-only
    // model even at alpha's high value here), not as accidentally reproducing the legacy model.
    // 2026-07-25: app-pol baseline v15 calibration -- alpha FIXED (not searched), see
    // maxFollowCapacity above for full context.
    public double feedAlgoShare = 0.7; // alpha: was 0.76493 (v13 candidate 4's point); fixed constant in v15
    // 2026-07-29: reset from v13's 3 to the feed-redesign v4 joint-BO winner (hop x decay_mode x
    // decay_lambda, alpha/tau held fixed -- see docs/report/2026-07-29-feed-reach-redesign.md "v4").
    // PROVISIONAL, not a full recalibration -- structural/bc dims still pending the user's other-
    // server joint search; re-baseline once that lands.
    public int feedHopH = 4;               // hop: was 3 (v13 candidate 4's point, pre-feed-redesign)
    // 2026-07-29: reach direction + cutoff redesign, per user critique that the prior mechanism was
    // unrealistic on two counts -- see AdminOptim.computeReachable/acceptProbability for the
    // implementation and docs/report/2026-07-29-feed-reach-redesign.md for the full rationale.
    // (1) Reach BFS now follows ONLY followees edges (accounts you follow), not followers too --
    // "your For-You network" is who you (transitively) follow, not an undirected blob. This is a
    // straight correction, not a knob (research-direction.md's own hop-direction caveat flagged it
    // as unresolved -- now resolved in the followee-out-edge direction).
    // (2) The hard hop-cutoff (binary in/out at depth h) is replaced by a distance-decay ACCEPTANCE
    // PROBABILITY applied per candidate during the velocity-ranked scan -- P(d) where d = hop
    // distance (>=1). `feedDecayMode` selects the functional form; `h` still caps how many hops the
    // BFS bothers to search (distances beyond h are simply not computed => P=0), so this is no more
    // expensive than the old hard cutoff -- same BFS, it now records depth instead of a flat
    // boolean. "hard" reproduces the exact legacy behavior (P=1 if d<=h else 0) and is kept as a
    // selectable ablation arm, not deleted, so existing calibrated hop=3 runs remain reproducible
    // for direct comparison against the new decay modes (litmus-test convention, research-
    // direction.md's "knob, not assumption").
    public String feedDecayMode = "exp";     // hard|exp|inverse -- see comment above
    // lambda=0 degenerates every mode to "no decay" (P=1 for all reachable d), same as hard mode
    // with h=infinity. 2026-07-29: set to the feed-redesign v4 joint-BO winner (~0.10992, rounded)
    // alongside feedHopH above -- PROVISIONAL, see that field's comment for full context.
    public double feedDecayLambda = 0.11;     // exp: P=exp(-lambda*(d-1)); inverse: P=1/(1+lambda*(d-1))
    public String velMode = "windowed"; // velocity scoring mode for the For-You feed (cumulative|windowed)
    // 2026-07-29: optional extra recency dampener on the velocity score itself (on top of
    // windowed/cumulative mode), aimed at the self-reinforcement risk (surfaced -> more reposts ->
    // score stays elevated -> keeps surfacing) that windowed mode only partially addresses -- see
    // docs/report/2026-07-29-feed-reach-redesign.md. Default 0 = off (unchanged prior behavior);
    // DEFERRED magnitude, same status as feedDecayLambda above. When >0, multiplies the velocity
    // score by exp(-age/tau) (AdminOptim.velocityScore/windowedVelocityScore).
    // 2026-07-29: set to 30 (v3 tau-scan recommendation -- midpoint of the [20,40] band that
    // meaningfully reduces self-reinforcement runaway without crushing virality; see
    // docs/report/2026-07-29-feed-reach-redesign.md "v3"). User decision: tau must be strictly
    // positive, never 0 -- some organic decay should always be present. PROVISIONAL, see feedHopH
    // above for full context.
    public double feedTimeDecayTau = 30.0;
    // 2026-07-25: app-pol baseline v15 calibration -- see maxFollowCapacity above for full context.
    public int feedCapacity = 15;       // was 40 (v13 candidate 4's point)
    // 2026-07-10: promoted off Const.ACCESS_PROB (was a hardcoded, unswept 0.1) so the model's
    // one global timescale knob — it gates an agent's ENTIRE per-step action set, including the
    // FJ/bounded-confidence opinion update itself (OpinionDynamics.java's per-agent loop: `if
    // (nextDouble() > accessProb) continue;` before repost/follow/unfollow/post/updateMyself()) —
    // is actually sweepable. Homogeneous across agents at construction; per-agent heterogeneity
    // post-construction is still possible via Agent.setAccessProb() (used by the GEXF round-trip).
    // 2026-07-25: cut to 1/4 (user decision, time-constrained param freeze -- docs/report/2026-07-
    // 21-conduit-experiment-design.md, "Periodic bin7 snapshots" entry). The bin7 fit was found to
    // be non-stationary -- best around step 10000, degrading steadily out to 40000 (v15 config,
    // single-seed check) -- rather than re-searching parameters with no time left, accessProb
    // (this model's single global timescale knob, gating whether an agent acts at all this step)
    // was cut 4x on the reasoning that it should rescale the dynamics' effective time axis by
    // roughly that same factor, moving the ~step-10000 sweet spot out to ~step-40000 (the
    // dashboard's default run length) instead of re-tuning every other parameter. Not verified to
    // be exactly linear (network-growth/follow dynamics have their own probabilistic gating too) --
    // check the actual bin7-snapshot shift before treating this as confirmed.
    public double accessProb = 0.1;

    // ---- Bounded-confidence opinion dynamics (core FJ mechanism) ----
    // 2026-07-25: app-pol baseline v13 calibration (candidate 4) -- see maxFollowCapacity above for
    // full context. pU is boundary-pinned at v13's search-box upper edge (0.1) -- true optimum may
    // want to go higher; see the v13 completion entry in the design doc.
    public double pU = 0.05; // P_u: the phase-diagram knob. probability of unfollowing a disagreeing followee (out-of-tolerance) per step
    // 2026-07-24: bc mechanism redesigned from a per-post ratchet to a graded per-step relaxation
    // toward a shared target (see Agent.java's updateMyself() comment) -- bcDecRate/bcRecoveryRate
    // are RETAINED as names but REINTERPRETED as relaxation-rate fractions of the gap closed per
    // step (not a per-post multiplicative-shrink constant / additive-toward-ceiling constant as
    // before). Negativity-dominance asymmetry (Vallone 1985; Baumeister 2001) is now the single
    // ratio bcDecRate/bcRecoveryRate, left free/swept rather than hardcoded to a fixed multiplier
    // (no citation gives a precise ratio -- see design doc discussion, 2026-07-24). Old calibrated
    // values (bcRecoveryRate=0.00156, bcDecRate=0.95134, v12 round0/pt4) do NOT carry over under
    // the new units -- 0.95134 as a per-step gap-closing fraction would mean bc nearly instantly
    // snaps to target every step, the opposite of "near-static" under the old semantics. Reset to
    // untuned placeholders (order-of-magnitude matched to postProbRelaxRate's default) pending v13
    // recalibration under the new mechanism; decRate > recoveryRate only to preserve the intended
    // asymmetry direction, not a considered value.
    // Content-independent mean-reversion rate: bc += bcRecoveryRate * (bcInit - bc) every post,
    // regardless of whether that post was comfortable (replaces the old symmetric multiplicative
    // ratchet `bc *= bcIncRate` on comfortable contact, which had no restoring force and drove
    // near-total boundary absorption under homophily-sorted feeds — docs/report/2026-07-18-bc-pp-
    // boundary-collapse-diagnosis.md). 0.0 = no recovery (monotone-only decline ratchet).
    // 2026-07-20 (v9, docs/report/2026-07-18-joint-stage-calibration.md): after v4-v6's balanced
    // 4-fact search kept trading SF1 off against Gini/Q/assort, re-ran a search that optimizes
    // ONLY the SF1 apparent-polarization ratio (mean+variance penalty), ignoring the other 3
    // facts, as a ceiling-finding exercise -- winning point had bc_dec=0.999 (near the search
    // box's edge). User noted that with decline this weak and recovery this strong, bc barely
    // ever leaves bcInit in practice -- tested directly: bc_dec=1.0 EXACTLY (not an approximation)
    // makes bc *provably* static, since `bc *= 1.0` never changes it and bc starts at bcInit, so
    // the recovery term multiplies zero forever too. 20-seed confirm at bc_dec=1.0 reproduced
    // v9's dynamic-bc point almost exactly (Gini/Q/assort identical to 3 decimals, ratio in the
    // same noisy range, crossCuttingFraction/interactionCrossCuttingFraction both ~0.04-0.05) --
    // the asymmetric decline/recovery mechanism is vestigial at this operating point. Adopted the
    // simpler static-bc config; bcRecoveryRate has no effect once bcDecRate=1.0 (set to 0 for
    // honesty, not left at a number that implies unused dynamics).
    // 2026-07-21: switched OFF the static-bc/v9 point as the default baseline, per the Path-1
    // causal-check design (docs/report/2026-07-21-conduit-experiment-design.md) -- v9's SF1
    // calibration was circular (baseline tuned to already hit the apparent-polarization target the
    // conduit hypothesis is supposed to explain). Reverted to v7's point instead: 3 of 4 structural
    // facts solid and stable (Gini/Q/assort), SF1 short by a real but modest ~12-15%, and the bc
    // mechanism is genuinely dynamic (not frozen) -- a non-circular base to manipulate on top of.
    // The v9/static-bc values (bcRecoveryRate=0.0, bcDecRate=1.0, bcInit=0.56, comfortPpFactor=0.5)
    // are preserved verbatim in that report's "Snapshot" section if this needs to be restored.
    // 2026-07-25: app-pol baseline v13 calibration (candidate 4) -- first calibrated values under the
    // new graded-relaxation semantics (supersedes the untuned 0.01/0.02 placeholders above). BOTH
    // boundary-pinned at v13's search-box edges (bc_recovery at the lower edge, bc_dec at the
    // hard-ceiling 1.0) -- identically across all 5 top-K candidates, not just this one. Asymmetry
    // ratio here is ~2000x (bc_dec/bc_recovery = 1.0/0.0005), far past what either negativity-
    // dominance citation supports and far past the ~2-2.5x loss-aversion analogue discussed when this
    // was left free rather than hardcoded. bc_dec=1.0 means zero-inertia decline: a single
    // net-uncomfortable step completely overwrites bc with no memory of prior history, closer to a
    // single-event "grudge" dynamic than gradually eroding tolerance. Flagged as needing box-widening
    // + re-calibration before treating as final -- see design doc "Calibration v13 completed."
    public double bcRecoveryRate = 0.0001;  // was 0.01 (untuned placeholder); boundary-pinned at v13's search-box lower edge
    public double bcDecRate = 0.5;          // gap-closing rate toward target on net-uncomfortable steps, sweepable; was 0.02 (untuned placeholder); pinned at the hard ceiling (zero inertia -- see note above)
    // 2026-07-14: migrated off Const.MINIMUM_BC / Const.BOUNDED_CONFIDENCE (both static-final, no
    // CLI path) so the clamp bounds on the dynamic bc ratchet are sweepable — needed to test
    // whether the bc histogram's bimodal pile-up at the bounds is a genuine emergent bistability
    // or an artifact of the clamp location (docs/report/2026-07-14-bc-bound-robustness-check.md).
    // bcCeiling doubles as bc's initial value (Agent constructor), matching the old BOUNDED_CONFIDENCE
    // dual role. Const.VOCAL_COMFORT_RADIUS (fixed at the old MINIMUM_BC=0.2) stays separate — it is
    // the R5/D4 perceptual comfort radius for the vocal-minority mechanism and must NOT move with
    // this sweep, or the two mechanisms would be conflated.
    public double bcFloor = 0.2;
    public double bcCeiling = 1.0;
    // 2026-07-14 correction: bc's initial value used to be hardwired to bcCeiling (old
    // BOUNDED_CONFIDENCE dual role), which confounds any bcCeiling sweep — widening the ceiling
    // also widens the day-0 tolerance window and thus the day-0 comfort probability, biasing the
    // whole population toward the ceiling regardless of whether the wall itself matters. Decoupled
    // so a boundary-robustness sweep can hold the starting point fixed while only moving the walls.
    // 2026-07-18: bcInit now doubles as the mean-reversion target for bcRecoveryRate (above), so it
    // can no longer default to bcCeiling — reverting toward the ceiling would reproduce the same
    // boundary-collapse problem the mean-reversion redesign was meant to fix.
    // 2026-07-21: reverted to v7's point (bcInit=0.838, raw BO value) as part of the Path-1
    // non-circular-baseline switch -- see bcRecoveryRate/bcDecRate above and
    // docs/report/2026-07-21-conduit-experiment-design.md. The v9/static-bc value (0.56) is
    // preserved in that report's "Snapshot" section.
    // 2026-07-23: app-pol baseline v9 calibration -- fixed at bcCeiling (BC_INIT_FIXED in
    // scripts/app_pol_baseline_bo_v7_wide_bc_init.py onward), not itself a free dim since v7: with
    // bc_init at the floor (v6's winner), only recovery could differentiate agents, and recovery
    // favored moderates by opinion-space density rather than genuine disagreement exposure -- see
    // maxFollowCapacity above and docs/report/2026-07-21-conduit-experiment-design.md ("uniform-bc
    // collapse" finding) for the full mechanism.
    public double bcInit = 0.8; // was 0.4141 (v5's point, pre-dates the bc_init-fixed-high finding)
    public boolean initOpinionClip = false; // legacy clipped-Gaussian initial opinions (default false = truncated resampling)
    // 2026-07-21: alternative to the (symmetric, mean-0) Gaussian/truncated-Gaussian generator --
    // "empirical" draws each agent's intrinsic opinion from the real, asymmetric 7-bin distribution
    // in Const.EMPIRICAL_OPINION_BIN_COUNTS (Buntain & Snegovaya 2025 survey data) instead. Default
    // "gaussian" preserves existing behavior (initOpinionClip still selects clip vs truncate within
    // that branch); "empirical" ignores initOpinionClip entirely (nothing to clip/truncate).
    public String initOpinionDist = "gaussian";
    // 2026-07-19: promoted off Const.VOCAL_COMFORT_RADIUS (fixed 0.2, no CLI path) to test whether
    // its fixed width is what's suppressing SF1 apparent-polarization (docs/report/2026-07-18-
    // joint-stage-calibration.md v3 diagnosis): comfortPostRate measures the fraction of an agent's
    // feed within this ABSOLUTE window of their own opinion, which structurally favors agents in
    // high-density regions of the opinion distribution (moderates) over sparse regions (extremes),
    // independent of network homophily quality -- a fixed radius may simply be the wrong yardstick.
    // 2026-07-22: finally tested, as a free dim in the app-pol baseline v5 calibration -- see
    // maxFollowCapacity above for full context. Landed at 0.1257 (narrower than the untested 0.2
    // default), but did not close the SF1 gap on its own (winner's SF1 still 1.027 vs [1.19,1.26]).
    // 2026-07-23: app-pol baseline v9 calibration (round7/pt5) -- still narrower again. This fixed-
    // absolute-window definition is the prime suspect for why v9's whole search (postProb mechanism
    // now fixed, 102 points evaluated) never found a point clearing both SF1 and bc_corr targets --
    // see docs/report/2026-07-21-conduit-experiment-design.md ("v9 top-K re-selection"). Not
    // redefined by this adoption, only re-valued.
    // 2026-07-24: app-pol baseline v12 calibration (round0/pt4) -- wider again, back near v5's
    // range. See maxFollowCapacity above for full context.
    // 2026-07-25: app-pol baseline v13 calibration (candidate 4) -- wider still, boundary-pinned at
    // v13's search-box upper edge (0.5, half the entire opinion range) identically across all 5
    // top-K candidates -- true optimum may want to go wider. See design doc "Calibration v13
    // completed."
    // 2026-07-25: app-pol baseline v15 calibration -- pinned at the box's exact upper edge (0.5)
    // again. Best-bin7-fit points across v13's history that also held gini near-target sat at
    // vcr~0.45-0.5 too -- consistent, not a fluke. See maxFollowCapacity above for full context.
    public double vocalComfortRadius = 0.1; // was 0.45227 (v13 candidate 4's point)

    // ---- Repost & relay mechanism ----
    public double repostProb = 0.1; // base repost probability
    // Diagnostic (2026-07-08): master switch for relay distortion + reattribution (research-
    // direction.md §3 items 1-2). false = verbatim repost, original attribution, no misrepresentation
    // grievance — tests whether Type-2-looking outcomes require the reattribution bypass or emerge
    // from sparse-network dynamics alone. Default false = disabled for this diagnostic pass;
    // set relay_enabled=true to restore the reattribution-bypass mechanism.
    public boolean relayEnabled = false;
    public boolean coupleRelayDistortion = true;  // explicit boolean coupling; default true = couple to stubbornness
    public double relayDistortionStrength = 0.5;  // only used when coupleRelayDistortion=false
    // 2026-07-17: repost is now permanently bc-gated (Agent.repost()) -- this is always the
    // out-of-bc repost rate, no coupling toggle (see Agent.java comment, same precedent as
    // bcGateAssim's removal). Held fixed at 0.0 (not swept) in the 2026-07-18 joint calibration
    // (docs/report/2026-07-18-joint-stage-calibration.md) -- consistent with the earlier Stage-2d
    // BO independently driving this to 0 across stage2b/c/d as well (a genuine floor, not a
    // boundary-pinning artifact, since probabilities can't go negative). Still an open item if a
    // nonzero out-of-bc repost rate is wanted later -- it would need its own calibration pass, not
    // just re-adding it to the existing joint search's dimensions.
    public double outOfBCRepostProb = 0.01;
    public String relAttrib = "original"; // relay attribution (original = legacy conduit immunity; reposter = sanctions hit relayer)

    // ---- Agent heterogeneity: stubbornness & capacity eviction ----
    // Joint calibration (2026-07-18, docs/report/2026-07-18-joint-stage-calibration.md). Raw BO
    // 0.687, rounded. Supersedes the Stage-2d value (0.95), which was consistently boundary-pinned
    // across stage2b/c/d under the old bc mechanism -- the joint search's winning point landed
    // comfortably interior instead, no pinning.
    // stubDist=const would ignore stubMin/stubMax entirely (uses the hardcoded
    // Const.INITIAL_STUBBORNNESS=0.7) -- must be "uniform" with stubMin=stubMax for a constant
    // value to actually take effect (same workaround the Stage-2 sweep scripts use).
    // 2026-07-25: app-pol baseline v15 calibration -- FIXED (not searched), from a cross-era
    // variance review (v9+v12+v13's top-5 pooled, stub had the lowest coefficient of variation of
    // any dim: CV=0.09, mean=0.822) -- see maxFollowCapacity above for full context.
    public String stubDist = "uniform"; // stubbornness distribution (const|uniform); uniform draws in [stubMin, stubMax]
    public double stubMin = 0.82; // was 0.9 (v13 candidate 4's point); fixed constant in v15
    public double stubMax = 0.82; // was 0.9 (v13 candidate 4's point); fixed constant in v15
    public double evictBeta = -1;     // capacity eviction: <0 = legacy argmax-disagreement; >=0 softmax temperature (0 = uniform)
    public String initPrune = "trim"; // trim removes over-cap followees at t=0 (none = legacy over-cap start)

    // ---- Posting-probability dynamics ----
    // Joint calibration (2026-07-18, docs/report/2026-07-18-joint-stage-calibration.md). Raw BO
    // 0.212, rounded.
    // 2026-07-25: app-pol baseline v15 calibration -- see maxFollowCapacity above for full context.
    public double initialPostProb = 0.25537; // was 0.01 (v13 candidate 4's point)
    public double maxPostProb = 1.0;
    // 2026-07-24: fixed at 0.01 (not swept) in every v11/v12 launch() call, per the user's
    // "lower the minPostingProb to 0.01" request -- was silently 0.05 (an untokenized default) in
    // every calibration before v11; see design doc's "Calibration v11" entry.
    public double minPostProb = 0.01;
    // 2026-07-23: replaced the symmetric multiplicative ratchet (postProb *= factor / /= factor
    // around comfortPostRate=0.5) with a graded relaxation toward a comfort-proportional target --
    // see Agent.java's updateMyself() comment and docs/report/2026-07-21-conduit-experiment-
    // design.md for the full diagnosis (the old ratchet had no restoring force, so postProb
    // saturated to minPostProb/maxPostProb for every agent regardless of *how* comfortable their
    // feed was, collapsing the intended extreme-vs-moderate vocality gap). This field is now eta in
    // `postProb += eta * (targetPostProb - postProb)`, not a multiplicative factor -- the old
    // comfortPpFactor values (0.1-3.0 range, calibrated for the old mechanism) are not meaningful
    // here. 0.01 is an untuned placeholder (time constant ~100 steps, matching comfortHistory's
    // window) pending recalibration; not yet swept under the new mechanism.
    // 2026-07-25: app-pol baseline v15 calibration -- see maxFollowCapacity above for full context.
    public double postProbRelaxRate = 0.1; // was 0.1 (v13 candidate 4's point)

    // ---- Camp/polarization analysis (sign-based metrics only; not a dynamics parameter) ----
    // 2026-07-18: agents with |opinion| < neutralBandHalfWidth are excluded from the two-camp
    // partition used by every sign-based analysis metric (Q_sign, Q_sign_repost,
    // crossCuttingFraction, interactionCrossCuttingFraction, RWC, and the Guerra et al. 2013
    // boundary-polarization measures) -- they count as neither "positive-camp" nor "negative-camp"
    // for those metrics specifically (opinionAssortativity/interactionAssortativity are untouched:
    // they use each agent's continuous opinion value directly, no camp partition at all).
    // Rationale: Conover et al. 2011's manual political-identity coding left ~5-11% of (actively
    // tweeting) users "undecidable," excluded from the left/right camps rather than force-assigned
    // -- a bare sign(opinion) split has no such exclusion. 0.2 is not derived from that paper (it
    // doesn't use a numeric opinion threshold at all -- its communities come from network
    // clustering, opinion labels are a post-hoc validation step); it carries over this project's
    // own prior convention of splitting [-1,1] into 5 equal-width camps, neutral = the middle
    // one. Given this model includes non-posting/silent agents (unlike Conover's necessarily-vocal
    // Twitter sample), the resulting excluded fraction is expected to exceed Conover's ~11% for
    // the population as a whole -- that is the intended effect, not something to correct back down.
    public double neutralBandHalfWidth = 0.2;

    // ---- Scale, duration & logging ----
    public int n = 1000;
    public int steps = 40000;
    public int interactionWindow = 5000; // windowed interaction-graph snapshot interval
    public int assertInterval = 1000;    // invariant-check cadence in steps (1 = legacy every-step)
    public boolean logRepostCascade = true;
    public boolean logGexf = true;
    // 2026-07-29: per-post lifespan/self-reinforcement log (posts/post_lifespan.csv), written once
    // per post at eviction from the For-You candidate window -- see AdminOptim.recordLifespan and
    // docs/report/2026-07-29-feed-reach-redesign.md. Bounded volume (one row per post that was ever
    // reposted, not per repost event like repost_cascades.csv), so on by default like that log.
    public boolean logPostLifespan = true;
    // force=true deletes a pre-existing result folder instead of aborting ("never overwrite" is
    // still the default; this is an explicit opt-in escape hatch). Not part of tag() — it's a
    // run-mechanics flag, not a model parameter, so it must not affect folder identity.
    public boolean force = false;

    // ---- 2026-07-26: explicit-ID-list hub manipulations (bridging-role isolation) ----
    // Applied to an arbitrary externally-supplied agent-ID list (e.g. "the neutral hubs realized
    // in this seed's mid tier"), NOT the InterventionSetup pool-selection machinery above (that
    // pathway picks hubs by its own extreme/topk/sizeStrategy heuristics; these three are driven
    // directly by an ID list computed outside the model, same pattern as the swap-experiment
    // scripts). Deliberately not part of tag() (see the "migrate-or-delete" note above) -- these
    // are always paired with a distinct continuation `seed` per (arm, tier) already, so folder
    // collision isn't a concern here the way it is for swept BO dimensions.
    public java.util.Set<Integer> muteAccessIds = java.util.Set.of();   // accessProb=0: full deactivation
    public java.util.Set<Integer> muteRepostIds = java.util.Set.of();   // ChannelMode=POST_ONLY: keep posting, stop reposting
    public java.util.Set<Integer> algoExcludeIds = java.util.Set.of();  // excluded from the For-You velocity-ranked candidate pool only
    // 2026-07-28: true node-removal counterfactual, distinct from algoExcludeIds above.
    // algoExcludeIds only changes what the For-You BFS is willing to traverse -- the underlying
    // followees/followers graph is explicitly left untouched (see AdminOptim.computeReachable's
    // comment), so an algo-excluded hub still fully propagates through the ordinary chronological
    // cascade (followers -> followers-of-followers) and still counts as a real edge in every
    // structural metric (modularity, crossCuttingFraction, assortativity, degree distribution).
    // removeHubIds instead severs the hub's real edges (both directions, via the same
    // AdminOptim.removeFollowEdge used by ordinary unfollow dynamics) and fully mutes them
    // (ChannelMode.NONE + accessProb=0), at t=0 of the run (OpinionDynamics.evolve()). Self-sealing:
    // Agent.follow()'s candidate list is built only from posts actually seen in an agent's feed, and
    // a muted, edge-severed hub can never author or be routed a new post again, so nobody can
    // rediscover/reconnect to them afterward -- no separate anti-reconnection guard needed.
    public java.util.Set<Integer> removeHubIds = java.util.Set.of();

    // ---- 2026-08-02: delayed-conduit-entry mechanism (orthogonally-popular neutral class) ----
    // Motivation: the mega/middle-tier "neutral hub" pool selected from the POST-EQUILIBRIUM
    // network (moderate_hub_5tier_removehub.py etc.) already has an opinion-homophily-shaped,
    // camp-correlated follower base by the time it's selected -- individually near-zero necessity
    // (docs/report/2026-07-21-conduit-experiment-design.md, "founder-clique redundancy") is a
    // direct consequence. This pair of fields instead lets an externally-supplied ID list (e.g.
    // "top-followerCount, |opinion|<0.2 agents on the INITIAL t=0 network, before any opinion-
    // homophily rewiring has happened") be pinned neutral and held silent, then activated
    // together at a single fixed step -- modeling a class of agents popular for reasons orthogonal
    // to this topic (their t=0 audience isn't yet opinion-sorted) who only start speaking on the
    // topic once it's already contentious. Deliberately two independent fields (not one), matching
    // the existing muteAccessIds/muteRepostIds/algoExcludeIds/removeHubIds precedent of orthogonal,
    // combinable single-purpose ID-list knobs -- a caller may want pinning without delayed
    // activation (activationStep=0) or vice versa.
    // pinNeutralIds: intrinsicOpinion/opinion forced to 0.0 at t=0 ONLY -- a one-time reset, not
    // a permanent freeze. stubbornness is intentionally left at its normal per-agent draw (NOT
    // forced to 1.0, unlike InterventionSetup.pinHub) -- these agents are neutral because they
    // weren't engaged with this topic, not because they're stubbornly anchored to centrism,
    // so their opinion should remain free to drift via ordinary FJ assimilation once
    // engaged (user decision, 2026-08-02).
    public java.util.Set<Integer> pinNeutralIds = java.util.Set.of();
    // silentUntilIds: ChannelMode=NONE at t=0; switches to cfg.channel at step==activationStep.
    // NOTE known risk (2026-08-02, not yet mitigated): Agent.follow()'s capacity-based eviction
    // (Agent.java, softmaxEvict/legacy argmax-disagreement path) can still sever OTHER agents'
    // follow edges INTO a silenced member -- purely by opinion-distance pressure as the network
    // sorts, with no post/content involved -- since that eviction is not gated on unfollow()'s
    // content-reactive path. Silence does not guarantee the pre-silence follower base survives
    // intact to activationStep; this must be checked empirically (followerCount of silentUntilIds
    // at each periodic degree snapshot) per run, not assumed by construction.
    public java.util.Set<Integer> silentUntilIds = java.util.Set.of();
    public int activationStep = 0;

    // 2026-08-04: generalization of pinNeutralIds for the L/M/P hub-tier design (docs/report/
    // 2026-08-02-delayed-moderate-conduit-pilot.md, "new L/M/P hub-tier experimental design" entry)
    // -- that design's non-neutral categories (Extreme/Pre-extreme, both signs) need an explicit
    // per-agent pin TARGET, not the fixed 0.0 that pinNeutralIds hard-codes. Same one-time-reset-
    // at-t=0, stubbornness-left-free semantics as pinNeutralIds (see its javadoc above); kept as a
    // separate field rather than replacing pinNeutralIds so existing scripts using pin_neutral_ids
    // (fixed 0.0) keep working unchanged. A given agent id should appear in at most one of the two.
    public java.util.Map<Integer, Double> pinOpinionIds = java.util.Map.of();

    private static java.util.Set<Integer> parseIdSet(String v) {
        if (v == null || v.isBlank()) return java.util.Set.of();
        java.util.Set<Integer> ids = new java.util.HashSet<>();
        for (String tok : v.split(",")) ids.add(Integer.parseInt(tok.trim()));
        return ids;
    }

    // Format: "id:opinion,id:opinion,..." e.g. "12:0.8,47:-0.4"
    private static java.util.Map<Integer, Double> parseIdValueMap(String v) {
        if (v == null || v.isBlank()) return java.util.Map.of();
        java.util.Map<Integer, Double> m = new java.util.HashMap<>();
        for (String tok : v.split(",")) {
            int c = tok.indexOf(':');
            m.put(Integer.parseInt(tok.substring(0, c).trim()), Double.parseDouble(tok.substring(c + 1).trim()));
        }
        return m;
    }

    public static ExperimentConfig fromArgs(String[] args) {
        ExperimentConfig c = new ExperimentConfig();
        if (args.length > 0 && !args[0].contains("=")) {
            c.seed = Integer.parseInt(args[0].trim());
        }
        for (String a : args) {
            int eq = a.indexOf('=');
            if (eq < 0) continue;
            String k = a.substring(0, eq).trim();
            String v = a.substring(eq + 1).trim();
            switch (k) {
                case "seed" -> c.seed = Integer.parseInt(v);
                case "extreme" -> c.extreme = ExtremeMode.valueOf(v.toUpperCase());
                case "n_neutral" -> c.nNeutral = Integer.parseInt(v);
                case "size" -> c.sizeStrategy = SizeStrategy.valueOf(v.toUpperCase());
                case "channel" -> c.channel = Agent.ChannelMode.valueOf(v.toUpperCase());
                case "topk" -> c.poolTopK = Integer.parseInt(v);
                case "asym_dir" -> c.asymDirection = Double.parseDouble(v);
                case "alpha" -> c.feedAlgoShare = Double.parseDouble(v);
                case "hop" -> c.feedHopH = Integer.parseInt(v);
                case "feed_decay_mode" -> c.feedDecayMode = v.toLowerCase();
                case "feed_decay_lambda" -> c.feedDecayLambda = Double.parseDouble(v);
                case "feed_time_decay_tau" -> c.feedTimeDecayTau = Double.parseDouble(v);
                case "bc_recovery" -> c.bcRecoveryRate = Double.parseDouble(v);
                case "p_u" -> c.pU = Double.parseDouble(v);
                case "max_follow" -> c.maxFollowCapacity = Double.parseDouble(v);
                case "net_seed" -> c.netSeed = Integer.parseInt(v);
                case "relay_enabled" -> c.relayEnabled = Boolean.parseBoolean(v);
                case "couple_relay_distortion" -> c.coupleRelayDistortion = Boolean.parseBoolean(v);
                case "relay_distortion_strength" -> c.relayDistortionStrength = Double.parseDouble(v);
                case "out_of_bc_repost_prob" -> c.outOfBCRepostProb = Double.parseDouble(v);
                case "bc_dec" -> c.bcDecRate = Double.parseDouble(v);
                case "bc_floor" -> c.bcFloor = Double.parseDouble(v);
                case "bc_ceiling" -> c.bcCeiling = Double.parseDouble(v);
                case "bc_init" -> c.bcInit = Double.parseDouble(v);
                case "vocal_comfort_radius" -> c.vocalComfortRadius = Double.parseDouble(v);
                case "init_op" -> c.initOpinionClip = v.equalsIgnoreCase("clip");
                case "init_dist" -> c.initOpinionDist = v.toLowerCase();
                case "assert_int" -> c.assertInterval = Integer.parseInt(v);
                case "network" -> c.networkType = v.toLowerCase();
                case "sbm_k" -> c.sbmK = Integer.parseInt(v);
                case "sbm_pin" -> c.sbmPin = Double.parseDouble(v);
                case "sbm_pout" -> c.sbmPout = Double.parseDouble(v);
                case "sbm_gamma" -> c.sbmGamma = Double.parseDouble(v);
                case "sbm_deg" -> c.sbmDeg = Integer.parseInt(v);
                case "read_path" -> c.readPath = v;
                case "hk_m" -> c.hkM = Integer.parseInt(v);
                case "hk_a" -> c.hkA = Integer.parseInt(v);
                case "hk_pt" -> c.hkPt = Double.parseDouble(v);
                case "repost_prob" -> c.repostProb = Double.parseDouble(v);
                case "stub_dist" -> c.stubDist = v.toLowerCase();
                case "stub_min" -> c.stubMin = Double.parseDouble(v);
                case "stub_max" -> c.stubMax = Double.parseDouble(v);
                case "evict_beta" -> c.evictBeta = Double.parseDouble(v);
                case "init_prune" -> c.initPrune = v.toLowerCase();
                case "vel_mode" -> c.velMode = v.toLowerCase();
                case "rel_attrib" -> c.relAttrib = v.toLowerCase();
                case "interaction_window" -> c.interactionWindow = Integer.parseInt(v);
                case "n" -> c.n = Integer.parseInt(v);
                case "steps" -> c.steps = Integer.parseInt(v);
                case "log_repost_cascade" -> c.logRepostCascade = Boolean.parseBoolean(v);
                case "log_gexf" -> c.logGexf = Boolean.parseBoolean(v);
                case "log_post_lifespan" -> c.logPostLifespan = Boolean.parseBoolean(v);
                case "force" -> c.force = Boolean.parseBoolean(v);
                case "feed_capacity" -> c.feedCapacity = Integer.parseInt(v);
                case "follow_prob" -> c.followProb = Double.parseDouble(v);
                case "initial_pp" -> c.initialPostProb = Double.parseDouble(v);
                case "max_pp" -> c.maxPostProb = Double.parseDouble(v);
                case "min_pp" -> c.minPostProb = Double.parseDouble(v);
                case "pp_relax_eta" -> c.postProbRelaxRate = Double.parseDouble(v);
                case "neutral_band" -> c.neutralBandHalfWidth = Double.parseDouble(v);
                case "access_prob" -> c.accessProb = Double.parseDouble(v);
                case "mute_access_ids" -> c.muteAccessIds = parseIdSet(v);
                case "mute_repost_ids" -> c.muteRepostIds = parseIdSet(v);
                case "algo_exclude_ids" -> c.algoExcludeIds = parseIdSet(v);
                case "remove_hub_ids" -> c.removeHubIds = parseIdSet(v);
                case "pin_neutral_ids" -> c.pinNeutralIds = parseIdSet(v);
                case "pin_opinion_ids" -> c.pinOpinionIds = parseIdValueMap(v);
                case "silent_until_ids" -> c.silentUntilIds = parseIdSet(v);
                case "activation_step" -> c.activationStep = Integer.parseInt(v);
                case "results_subdir" -> c.resultsSubdir = v;
                default -> { /* ignore unknown keys */ }
            }
        }
        return c;
    }

    // 2026-07-09 consolidation: tag() used to compare each field against its own hand-copied
    // literal (DEFAULT_P_U, bare numbers like `!= 0.25`, `!= "cumulative"`...) — a *third* copy of
    // every default, next to the field initializer above and the Const.java literal it used to
    // mirror. Those three copies drifted in practice (e.g. repostProb's field default moved to 0.1
    // while tag() still compared against the old 0.25, silently mislabeling every default run as
    // non-default). DEFAULTS is a single plain instance built from the field initializers
    // themselves, so tag() below has exactly one thing to compare against and cannot drift from
    // the fields it's describing.
    private static final ExperimentConfig DEFAULTS = new ExperimentConfig();

    /** R15: resolved network seed (sentinel = fall back to the run seed). */
    public int resolvedNetSeed() {
        return (netSeed == Integer.MIN_VALUE) ? seed : netSeed;
    }

    // 2026-07-28: optional experiment-grouping subfolder under results/ (e.g.
    // "2026-07-28_removehub-mega-tier") -- lets a batch of runs land pre-sorted instead of all
    // 600+ run_<seed>_<tag> folders sitting flat in results/, which was making the folder too
    // heavy to browse/load (dashboard included). Empty by default = unchanged prior behavior.
    // dashboard/core.py's result_dir() glob was widened to results/**/run_<seed>_* to match.
    public String resultsSubdir = "";

    /** R20: per-run output folder (was Const.RESULT_FOLDER_PATH, set globally in main). */
    public String resultFolder() {
        String prefix = resultsSubdir.isBlank() ? "" : resultsSubdir + "/";
        return "results/" + prefix + "run_" + seed + "_" + tag() + "/";
    }

    /** Compact, filesystem-safe tag identifying this configuration. */
    public String tag() {
        String t = "ext-" + extreme + "_nneutral-" + nNeutral + "_size-" + sizeStrategy + "_ch-" + channel;
        // 2026-07-10: tag() now follows one rule everywhere, with no exceptions — tag a field iff
        // it differs from DEFAULTS, full stop. It used to special-case a few flags to "always tag
        // when active" (feed knobs when alpha>0, "_norelay"/"_nohost" whenever relay/hostility were
        // off) under the assumption that state was the non-default one; once the defaults
        // themselves flipped (relay/hostility off, feed algo on), those checks started tagging
        // every default run instead of every non-default one. `h` is still only shown alongside
        // `alpha` when alpha>0 (h is meaningless/dead once the For-You feed is off).
        if (feedAlgoShare != DEFAULTS.feedAlgoShare || feedHopH != DEFAULTS.feedHopH
                || !feedDecayMode.equals(DEFAULTS.feedDecayMode) || feedDecayLambda != DEFAULTS.feedDecayLambda) {
            t += "_a-" + String.format("%.2f", feedAlgoShare);
            if (feedAlgoShare > 0.0) {
                t += "_h-" + feedHopH;
                // decay mode/lambda are meaningless once alpha=0 (For-You off), same nesting as h.
                if (!feedDecayMode.equals(DEFAULTS.feedDecayMode)) t += "_decay-" + feedDecayMode;
                if (!feedDecayMode.equals("hard") && feedDecayLambda != DEFAULTS.feedDecayLambda) {
                    t += "_lam-" + String.format("%.2f", feedDecayLambda);
                }
            }
        }
        if (feedTimeDecayTau != DEFAULTS.feedTimeDecayTau) t += "_tdtau-" + String.format("%.1f", feedTimeDecayTau);
        if (pU != DEFAULTS.pU) {
            t += "_pu-" + String.format("%.4f", pU);
        }
        if (maxFollowCapacity != DEFAULTS.maxFollowCapacity) {
            t += "_maxf-" + (int) maxFollowCapacity;
        }
        if (bcDecRate != DEFAULTS.bcDecRate) {
            t += "_bcdec-" + String.format("%.4f", bcDecRate);
        }
        if (bcRecoveryRate != DEFAULTS.bcRecoveryRate) {
            t += "_bcrecovery-" + String.format("%.4f", bcRecoveryRate);
        }
        if (bcFloor != DEFAULTS.bcFloor) {
            t += "_bcfloor-" + String.format("%.4f", bcFloor);
        }
        if (bcCeiling != DEFAULTS.bcCeiling) {
            t += "_bcceil-" + String.format("%.4f", bcCeiling);
        }
        if (bcInit != DEFAULTS.bcInit) {
            t += "_bcinit-" + String.format("%.4f", bcInit);
        }
        if (vocalComfortRadius != DEFAULTS.vocalComfortRadius) {
            t += "_vcr-" + String.format("%.4f", vocalComfortRadius);
        }
        if (relayEnabled != DEFAULTS.relayEnabled) {
            t += relayEnabled ? "_relay" : "_norelay";
        }
        if (!coupleRelayDistortion) {
            t += "_relaystr-" + String.format("%.2f", relayDistortionStrength);
        }
        if (outOfBCRepostProb != DEFAULTS.outOfBCRepostProb) {
            t += "_outofbcprob-" + String.format("%.3f", outOfBCRepostProb);
        }
        if (initOpinionClip) {
            t += "_initop-clip";
        }
        if (!initOpinionDist.equals(DEFAULTS.initOpinionDist)) {
            t += "_initdist-" + initOpinionDist;
        }
        if (netSeed != Integer.MIN_VALUE && netSeed != seed) {
            t += "_nseed-" + netSeed;
        }
        if (!networkType.equals(DEFAULTS.networkType)) {
            t += "_nw-" + networkType;
        }
        // 2026-07-09 fix: DC-SBM structural params were entirely untagged, so e.g. two runs at the
        // same seed differing only in sbm_pout produced IDENTICAL folder names — the second run's
        // R26 "abort if exists" guard silently aborted it, an OAT-sweep collision found the hard
        // way. Tag whenever non-default so distinct structural configs always get distinct folders.
        if (sbmK != DEFAULTS.sbmK) t += "_sbmk-" + sbmK;
        if (sbmPin != DEFAULTS.sbmPin) t += "_sbmpin-" + String.format("%.4f", sbmPin);
        if (sbmPout != DEFAULTS.sbmPout) t += "_sbmpout-" + String.format("%.4f", sbmPout);
        if (sbmGamma != DEFAULTS.sbmGamma) t += "_sbmgamma-" + String.format("%.2f", sbmGamma);
        if (sbmDeg != DEFAULTS.sbmDeg) t += "_sbmdeg-" + sbmDeg;
        if (hkM != DEFAULTS.hkM) t += "_hkm-" + hkM;
        if (hkA != DEFAULTS.hkA) t += "_hka-" + hkA;
        if (hkPt != DEFAULTS.hkPt) t += "_hkpt-" + String.format("%.2f", hkPt);
        // Phase 2-4 knobs: tag only when non-default so legacy folder names are unchanged.
        if (repostProb != DEFAULTS.repostProb) t += "_rp-" + String.format("%.3f", repostProb);
        if (!stubDist.equals(DEFAULTS.stubDist)) t += "_stub-" + stubDist + String.format("-%.2f-%.2f", stubMin, stubMax);
        // 2026-07-09 fix: was `evictBeta >= 0`, written when the legacy/default value was -1 (any
        // non-negative value was by definition non-default). The default has since moved to 1
        // (still >= 0), so that check no longer means "non-default" — it now tags every default
        // run. Compare against DEFAULTS like everything else instead of re-deriving "default" from
        // a sign check.
        if (evictBeta != DEFAULTS.evictBeta) t += "_eb-" + String.format("%.2f", evictBeta);
        if (!initPrune.equals(DEFAULTS.initPrune)) t += "_prune-" + initPrune;
        if (!velMode.equals(DEFAULTS.velMode)) t += "_vm-" + velMode;
        if (!relAttrib.equals(DEFAULTS.relAttrib)) t += "_attr-" + relAttrib;
        if (n != DEFAULTS.n) t += "_n-" + n;
        if (steps != DEFAULTS.steps) t += "_st-" + steps;
        if (feedCapacity != DEFAULTS.feedCapacity) t += "_fc-" + feedCapacity;
        if (followProb != DEFAULTS.followProb) t += "_folp-" + String.format("%.3f", followProb);
        if (initialPostProb != DEFAULTS.initialPostProb) t += "_ipp-" + String.format("%.3f", initialPostProb);
        if (maxPostProb != DEFAULTS.maxPostProb) t += "_mxpp-" + String.format("%.3f", maxPostProb);
        if (minPostProb != DEFAULTS.minPostProb) t += "_mnpp-" + String.format("%.3f", minPostProb);
        if (postProbRelaxRate != DEFAULTS.postProbRelaxRate) t += "_ppeta-" + String.format("%.4f", postProbRelaxRate);
        if (neutralBandHalfWidth != DEFAULTS.neutralBandHalfWidth) t += "_neutband-" + String.format("%.3f", neutralBandHalfWidth);
        if (accessProb != DEFAULTS.accessProb) t += "_ap-" + String.format("%.4f", accessProb);
        return t;
    }
}
