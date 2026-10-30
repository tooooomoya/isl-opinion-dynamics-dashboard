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
        boolean trendCountLikes, // Trend velocity counts likes as well as reshares
        boolean trendTieRandom,  // equal Trend scores are ordered at random (false: creation order, oldest first)
        int feedCapacity,        // S: max candidate posts delivered per visit
        double accessProb,       // per-step probability an agent visits
        java.util.Set<Integer> algoExcludeIds,
        // ---- values ----
        String initOpinionDist,  // uniform|gaussian|empirical (unique-person survey weights)
        double initSd,           // sd of the gaussian start (truncated to [-1,1])
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
        boolean creditPost,      // true: likes are credited to the action that made the post (delayed), not the stock
        int creditHorizon,
        boolean fitRelative,     // true: identity fit minus its expectation under a random feed (state and reward)       // steps after creation during which a post's likes count for its creating action
        // ---- Q-learning ----
        double qEta,
        double qGamma,
        boolean bandit,           // true: single state and no bootstrapping (qGamma ignored)
        double qTau,
        double qInit,
        double qEps,              // exploration floor (uniform random action with this probability)
        boolean rewireOn,         // false = static follow network: rewire is not an available action
        double costPost,          // reward cost paid for a post (subtracted from the reward its decision earns)
        double costReshare,       // reward cost paid for a reshare (typically smaller than costPost)
        boolean rewireGate,       // true: a rewire swaps only if the candidate is strictly closer than the oldest followee; false: it always swaps
        double postNoise,         // sd of the Gaussian noise on the X expressed in an original post (0 = exact); > 0 also makes rewire judge agents by their posts
        int notifyMax,            // > 0: reshares of my own posts join my candidate pool (hop-exempt); 0 = off
        double costRewire,        // reward cost paid for a rewire decision (whether or not the swap is executed)
        double foryouHopLambda,   // For You hop term exp(-lambda (d-1)) multiplied into the similarity weight (< 0: legacy feed_decay machinery)
        int foryouCandMax,        // For You: random sample of at most this many hop-filtered candidates per feed before weighting (0 = all)
        boolean fitBaselineAnalytic, // relative fit: baseline 1 - (1 + x^2)/4 (random feed, X uniform on [-1,1]) instead of the empirical mean similarity
        boolean likeGateNoop,     // like range gate: false = out-of-range posts are not candidates; true = a like whose drawn post is out of range does nothing (counted as gated)
        double likeMaxDist,       // absolute like range: a post is likeable only if |x_i - x_post| <= this (>=2 = no limit)
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
                c.velMode, c.trendCount.equals("both"), c.trendTie.equals("random"), c.feedCapacity, c.accessProb, c.algoExcludeIds,
                c.initOpinionDist, c.initSd, c.mu, c.neutralBandHalfWidth,
                c.betaH, c.deadAfter, c.lRef, c.recogLambda, c.recogMix, c.wFit, c.wRec, c.credit.equals("post"), c.creditHorizon, c.fitMode.equals("relative"),
                c.qEta, c.qGamma, c.learner.equals("bandit"), c.qTau, c.qInit, c.qEps, c.rewireOn, c.costPost, c.costReshare, c.rewireGate, c.postNoise, c.notifyMax, c.costRewire, c.foryouHopLambda, c.foryouCandMax, c.fitBaseline.equals("analytic"), c.likeGate.equals("noop"), c.likeMaxDist,
                c.iEdgeLo, c.iEdgeHi, c.lEdgeLo, c.lEdgeHi,
                Math.max(1, c.assertInterval),
                c.resultFolder());
    }
}
