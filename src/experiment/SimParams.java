package experiment;

/**
 * R20 (docs/report/2026-07-07-model-revision-requirements.md): immutable, instance-scoped runtime
 * parameters, replacing the mutable {@code public static} fields on {@code Const} that {@code main}
 * used to overwrite per run. Built once from an {@link ExperimentConfig}; passed by reference into
 * Agent, AdminOptim, and OpinionDynamics (one shared pointer, no copying).
 *
 * True physical constants (bin counts, feed capacity, initial trait means, folder layout strings)
 * remain {@code final} on {@code Const}.
 */
public record SimParams(
        int n,                  // R17: agent count
        double feedAlgoShare,   // alpha: For-You share of the feed
        int feedHopH,           // h: For-You reach in hops (<=0 = global), also the BFS depth cap
        String feedDecayMode,   // hard|exp|inverse -- see ExperimentConfig.feedDecayMode
        double feedDecayLambda, // decay steepness; 0 = no decay in any mode
        double feedTimeDecayTau, // optional extra exp(-age/tau) dampener on velocity score; 0=off
        double bcRecoveryRate,  // mean-reversion rate toward bcInit, content-independent (2026-07-18)
        double pU,              // P_u: unfollow probability (phase knob)
        double maxFollowCapacity,
        boolean relayEnabled,              // diagnostic master switch: false = verbatim repost, no reattribution
        boolean coupleRelayDistortion,     // relay distortion: couple to stubbornness (true) or explicit (false)
        double relayDistortionStrength,    // only used when coupleRelayDistortion=false
        double outOfBCRepostProb,          // out-of-bc repost rate; repost is always bc-gated (Agent.repost())
        double bcDecRate,       // tolerance decline rate
        double bcFloor,         // dynamic-bc clamp floor (sweepable; see Const.VOCAL_COMFORT_RADIUS)
        double bcCeiling,       // dynamic-bc clamp ceiling
        double bcInit,          // bc's initial value; decoupled from bcCeiling (2026-07-14)
        double vocalComfortRadius, // fixed comfort window for postProb (2026-07-19, was Const.VOCAL_COMFORT_RADIUS)
        boolean initOpinionClip,// true = legacy clip; false = truncated resampling
        String initOpinionDist, // gaussian|empirical (2026-07-21, Const.EMPIRICAL_OPINION_BIN_COUNTS)
        int assertInterval,     // invariant-check cadence in steps
        // ---- Phase 2-4 ----
        double repostProb,      // R6
        String stubDist,        // R13: const|uniform
        double stubMin,
        double stubMax,
        double evictBeta,       // R9: <0 legacy argmax; >=0 softmax temperature
        String velMode,         // R11: cumulative|windowed
        String relAttrib,       // R10: original|reposter
        // ---- Tier-D robustness knobs (2026-07-09), migrated off Const per R20's own convention ----
        int feedCapacity,       // S: max posts delivered per feed per step
        double followProb,      // per-step probability the follow() action executes
        double initialPostProb,
        double maxPostProb,
        double minPostProb,
        double postProbRelaxRate, // eta: postProb's relaxation rate toward its comfort-rate target (2026-07-23; was comfortPpFactor)
        double neutralBandHalfWidth, // |opinion| below this excluded from sign-based camp metrics
        double accessProb,      // per-step probability an agent's whole action set (incl. the
                                 // opinion update) executes; the model's global timescale knob
        java.util.Set<Integer> algoExcludeIds, // 2026-07-26: excluded from the For-You velocity
                                 // candidate pool only (AdminOptim.AdminFeedback); organic/chrono
                                 // reach to these agents is untouched
        String resultFolder) {

    public static SimParams from(ExperimentConfig c) {
        return new SimParams(
                c.n,
                c.feedAlgoShare,
                c.feedHopH,
                c.feedDecayMode,
                c.feedDecayLambda,
                c.feedTimeDecayTau,
                c.bcRecoveryRate,
                c.pU,
                c.maxFollowCapacity,
                c.relayEnabled,
                c.coupleRelayDistortion,
                c.relayDistortionStrength,
                c.outOfBCRepostProb,
                c.bcDecRate,
                c.bcFloor,
                c.bcCeiling,
                c.bcInit,
                c.vocalComfortRadius,
                c.initOpinionClip,
                c.initOpinionDist,
                Math.max(1, c.assertInterval),
                c.repostProb,
                c.stubDist,
                c.stubMin,
                c.stubMax,
                c.evictBeta,
                c.velMode,
                c.relAttrib,
                c.feedCapacity,
                c.followProb,
                c.initialPostProb,
                c.maxPostProb,
                c.minPostProb,
                c.postProbRelaxRate,
                c.neutralBandHalfWidth,
                c.accessProb,
                c.algoExcludeIds,
                c.resultFolder());
    }
}
