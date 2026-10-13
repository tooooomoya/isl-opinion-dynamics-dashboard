package experiment;

/**
 * Immutable, instance-scoped runtime parameters built once from an {@link ExperimentConfig} and
 * shared by reference with Agent, AdminOptim and OpinionDynamics. (Attention-economy branch: the
 * bounded-confidence, follow/unfollow, comfort and reshare-distortion parameters of the inherited
 * model are gone.)
 */
public record SimParams(
        int n,                   // agent count
        // ---- feed / screen ----
        double trendShare,       // Trend (popularity) share of the feed
        int trendHopH,           // Trend reach in hops (<=0 = global), also the BFS depth cap
        double foryouShare,      // For You (perspective similarity) share of the feed
        int foryouHopH,          // For You reach in hops (<=0 = global)
        double foryouBeta,       // For You sharpness: weight exp(-beta |Xhat - X_post|)
        boolean foryouProfile,   // score against the estimated X (true) or the true X (control)
        double rhoLike,          // estimate update weight on a like
        double rhoReshare,       // estimate update weight on a reshare
        String feedDecayMode,    // hard|exp|inverse
        double feedDecayLambda,  // decay steepness; 0 = no decay in any mode
        double feedTimeDecayTau, // optional exp(-age/tau) dampener on velocity score; 0=off
        String velMode,          // cumulative|windowed
        int feedCapacity,        // S: max candidate posts delivered per visit
        double accessProb,       // per-step probability an agent visits
        java.util.Set<Integer> algoExcludeIds,
        // ---- values ----
        String initOpinionDist,  // uniform|gaussian
        double mu,               // drift weight toward the feed mean (0 = X fixed)
        double neutralBandHalfWidth,
        // ---- attention / death ----
        double betaH,            // homophily pull for the feed pick and the rewire target
        int deadAfter,           // L: steps after the last like/reshare before a post dies
        double lRef,             // scale of the slow (log) recognition term
        double recogLambda,      // scale of the fast (exponential) recognition term
        double recogMix,         // weight of the fast term in recognition
        double wFit,             // reward weight of identity fit:  r = wFit * I + wRec * L
        double wRec,             // reward weight of recognition
        // ---- Q-learning ----
        double qEta,
        double qGamma,
        double qTau,
        double qInit,
        double qEps,              // exploration floor (uniform random action with this probability)
        boolean rewireOn,         // false = static follow network: rewire is not an available action
        double iEdgeLo, double iEdgeHi,   // identity-fit state-bin edges
        double lEdgeLo, double lEdgeHi,   // recognition state-bin edges
        int assertInterval,
        String resultFolder) {

    public static SimParams from(ExperimentConfig c) {
        if (c.trendShare < 0 || c.foryouShare < 0 || c.trendShare + c.foryouShare > 1.0 + 1e-9)
            throw new IllegalArgumentException("trend_share + foryou_share must be within [0,1] (chrono takes the rest)");
        return new SimParams(
                c.n,
                c.trendShare, c.trendHopH, c.foryouShare, c.foryouHopH, c.foryouBeta, c.foryouProfile, c.rhoLike, c.rhoReshare, c.feedDecayMode, c.feedDecayLambda, c.feedTimeDecayTau,
                c.velMode, c.feedCapacity, c.accessProb, c.algoExcludeIds,
                c.initOpinionDist, c.mu, c.neutralBandHalfWidth,
                c.betaH, c.deadAfter, c.lRef, c.recogLambda, c.recogMix, c.wFit, c.wRec,
                c.qEta, c.qGamma, c.qTau, c.qInit, c.qEps, c.rewireOn,
                c.iEdgeLo, c.iEdgeHi, c.lEdgeLo, c.lEdgeHi,
                Math.max(1, c.assertInterval),
                c.resultFolder());
    }
}
