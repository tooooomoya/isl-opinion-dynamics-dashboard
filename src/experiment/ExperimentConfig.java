package experiment;

import agent.Agent;

/**
 * Configuration for a single simulation run of the attention-economy model (branch
 * attention-economy; spec: docs/report/2026-10-12-attention-economy-model-spec-and-code-change-plan.md,
 * rev 9). Parsed from CLI args as space-separated {@code key=value} tokens, e.g.
 *   seed=0 beta_h=3 q_eta=0.1 dead_after=50
 * A bare numeric first token is also accepted as the seed. Unknown keys are silently ignored, so
 * scripts from the inherited opinion-dynamics model still parse (their removed knobs are inert).
 *
 * Mechanisms removed on this branch (their knobs are gone): bounded confidence (all roles), block,
 * follow/unfollow/eviction, reshare distortion, comfort-driven posting rate, per-agent stubbornness
 * (replaced by the single drift weight {@code mu}).
 */
public class ExperimentConfig {
    public enum ExtremeMode { NONE, SYM, ASYM }
    public enum SizeStrategy { LARGEST, SMALLEST }

    // ---- Run identity ----
    public int seed = 0;
    public int netSeed = Integer.MIN_VALUE; // sentinel = fall back to `seed` (see resolvedNetSeed)

    // ---- Intervention design (inherited hub machinery; out of scope for the attention-economy
    //      study, kept so InterventionSetup still compiles/runs) ----
    public ExtremeMode extreme = ExtremeMode.NONE;
    public int nNeutral = 0;
    public SizeStrategy sizeStrategy = SizeStrategy.LARGEST;
    public Agent.ChannelMode channel = Agent.ChannelMode.BOTH;
    public int poolTopK = 15;
    public double asymDirection = 1.0;

    // ---- Network structure & generation (studied factor: the network) ----
    public String networkType = "ws"; // dcsbm|ba|hk|ws|dms|cnn|lfr|random|read (branch default: ws, no initial hubs)
    public int wsOut = 15;               // WS: out-degree of every agent at t=0 (edges to the next wsOut agents on a directed ring)
    public int baOut = 15;               // dba start: out-degree of every agent
    public double baAttract = 15.0;      // dba start: attachment ~ (in-degree + baAttract); 0 = strongest hubs, large = uniform
    public int homOut = 15;              // homophily start: out-degree of every agent
    public double homGamma = 2.0;        // homophily start: follow weight exp(-homGamma*|x_i-x_j|); 0 = uniform random
    public double randomP = 0.015;       // random (directed Erdos-Renyi) start: P(i follows j); 0.015 gives mean out-degree ~15 at n=1000
    public double wsBeta = 0.1;          // WS: probability each ring edge is rewired to a random target
    public int sbmK = 4;
    public double sbmPin = 0.08;
    public double sbmPout = 0.002;
    public double sbmGamma = 2.3;
    public int sbmDeg = 50;
    public String readPath = "results/temp/step_1000.gexf";
    public int hkM = 15;       // out-edges per new node (= each agent's fixed out-degree under rewire)
    public int hkA = 4;
    public double hkPt = 0.05;

    // ---- Feed / algorithmic exposure (studied factor: the screen) ----
    // Three streams fill the feed: chrono (followees' posts, the remainder), Trend (popularity: reshare
    // velocity, opinion-blind) and For You (perspective similarity to the platform's estimate of the reader's X).
    public double trendShare = 0.7;  // Trend share of the feed (keys: trend_share, alias alpha)
    public int trendHopH = 4;        // Trend reach in hops (keys: trend_hop, alias hop); <=0 = global
    public double foryouShare = 0.0; // For You share of the feed (0 = off)
    public int foryouHopH = 4;       // For You reach in hops; <=0 = global (X-matching only, network ignored)
    public double foryouBeta = 3.0;  // For You sharpness: candidate weight exp(-foryouBeta*|Xhat_i - X_post|)
    public boolean foryouProfile = true; // true: score against the platform's estimate Xhat_i; false: the true X_i (control)
    public double rhoLike = 0.05;    // Xhat update weight on a like:    Xhat <- (1-rho) Xhat + rho X_post
    public double rhoReshare = 0.10; // Xhat update weight on a reshare
    public String feedDecayMode = "exp"; // hard|exp|inverse
    public double feedDecayLambda = 0.11;
    public String velMode = "windowed";  // cumulative|windowed
    public double feedTimeDecayTau = 30.0;
    public int feedCapacity = 10;        // candidate posts delivered per visit
    public double accessProb = 0.1;      // chance an agent visits at a step; sets time between decisions

    // ---- Values ----
    public String initOpinionDist = "uniform"; // uniform|gaussian ; X in [-1,1], d = 1
    public double mu = 0.0;                    // drift weight toward the feed mean; 0 = X fixed (baseline)
    public double neutralBandHalfWidth = 0.2;  // analysis-only: sign-camp metrics exclude |x| below this

    // ---- Attention, death, action choice ----
    public double betaH = 3.0;     // homophily pull: P(pick post j) ~ exp(-betaH * |x_i - x_j|), also rewire target
    public int deadAfter = 50;     // L: a post dies this many steps after its last like/reshare
    public double lRef = 300.0;    // scale of the slow (log) recognition term: likes at which it reaches 1
    // recognition = recogMix * (1 - exp(-likes / recogLambda)) + (1 - recogMix) * min(1, ln(1+likes) / ln(1+lRef))
    // The fast term saturates after a few likes, so the first likes are worth a lot to peripheral agents; the slow
    // log term keeps rising to lRef, so influencers still differ from one another.
    public double recogLambda = 2.0;
    public double recogMix = 0.5;
    public double wFit = 1.0;      // reward = wFit * identityFit + wRec * recognition (equal weights = the original reward)
    public double wRec = 1.0;
    // credit = "stock": recognition (likes on all my surviving posts) is part of every visit's reward (original).
    // credit = "post": the visit reward is wFit*I only; the likes a POST/RESHARE's own new post collects within
    // creditHorizon steps are credited back to the (state, action) that made it, as a delayed update.
    public String credit = "stock";
    public int creditHorizon = 50;
    // fit_mode = "raw": the identity fit is the mean similarity of the feed. fit_mode = "relative": the agent's expected fit
    // under a random feed (mean similarity to all agents) is subtracted, for both the state and the reward.
    public String fitMode = "raw";

    // ---- Q-learning (stateless action values over a 3x3 state; spec rev 7, section 10) ----
    public double qEta = 0.1;      // learning rate
    public double qGamma = 0.9;    // discount
    // learner = "q": Q(s,a) over the 3x3 state with bootstrapping. learner = "bandit": one state, no bootstrapping (gamma=0):
    // Q(a) += eta * (r - Q(a)), a plain stochastic multi-armed bandit over {post, like, reshare, rewire}.
    public String learner = "q";
    public double qTau = 0.5;      // softmax temperature (exploration)
    public double qInit = 0.0;     // equal start for all (state, action) pairs
    public double costPost = 0.0;    // reward cost of posting (cost_post)
    public double costReshare = 0.0; // reward cost of resharing (cost_reshare)
    public boolean rewireGate = true;  // rewire_gate: false = always swap the oldest followee for the drawn candidate (no similarity check)
    public double postNoise = 0.0;     // post_noise: x_post = clip(x_i + N(0, post_noise^2), -1, 1); > 0 also switches rewire to observed (post-based) opinions
    public int notifyMax = 0;          // notify_original (>0 = on): reshares of my own posts join my candidate pool, hop-exempt (0 = off)
    public double reshareAlpha = 0.0; // likes on a reshare: alpha to the original's author, 1-alpha to the resharer (reshare_alpha)
    public double costRewire = 0.0;  // reward cost of a rewire decision (cost_rewire)
    public double foryouHopLambda = -1.0; // foryou_hop_lambda: For You score = similarity x exp(-lambda (hop-1)); < 0 = legacy feed_decay_* machinery
    public int startDeg = 0;            // start_deg: force the start network to exactly n x start_deg directed edges (mean degree), 0 = as generated
    public int metricsHeavyEvery = 1;   // metrics_heavy_every: recompute network-wide step metrics every k steps (carry forward in between)
    public int foryouCandMax = 0;      // foryou_cand_max: cap on the For You candidate sample per feed (0 = no cap)
    public String fitBaseline = "empirical"; // fit_baseline: empirical | analytic (relative fit only)
    public String likeGate = "filter"; // like_gate: filter (out-of-range posts are not like candidates) | noop (the like is chosen, the drawn post is out of range => nothing happens, counted)
    public double likeMaxDist = 2.0; // like only posts with |x_i - x_post| <= this (absolute range; 2 = unrestricted)
    public boolean rewireOn = true; // false = static network (rewire not available as an action)
    public double qEps = 0.05;     // exploration floor: with this probability pick uniformly among the available actions
    // state bin edges on [0,1] for identity fit (i*) and recognition (l*): low < lo <= mid < hi <= high.
    // Typical identity fit under random mixing is ~2/3, so fixed thirds are a placeholder to be set
    // from a pilot distribution (spec 12.2).
    public double iEdgeLo = 1.0 / 3.0, iEdgeHi = 2.0 / 3.0;
    public double lEdgeLo = 1.0 / 3.0, lEdgeHi = 2.0 / 3.0;

    // ---- Scale, duration & logging ----
    public int n = 1000;
    public int steps = 40000;
    public int interactionWindow = 5000;
    public int assertInterval = 1000;
    public boolean logRepostCascade = true;
    public boolean logGexf = true;
    public boolean logPostLifespan = true;
    public boolean force = false;
    public String resultsSubdir = "";

    // ---- ID-list manipulations (inherited; used by InterventionSetup/OpinionDynamics) ----
    public java.util.Set<Integer> algoExcludeIds = java.util.Set.of();
    public java.util.Set<Integer> silentUntilIds = java.util.Set.of();
    public int activationStep = 0;
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
                case "net_seed" -> c.netSeed = Integer.parseInt(v);
                case "extreme" -> c.extreme = ExtremeMode.valueOf(v.toUpperCase());
                case "n_neutral" -> c.nNeutral = Integer.parseInt(v);
                case "size" -> c.sizeStrategy = SizeStrategy.valueOf(v.toUpperCase());
                case "channel" -> c.channel = Agent.ChannelMode.valueOf(v.toUpperCase());
                case "topk" -> c.poolTopK = Integer.parseInt(v);
                case "asym_dir" -> c.asymDirection = Double.parseDouble(v);
                case "alpha", "trend_share" -> c.trendShare = Double.parseDouble(v);
                case "hop", "trend_hop" -> c.trendHopH = Integer.parseInt(v);
                case "feed_decay_mode" -> c.feedDecayMode = v.toLowerCase();
                case "feed_decay_lambda" -> c.feedDecayLambda = Double.parseDouble(v);
                case "feed_time_decay_tau" -> c.feedTimeDecayTau = Double.parseDouble(v);
                case "vel_mode" -> c.velMode = v.toLowerCase();
                case "feed_capacity" -> c.feedCapacity = Integer.parseInt(v);
                case "access_prob" -> c.accessProb = Double.parseDouble(v);
                case "init_dist" -> c.initOpinionDist = v.toLowerCase();
                case "mu" -> c.mu = Double.parseDouble(v);
                case "neutral_band" -> c.neutralBandHalfWidth = Double.parseDouble(v);
                case "beta_h" -> c.betaH = Double.parseDouble(v);
                case "dead_after" -> c.deadAfter = Integer.parseInt(v);
                case "l_ref" -> c.lRef = Double.parseDouble(v);
                case "recog_lambda" -> c.recogLambda = Double.parseDouble(v);
                case "w_fit" -> c.wFit = Double.parseDouble(v);
                case "w_rec" -> c.wRec = Double.parseDouble(v);
                case "fit_mode" -> c.fitMode = v.toLowerCase();
                case "credit" -> c.credit = v.toLowerCase();
                case "credit_horizon" -> c.creditHorizon = Integer.parseInt(v);
                case "recog_mix" -> c.recogMix = Double.parseDouble(v);
                case "q_eta" -> c.qEta = Double.parseDouble(v);
                case "q_gamma" -> c.qGamma = Double.parseDouble(v);
                case "learner" -> c.learner = v.toLowerCase();
                case "q_tau" -> c.qTau = Double.parseDouble(v);
                case "cost_post" -> c.costPost = Double.parseDouble(v);
                case "cost_reshare" -> c.costReshare = Double.parseDouble(v);
                case "rewire_gate" -> c.rewireGate = Boolean.parseBoolean(v);
                case "post_noise" -> c.postNoise = Double.parseDouble(v);
                case "notify_original" -> c.notifyMax = Integer.parseInt(v);
                case "reshare_alpha" -> c.reshareAlpha = Double.parseDouble(v);
                case "cost_rewire" -> c.costRewire = Double.parseDouble(v);
                case "foryou_hop_lambda" -> c.foryouHopLambda = Double.parseDouble(v);
                case "start_deg" -> c.startDeg = Integer.parseInt(v);
                case "metrics_heavy_every" -> c.metricsHeavyEvery = Integer.parseInt(v);
                case "foryou_cand_max" -> c.foryouCandMax = Integer.parseInt(v);
                case "fit_baseline" -> c.fitBaseline = v.toLowerCase();
                case "like_gate" -> c.likeGate = v.toLowerCase();
                case "like_max_dist" -> c.likeMaxDist = Double.parseDouble(v);
                case "q_init" -> c.qInit = Double.parseDouble(v);
                case "foryou_share" -> c.foryouShare = Double.parseDouble(v);
                case "foryou_hop" -> c.foryouHopH = Integer.parseInt(v);
                case "fy_beta" -> c.foryouBeta = Double.parseDouble(v);
                case "fy_profile" -> c.foryouProfile = Boolean.parseBoolean(v);
                case "rho_l" -> c.rhoLike = Double.parseDouble(v);
                case "rho_r" -> c.rhoReshare = Double.parseDouble(v);
                case "rewire" -> c.rewireOn = Boolean.parseBoolean(v);
                case "q_eps" -> c.qEps = Double.parseDouble(v);
                case "i_edge_lo" -> c.iEdgeLo = Double.parseDouble(v);
                case "i_edge_hi" -> c.iEdgeHi = Double.parseDouble(v);
                case "l_edge_lo" -> c.lEdgeLo = Double.parseDouble(v);
                case "l_edge_hi" -> c.lEdgeHi = Double.parseDouble(v);
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
                case "ws_out" -> c.wsOut = Integer.parseInt(v);
                case "ws_beta" -> c.wsBeta = Double.parseDouble(v);
                case "random_p" -> c.randomP = Double.parseDouble(v);
                case "ba_out" -> c.baOut = Integer.parseInt(v);
                case "ba_attract" -> c.baAttract = Double.parseDouble(v);
                case "hom_out" -> c.homOut = Integer.parseInt(v);
                case "hom_gamma" -> c.homGamma = Double.parseDouble(v);
                case "interaction_window" -> c.interactionWindow = Integer.parseInt(v);
                case "n" -> c.n = Integer.parseInt(v);
                case "steps" -> c.steps = Integer.parseInt(v);
                case "log_repost_cascade" -> c.logRepostCascade = Boolean.parseBoolean(v);
                case "log_gexf" -> c.logGexf = Boolean.parseBoolean(v);
                case "log_post_lifespan" -> c.logPostLifespan = Boolean.parseBoolean(v);
                case "force" -> c.force = Boolean.parseBoolean(v);
                case "results_subdir" -> c.resultsSubdir = v;
                case "algo_exclude_ids" -> c.algoExcludeIds = parseIdSet(v);
                case "pin_opinion_ids" -> c.pinOpinionIds = parseIdValueMap(v);
                case "silent_until_ids" -> c.silentUntilIds = parseIdSet(v);
                case "activation_step" -> c.activationStep = Integer.parseInt(v);
                default -> { /* ignore unknown keys */ }
            }
        }
        return c;
    }

    // DEFAULTS is a plain instance built from the field initializers, so tag() has exactly one
    // thing to compare against and cannot drift from the fields it describes.
    private static final ExperimentConfig DEFAULTS = new ExperimentConfig();

    /** Resolved network seed (sentinel = fall back to the run seed). */
    public int resolvedNetSeed() {
        return (netSeed == Integer.MIN_VALUE) ? seed : netSeed;
    }

    /** Per-run output folder. */
    public String resultFolder() {
        String prefix = resultsSubdir.isBlank() ? "" : resultsSubdir + "/";
        String t = tag();
        if (t.length() > 190) { // keep the folder name under the 255-char filesystem limit: truncate + hash of the full tag
            t = t.substring(0, 170) + "~" + String.format("%08x", t.hashCode());
        }
        return "results/" + prefix + "run_" + seed + "_" + t + "/";
    }

    /** Compact, filesystem-safe tag: a field is tagged iff it differs from DEFAULTS. */
    public String tag() {
        String t = "ext-" + extreme + "_nneutral-" + nNeutral + "_size-" + sizeStrategy + "_ch-" + channel;
        if (trendShare != DEFAULTS.trendShare || trendHopH != DEFAULTS.trendHopH
                || !feedDecayMode.equals(DEFAULTS.feedDecayMode) || feedDecayLambda != DEFAULTS.feedDecayLambda) {
            t += "_a-" + String.format("%.2f", trendShare);
            if (trendShare > 0.0) {
                t += "_h-" + trendHopH;
                if (!feedDecayMode.equals(DEFAULTS.feedDecayMode)) t += "_decay-" + feedDecayMode;
                if (!feedDecayMode.equals("hard") && feedDecayLambda != DEFAULTS.feedDecayLambda) {
                    t += "_lam-" + String.format("%.2f", feedDecayLambda);
                }
            }
        }
        if (foryouShare != DEFAULTS.foryouShare) {
            t += "_fy-" + String.format("%.2f", foryouShare) + "_fyh-" + foryouHopH;
            if (foryouBeta != DEFAULTS.foryouBeta) t += "_fyb-" + String.format("%.1f", foryouBeta);
            if (!foryouProfile) t += "_fytrue";
            if (rhoLike != DEFAULTS.rhoLike) t += "_rl-" + String.format("%.2f", rhoLike);
            if (rhoReshare != DEFAULTS.rhoReshare) t += "_rr-" + String.format("%.2f", rhoReshare);
        }
        if (feedTimeDecayTau != DEFAULTS.feedTimeDecayTau) t += "_tdtau-" + String.format("%.1f", feedTimeDecayTau);
        if (!initOpinionDist.equals(DEFAULTS.initOpinionDist)) t += "_initdist-" + initOpinionDist;
        if (mu != DEFAULTS.mu) t += "_mu-" + String.format("%.4f", mu);
        if (betaH != DEFAULTS.betaH) t += "_bh-" + String.format("%.2f", betaH);
        if (deadAfter != DEFAULTS.deadAfter) t += "_L-" + deadAfter;
        if (lRef != DEFAULTS.lRef) t += "_lref-" + String.format("%.0f", lRef);
        if (recogLambda != DEFAULTS.recogLambda) t += "_rlam-" + String.format("%.2f", recogLambda);
        if (wFit != DEFAULTS.wFit) t += "_wfit-" + String.format("%.2f", wFit);
        if (wRec != DEFAULTS.wRec) t += "_wrec-" + String.format("%.2f", wRec);
        if (!fitMode.equals(DEFAULTS.fitMode)) t += "_fit-" + fitMode;
        if (!credit.equals(DEFAULTS.credit)) t += "_credit-" + credit + "-" + creditHorizon;
        if (recogMix != DEFAULTS.recogMix) t += "_rmix-" + String.format("%.2f", recogMix);
        if (qEta != DEFAULTS.qEta) t += "_qeta-" + String.format("%.4f", qEta);
        if (rewireGate != DEFAULTS.rewireGate) t += "_gate-" + rewireGate;
        if (postNoise != DEFAULTS.postNoise) t += "_pn-" + String.format("%.2f", postNoise);
        if (notifyMax != DEFAULTS.notifyMax) t += "_nt-" + notifyMax;
        if (reshareAlpha != DEFAULTS.reshareAlpha) t += "_ra-" + String.format("%.2f", reshareAlpha);
        if (costPost != DEFAULTS.costPost || costReshare != DEFAULTS.costReshare || costRewire != DEFAULTS.costRewire) t += "_cost-" + String.format("%.2f", costPost) + "-" + String.format("%.2f", costReshare) + "-" + String.format("%.2f", costRewire);
        if (foryouHopLambda != DEFAULTS.foryouHopLambda) t += "_hl-" + String.format("%.2f", foryouHopLambda);
        if (startDeg != DEFAULTS.startDeg) t += "_sd-" + startDeg;
        if (foryouCandMax != DEFAULTS.foryouCandMax) t += "_cm-" + foryouCandMax;
        if (!fitBaseline.equals(DEFAULTS.fitBaseline)) t += "_fb-" + fitBaseline;
        if (!likeGate.equals(DEFAULTS.likeGate)) t += "_lg-" + likeGate;
        if (likeMaxDist != DEFAULTS.likeMaxDist) t += "_lmd-" + String.format("%.2f", likeMaxDist);
        if (!learner.equals(DEFAULTS.learner)) t += "_learner-" + learner;
        if (qGamma != DEFAULTS.qGamma) t += "_qgam-" + String.format("%.2f", qGamma);
        if (qTau != DEFAULTS.qTau) t += "_qtau-" + String.format("%.3f", qTau);
        if (qInit != DEFAULTS.qInit) t += "_qinit-" + String.format("%.2f", qInit);
        if (rewireOn != DEFAULTS.rewireOn) t += "_rewire-" + rewireOn;
        if (qEps != DEFAULTS.qEps) t += "_qeps-" + String.format("%.3f", qEps);
        if (iEdgeLo != DEFAULTS.iEdgeLo || iEdgeHi != DEFAULTS.iEdgeHi)
            t += "_iedge-" + String.format("%.2f-%.2f", iEdgeLo, iEdgeHi);
        if (lEdgeLo != DEFAULTS.lEdgeLo || lEdgeHi != DEFAULTS.lEdgeHi)
            t += "_ledge-" + String.format("%.2f-%.2f", lEdgeLo, lEdgeHi);
        if (netSeed != Integer.MIN_VALUE && netSeed != seed) t += "_nseed-" + netSeed;
        if (!networkType.equals(DEFAULTS.networkType)) t += "_nw-" + networkType;
        if (sbmK != DEFAULTS.sbmK) t += "_sbmk-" + sbmK;
        if (sbmPin != DEFAULTS.sbmPin) t += "_sbmpin-" + String.format("%.4f", sbmPin);
        if (sbmPout != DEFAULTS.sbmPout) t += "_sbmpout-" + String.format("%.4f", sbmPout);
        if (sbmGamma != DEFAULTS.sbmGamma) t += "_sbmgamma-" + String.format("%.2f", sbmGamma);
        if (sbmDeg != DEFAULTS.sbmDeg) t += "_sbmdeg-" + sbmDeg;
        if (wsOut != DEFAULTS.wsOut) t += "_wsout-" + wsOut;
        if (baOut != DEFAULTS.baOut) t += "_baout-" + baOut;
        if (baAttract != DEFAULTS.baAttract) t += "_baa-" + String.format("%.1f", baAttract);
        if (homOut != DEFAULTS.homOut) t += "_homout-" + homOut;
        if (homGamma != DEFAULTS.homGamma) t += "_homg-" + String.format("%.2f", homGamma);
        if (randomP != DEFAULTS.randomP) t += "_rp-" + String.format("%.4f", randomP);
        if (wsBeta != DEFAULTS.wsBeta) t += "_wsbeta-" + String.format("%.2f", wsBeta);
        if (hkM != DEFAULTS.hkM) t += "_hkm-" + hkM;
        if (hkA != DEFAULTS.hkA) t += "_hka-" + hkA;
        if (hkPt != DEFAULTS.hkPt) t += "_hkpt-" + String.format("%.2f", hkPt);
        if (!velMode.equals(DEFAULTS.velMode)) t += "_vm-" + velMode;
        if (n != DEFAULTS.n) t += "_n-" + n;
        if (steps != DEFAULTS.steps) t += "_st-" + steps;
        if (feedCapacity != DEFAULTS.feedCapacity) t += "_fc-" + feedCapacity;
        if (neutralBandHalfWidth != DEFAULTS.neutralBandHalfWidth) t += "_neutband-" + String.format("%.3f", neutralBandHalfWidth);
        if (accessProb != DEFAULTS.accessProb) t += "_ap-" + String.format("%.4f", accessProb);
        return t;
    }
}
