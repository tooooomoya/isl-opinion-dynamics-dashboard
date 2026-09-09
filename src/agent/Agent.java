package agent;

import admin.AdminOptim;
import constants.Const;
import experiment.SimParams;
import java.util.*;
import rand.randomGenerator;

public class Agent {
    // Activity-channel control for opinion-leader / hub manipulation (Exp A: repost-channel isolation).
    // Decouples the two ways a hub spreads information so their effects can be separated.
    public enum ChannelMode { BOTH, POST_ONLY, REPOST_ONLY, NONE }

    private int id;
    private double opinion;
    private double stubbornness;
    private double bc; // Bounded Confidence
    private double intrinsicOpinion;
    private final int NUM_OF_AGENTS; // R17: set from SimParams.n() in the constructor
    private int toPost; // % of posts at a step
    private int numOfPosts; // maximum % of posts that an agent can read at a step
    private int opinionClass;
    private PostCash postCash; // posts in feeds shall be selected from cash
    private double postProb;
    private List<Post> feed = new ArrayList<>(); // timeline
    // 2026-07-30: which rootPostIds this step's feed delivered via the algorithmic For-You stream
    // (set fresh each step by AdminOptim.AdminFeedback, before repost() runs later the same step --
    // chrono and For-You are dedup'd against each other by rootPostId there, so a root is never in
    // both, making this membership check unambiguous). Everything else in feed this step is chrono.
    private java.util.Set<Integer> forYouRootIds = java.util.Set.of();
    private double accessProb; // set from SimParams in the constructor; see getAccessProb/setAccessProb
    private boolean target = false; // for further simulation like using bots
    // 2026-08-06: hub-tier label for feed-composition mechanism analysis (docs/report/2026-08-02-
    // delayed-moderate-conduit-pilot.md HANDOFF). -1 = not a pinned hub. For pinned hubs, a FROZEN
    // snapshot of getOpinionClass() taken once at pin time (OpinionDynamics' pinNeutralIds/
    // pinOpinionIds setup loop) -- deliberately NOT re-derived from live opinion later, since pinned
    // hubs are NOT stubbornness=1 in the current L/M/P design (their opinion can drift after t=0),
    // so a live re-classification could silently relabel a hub mid-run. Matches the 5-bin convention
    // (bin 2 = "Neutral", bins 0/4 = extremes, 1/3 = "moderate") used throughout the analysis
    // scripts' camp_bin().
    private int hubTier = -1;
    private int timeStep;
    // R22: the follow graph is owned solely by AdminOptim; agents keep only their own block list.
    private final boolean[] blockedUserList; // R17: sized from NUM_OF_AGENTS in the constructor
    private boolean used; // whether agent uses platform or not
    private double repostProb;
    private boolean postEnabled = true;   // whether this agent broadcasts its own posts
    private boolean repostEnabled = true; // whether this agent emits reposts
    private static final int COMFORT_MEMORY_SIZE = 100;  // 直近何ステップを保持するか
    private Deque<Double> comfortHistory = new ArrayDeque<>();
    private final SimParams p; // R20: instance-scoped runtime params (was mutable Const statics)
    // R1: transient per-step behavioral-event counters, reset at the start of each action call and
    // read by OpinionDynamics after the call (lightweight event instrumentation, no EventLog object).
    private int lastReposts = 0;
    private int lastCrossReposts = 0;
    private int lastBlocks = 0;


    // constructor
    public Agent(int agentID, SimParams params) {
        this.id = agentID;
        this.p = params;
        this.NUM_OF_AGENTS = params.n();               // R17
        this.blockedUserList = new boolean[NUM_OF_AGENTS];
        // R12: truncated (rejection-sampled) Gaussian by default; legacy clip kept behind
        // initOpinionClip for regression comparison (clip creates ~4.8% atoms at exactly +-1).
        // 2026-07-21: "empirical" bypasses both -- draws from the real, deliberately-asymmetric
        // 7-bin survey distribution (Const.EMPIRICAL_OPINION_BIN_COUNTS) instead of a symmetric
        // mean-0 generator, since the Gaussian has no skew parameter a loss function could fit
        // toward that shape; sampling directly from the data is simpler and more faithful than
        // adding a parametric-family assumption on top of it.
        // 2026-08-07: "uniform" -- draws intrinsicOpinion ~ U[-1,1], for the CN2026 review's
        // robustness check on whether the Gaussian's center-mass concentration (and resulting
        // uneven camp_bin population sizes, e.g. echo_chamber_by_class nodeCount 17+50+55+55+17)
        // is load-bearing for the two-level homophily-gate mechanism's findings.
        if (p.initOpinionDist().equals("empirical")) {
            this.intrinsicOpinion = sampleEmpiricalOpinion();
        } else if (p.initOpinionDist().equals("uniform")) {
            this.intrinsicOpinion = -1.0 + randomGenerator.dynamics().nextDouble() * 2.0;
        } else if (p.initOpinionClip()) {
            this.intrinsicOpinion = Math.max(-1.0, Math.min(1.0, randomGenerator.dynamics().nextGaussian() * Const.INITIAL_OPINION_STD));
        } else {
            double x;
            do {
                x = randomGenerator.dynamics().nextGaussian() * Const.INITIAL_OPINION_STD;
            } while (Math.abs(x) > 1.0);
            this.intrinsicOpinion = x;
        }
        
        // R13: heterogeneous stubbornness (uniform draw) as a robustness arm; const = legacy 0.8.
        // NB pinned hubs (R4) override this to 1.0 after construction; relay strength (R3) couples
        // to the final value.
        if (p.stubDist().equals("uniform")) {
            this.stubbornness = p.stubMin() + randomGenerator.dynamics().nextDouble() * (p.stubMax() - p.stubMin());
        } else {
            this.stubbornness = Const.INITIAL_STUBBORNNESS;
        }
        this.opinion = this.intrinsicOpinion;
        this.bc = p.bcInit(); // dynamic not static; decoupled from bcCeiling (2026-07-14)
        this.postProb = p.initialPostProb();
        this.timeStep = 0;
        this.repostProb = p.repostProb(); // R6
        this.accessProb = p.accessProb(); // 2026-07-10: was Const.ACCESS_PROB, now sweepable
        // 2026-07-09: was a second hardcoded "10", independent of AdminOptim's feedCapacity read
        // site — postCash's real capacity was silently bottlenecking the feed at 10 regardless of
        // feed_capacity=, which is why feed_capacity=20 showed zero effect in the OAT sweep while
        // feed_capacity=5 (< 10) did show one. Both must track the same knob.
        setNumOfPosts(p.feedCapacity());
        setOpinionClass();
    }

    // 2026-07-21: 7 equal-width bins spanning [-1,1] (width 2/7 each), in ascending
    // self-reported-lean order -- shared edge convention between the empirical initial-opinion
    // sampler below and OpinionDynamics' cumulative post-count-by-bin accumulator, so the two stay
    // comparable. Public/static so both call sites use exactly the same bin boundaries.
    public static int opinionToBin7(double opinion) {
        int bin = (int) Math.floor((opinion + 1.0) / (2.0 / Const.NUM_OF_BINS_EMPIRICAL_7));
        return Math.max(0, Math.min(Const.NUM_OF_BINS_EMPIRICAL_7 - 1, bin));
    }

    // Draws a bin proportional to Const.EMPIRICAL_OPINION_BIN_COUNTS, then samples uniformly
    // within that bin's continuous sub-interval of [-1,1] (not 7 point masses -- real respondents
    // sharing a self-reported label don't share one exact underlying opinion value).
    private double sampleEmpiricalOpinion() {
        int[] counts = Const.EMPIRICAL_OPINION_BIN_COUNTS;
        int total = 0;
        for (int c : counts) total += c;
        int r = randomGenerator.dynamics().nextInt(total);
        int bin = 0;
        int cum = 0;
        for (int i = 0; i < counts.length; i++) {
            cum += counts[i];
            if (r < cum) { bin = i; break; }
        }
        double width = 2.0 / Const.NUM_OF_BINS_EMPIRICAL_7;
        double lo = -1.0 + bin * width;
        return lo + randomGenerator.dynamics().nextDouble() * width;
    }

    // getter methods

    public int getId() {
        return this.id;
    }

    public double getOpinion() {
        return this.opinion;
    }

    public double getIntrinsicOpinion() {
        return this.intrinsicOpinion;
    }

    public double getStubbornness() {
        return this.stubbornness;
    }

    public int getNumOfPosts() {
        return this.numOfPosts;
    }

    public int getToPost() {
        return this.toPost;
    }

    public int getOpinionClass() {
        return this.opinionClass;
    }

    public double getBc() {
        return this.bc;
    }

    public double getPostProb() {
        return this.postProb;
    }

    public List<Post> getFeed() {
        return this.feed;
    }

    public double getAccessProb() {
        return this.accessProb;
    }

    public PostCash getPostCash() {
        return this.postCash;
    }

    public boolean[] getBlockedUserList() {
        return this.blockedUserList;
    }

    public boolean getTarget() {
        return this.target;
    }

    public int getHubTier() {
        return this.hubTier;
    }

    public double getAverageComfortRate() {
        if (comfortHistory.isEmpty()) return 0.0;
        double sum = 0.0;
        for (double v : comfortHistory) sum += v;
        return sum / comfortHistory.size();
    }

    // R1: transient counters from the most recent repost()/unfollow() call this step.
    public int getLastReposts() { return this.lastReposts; }
    public int getLastCrossReposts() { return this.lastCrossReposts; }
    public int getLastBlocks() { return this.lastBlocks; }

    // setter methods

    public void setOpinion(double value) {
        this.opinion = value;
        setOpinionClass();
    }

    public void setPostProb(double value) {
        this.postProb = value;
    }

    public void setAccessProb(double value) {
        this.accessProb = value;
    }

    public void setBoundedConfidence(double value) {
        this.bc = value;
    }

    public void setTimeStep(int time) {
        this.timeStep = time;
    }

    public void setStubbornness(double value) {
        this.stubbornness = value;
    }

    public void setIntrinsicOpinion(double value) {
        this.intrinsicOpinion = value;
    }

    public void setNumOfPosts(int value) {
        this.numOfPosts = value;
        setPostCash(this.numOfPosts);
    }

    public void setPostCash(int value) {
        this.postCash = new PostCash(value);
    }

    public void setToPost(int value) {
        this.toPost = value;
    }

    public void setOpinionClass() {
        double shiftedOpinion = this.opinion + 1; // [-1,1] → [0,2]
        double opinionBinWidth = 2.0 / Const.NUM_OF_BINS_OF_OPINION;
        this.opinionClass = (int) Math.min(shiftedOpinion / opinionBinWidth, Const.NUM_OF_BINS_OF_OPINION - 1);
    }

    public void setTarget() {
        this.target = true;
    }

    public void setHubTier(int tier) {
        this.hubTier = tier;
    }

    // Exp A: assign which spreading channels this hub is allowed to use.
    public void setChannelMode(ChannelMode mode) {
        this.postEnabled = (mode == ChannelMode.BOTH || mode == ChannelMode.POST_ONLY);
        this.repostEnabled = (mode == ChannelMode.BOTH || mode == ChannelMode.REPOST_ONLY);
    }

    public boolean isPostEnabled() {
        return this.postEnabled;
    }

    public boolean isRepostEnabled() {
        return this.repostEnabled;
    }

    public void addToPostCash(Post post) {
        if (post.getPostUserId() != this.id
                && !this.blockedUserList[post.getPostUserId()]) {
            this.postCash.addPost(post);
        }
    }

    public void setUsed() {
        this.used = true;
    }

    public void resetUsed() {
        this.used = false;
    }

    // other methods

    public void resetPostCash() {
        this.postCash.reset();
        this.toPost = 0;
    }

    public void addPostToFeed(Post post) {
        if (!this.blockedUserList[post.getPostUserId()]) {
            this.feed.add(post);
        }
    }

    public void resetFeed() {
        this.feed.clear();
    }

    public void setForYouRootIds(java.util.Set<Integer> ids) {
        this.forYouRootIds = ids;
    }

    public void shufflePostCash(){
        this.postCash.shuffle();
    }

    // 2026-08-06: agentSet/stepStats params added so the comfort check below (the only place a
    // reader's own vcr/opinion and each feed post's author are both in scope at once) can tally
    // StepStats.feedClassComfortCountSum -- see that field's javadoc for why this needs to happen
    // here rather than in AdminOptim.AdminFeedback (which builds the feed but doesn't know the
    // reader's per-post comfort verdict).
    public void updateMyself(Agent[] agentSet, dynamics.StepStats stepStats) {
        int postNum = 0;
        int comfortPostNum = 0;
        // FJ assimilation averages only in-tolerance (dynamic bc) posts (2026-07-16, permanent:
        // was a bc_gate_assim toggle, now the only behavior — selective persuadability, not
        // selective exposure: out-of-bc posts still count fully for bc-decline/comfort below,
        // they just don't move the stated opinion).
        double assimSum = 0.0;
        int assimNum = 0;

        // read all posts in feed
        for (Post post : this.feed) {
            postNum++;

            double bcDist = Math.abs(post.getPostOpinion() - this.opinion);
            boolean inBcRange = bcDist < this.bc;
            if (inBcRange) {
                assimSum += post.getPostOpinion();
                assimNum++;
            }

            // R5/D4: fixed perceptual comfort radius BY DESIGN — deliberately NOT the dynamic bc.
            // These are two different KINDS of threshold, not two measurements of the same thing
            // (user framing, 2026-07-25): bc is a rejection/defensive threshold -- how much
            // disagreement can be tolerated before disengaging (assimilation stops, unfollow
            // triggers); vocalComfortRadius is an activation/expression threshold -- how much
            // nearby agreement is needed to feel safe enough to speak up. An agent can plausibly be
            // narrow-bc (easily disengages) yet still have a generous comfort radius (doesn't take
            // much to feel emboldened), or vice versa -- coupling them would conflate "how
            // defensive am I" with "do I feel safe to speak," a category error independent of the
            // self-referential-feedback problem that would also result (a wide bc would inflate its
            // own comfort measurement, reimporting the same runaway-growth issue diagnosed for bc's
            // own graded-relaxation target -- see the block below). Concretely: using dynamic bc
            // here would silence intolerant extremists (narrow bc -> almost nothing reads as
            // comfortable -> rarely vocal) rather than making them the hyper-vocal minority the
            // empirical target (Buntain & Snegovaya 2025) actually shows.
            // 2026-07-19: promoted off Const.VOCAL_COMFORT_RADIUS to p.vocalComfortRadius() (sweepable) --
            // testing whether the fixed absolute window is what's suppressing SF1 apparent
            // polarization (docs/report/2026-07-18-joint-stage-calibration.md).
            boolean withinComfort = Math.abs(post.getPostOpinion() - this.opinion) < p.vocalComfortRadius();
            if (withinComfort) {
                comfortPostNum++;
            }

            // 2026-08-06: StepStats.feedClassComfortCountSum javadoc -- population readers only,
            // same R1 hub-exclusion convention as everywhere else.
            if (!this.target && withinComfort) {
                int authorClass = agentSet[post.getPostUserId()].getOpinionClass();
                stepStats.feedClassComfortCountSum[this.opinionClass][authorClass]++;
            }

        }

        // Graded bc relaxation (redesigned 2026-07-24, docs/report/2026-07-21-conduit-experiment-
        // design.md), superseding the 2026-07-22 per-post asymmetric ratchet above (git history).
        // That design applied `bc *= bcDecRate` / `bc += bcRecoveryRate*(bcCeiling-bc)` once PER
        // POST in the feed, sequentially — with feed_capacity ~24-32 posts/step, whichever side
        // (comfortable vs. uncomfortable) held even a modest feed-majority compounded across ~20-30
        // hits within a single step and steamrolled bc to whichever rail that majority favored,
        // regardless of the actual comfortable fraction's magnitude — the same "no graded interior
        // equilibrium, saturates to a rail on either side of a threshold" failure mode diagnosed and
        // fixed for postProb on 2026-07-23 (see below), just one step later on bc. Dashboard GEXF
        // inspection of app-pol baseline v12's round0/pt4 confirmed it empirically: bc histogram was
        // a single spike at bcCeiling (~85% of agents) plus a small floor pile, no separation by
        // opinion extremity, despite bc_dec=0.951 being far from its 1.0 (fully-static) extreme.
        // Fix: aggregate ONCE per step (inBcRate, reusing the same assimNum/postNum already computed
        // above for the FJ assimilation average) into a single graded target, then relax toward it —
        // exact structural mirror of postProb's targetPostProb fix below. bcDecRate/bcRecoveryRate
        // are RETAINED but REINTERPRETED: no longer a per-post multiplicative-shrink constant and a
        // per-post additive-toward-ceiling constant (two different functional forms, not
        // commensurable), but now two relaxation RATES toward the same shared target — asymmetric
        // negativity-dominance (Vallone et al. 1985; Baumeister et al. 2001, wssit2026-TomoyaTakeda
        // .tex Sec. "Confidence Decline") is now the single, comparable ratio bcDecRate/bcRecoveryRate
        // (>1 = bc falls faster than it rises for an equally-sized gap), rather than smeared across
        // two incommensurable mechanisms. Deliberately left free/swept (not hardcoded to a fixed
        // ratio) since no citation here gives a precise multiplier — see design doc discussion.
        // Old calibrated values do NOT carry over: units changed from "per-post factor" to "per-step
        // gap-closing fraction," needs fresh calibration (search-space ranges too — old bcDecRate
        // range was tuned as a near-1.0 multiplicative retention factor, not a relaxation rate).
        if (postNum > 0) {
            double inBcRate = (double) assimNum / postNum;
            double targetBC = p.bcFloor() + (p.bcCeiling() - p.bcFloor()) * inBcRate;
            if (targetBC < this.bc) {
                this.bc += p.bcDecRate() * (targetBC - this.bc);
            } else {
                this.bc += p.bcRecoveryRate() * (targetBC - this.bc);
            }
        }

        if (postNum > 0) {
            double comfortPostRate = (double) comfortPostNum / postNum;

            comfortHistory.addLast(comfortPostRate);
            if (comfortHistory.size() > COMFORT_MEMORY_SIZE) {
                comfortHistory.removeFirst();
            }

            // Graded comfort->vocality (redesigned 2026-07-23, docs/report/2026-07-21-conduit-
            // experiment-design.md): supersedes the symmetric multiplicative ratchet above (`pp *=
            // factor` / `pp /= factor` around the comfortPostRate=0.5 threshold), which had no
            // restoring force -- being on either side of 0.5 is a self-reinforcing regime (crossing
            // the threshold doesn't change which branch fires next step), so postProb had no stable
            // interior point and saturated to minPostProb/maxPostProb for every agent regardless of
            // *how* comfortable their feed was, not just *whether*. Confirmed empirically via a
            // dashboard GEXF inspection of round1/pt3's replication (postProb histogram: bimodal
            // spike at the two rails, near-empty middle) -- moderates in a homophilous bubble ended
            // up exactly as vocal as the extremes, collapsing the intended camp separation.
            // targetPostProb is a linear interpolation between the vocality floor/ceiling by this
            // step's comfort rate; postProb relaxes toward it by a fraction postProbRelaxRate of the
            // remaining gap each step (discrete leaky-integrator / exponential-moving-average
            // toward a moving target). Because the update now depends on postProb itself (the
            // `-postProb` term), targetPostProb is a genuine stable equilibrium for every comfort
            // level, not just the two boundaries -- an agent with comfortPostRate=0.6 settles at a
            // stable intermediate vocality instead of eventually saturating like one at 0.95.
            double targetPostProb = p.minPostProb() + (p.maxPostProb() - p.minPostProb()) * comfortPostRate;
            this.postProb += p.postProbRelaxRate() * (targetPostProb - this.postProb);
        }

        //// social influence
        // Only update when at least one in-bc post drives assimilation; an empty average would
        // make (sum / num) = 0/0 = NaN and corrupt the opinion irrecoverably. All-out-of-bc feeds
        // (bc collapsed to the floor with nothing comfortable delivered) leave opinion frozen for
        // the step.
        if (assimNum > 0) {
            this.opinion = this.stubbornness * this.intrinsicOpinion + (1 - this.stubbornness) * (assimSum / assimNum);
        }

        //// clipping

        // opinion is in [-1, 1]
        this.opinion = Math.max(-1.0, Math.min(this.opinion, 1.0));

        // postProb is in [minPostProb, maxPostProb]
        this.postProb = Math.max(p.minPostProb(), Math.min(this.postProb, p.maxPostProb()));

        // bc is in [p.bcFloor(), p.bcCeiling()] (upper clamp needed now that recovery can push bc
        // back up, not just decline toward the floor). Bounds are sweepable (2026-07-14) to test
        // whether the bc-histogram pile-up at the bounds survives relaxing them.
        this.bc = Math.max(this.bc, p.bcFloor());
        this.bc = Math.min(this.bc, p.bcCeiling());

        setOpinionClass();
    }

    public List<Post> repost(Agent[] agents) {
        this.lastReposts = 0;
        this.lastCrossReposts = 0;
        // Exp A: a hub with reposting disabled emits no reposts (still reads/updates normally).
        if (!this.repostEnabled) {
            return Collections.emptyList();
        }
        if (this.feed.isEmpty()) {
            return Collections.emptyList();
        }

        // Repost is bc-gated (2026-07-17, permanent, mirroring updateMyself()'s bcGateAssim
        // precedent): in-bc posts repost at repostProb, out-of-bc posts at the separate, lower
        // outOfBCRepostProb -- selective amplification, not selective exposure (out-of-bc posts
        // are still seen/read: they count fully for bc-decline/comfort elsewhere, they just relay
        // less readily). Was previously coupled to repostProb by default
        // (coupleOutOfBCRepost=true, the 2026-06-26 parsimony behavior), which made this gate a
        // no-op; removed rather than left as a togglable option, same precedent as bcGateAssim.
        List<Post> repostedPostList = new ArrayList<>();
        for (Post post : this.feed) {
            boolean inBc = Math.abs(post.getPostOpinion() - this.opinion) < this.bc;
            double pr = inBc ? this.repostProb : p.outOfBCRepostProb();
            if (randomGenerator.dynamics().nextDouble() < pr) {
                // Boost the velocity signal on the object admin's For-You ranking tracks
                // (the feed post), before constructing the (possibly distorted) relayed copy.
                post.receiveRepost(this.timeStep);
                // R1: cross-cutting repost = reposter and the post content are opposite-sign
                // (basis is the pre-relay feed-post opinion the reposter actually endorsed).
                this.lastReposts++;
                if (this.opinion * post.getPostOpinion() < 0) this.lastCrossReposts++;
                boolean viaAlgo = this.forYouRootIds.contains(post.getRootPostId());
                Post relayed = relay(post, !inBc, viaAlgo);
                repostedPostList.add(relayed);
            }
        }
        return repostedPostList;
    }

    // Relay distortion: conveyed opinion is reframed toward the reposter's own opinion.
    // R3: strength is relayDistortionStrength when coupleRelayDistortion=false (explicit global override);
    // when true, coupled to this.stubbornness (agent-specific default).
    // R10: attribution. Default "original" keeps postUserId = source author (conduit immunity —
    // sanctions/follows target the source, the misattribution mechanism). "reposter" sets
    // postUserId = relayer, neutralizing that (sanctions hit the relayer instead). Lineage
    // (rootPostId/parentPostId/relayerId/depth) is always recorded for cascade logging (R19).
    // outOfBc: whether this relay crossed the reposter's own bc window at read time (2026-07-21) --
    // recorded on the Post as the homophily/hostile repost-edge tag; does NOT change conveyed
    // opinion (both in-bc and out-of-bc relay stay content-preserving so the receiver's bc-decline
    // exposure channel is unaffected either way).
    private Post relay(Post original, boolean outOfBc, boolean viaAlgo) {
        // Diagnostic (2026-07-08): relayEnabled=false short-circuits distortion + reattribution —
        // verbatim opinion, original attribution (see ExperimentConfig.relayEnabled).
        if (!p.relayEnabled()) {
            return Post.relayOf(original, this.id, original.getPostUserId(), original.getPostOpinion(), outOfBc, viaAlgo);
        }
        double s = p.coupleRelayDistortion() ? this.stubbornness : p.relayDistortionStrength();
        double conveyed = original.getPostOpinion()
                + s * (this.opinion - original.getPostOpinion());
        conveyed = Math.max(-1.0, Math.min(1.0, conveyed));
        int attrib = p.relAttrib().equals("reposter") ? this.id : original.getPostUserId();
        return Post.relayOf(original, this.id, attrib, conveyed, outOfBc, viaAlgo);
    }

    /**
     * フォロー処理を行うメソッド
     * @param agents エージェント配列
     * @return int[] {新規フォローID, 解除したID}。何もしなかった場合は null を返す。
     */
    // R22: the follow graph is owned by AdminOptim; queries/mutations go through it. Mutations are
    // applied INLINE here (the old end-of-turn admin.updateAdjacencyMatrix is removed). Eviction
    // iterates followees in ascending id order, reproducing the old followList index-order
    // tie-breaking exactly, so this is a behavior-preserving refactor (byte-identical output).
    public int[] follow(Agent[] agents, AdminOptim admin) {
        // 1. 候補者のリストアップ
        List<Integer> candidates = new ArrayList<>();
        for (Post post : this.feed) {
            // 既にフォローしている、またはブロック（blockedUserList）している人は除外
            if (Math.abs(post.getPostOpinion() - this.opinion) < this.bc
                    && !admin.follows(this.id, post.getPostUserId())
                    && !this.blockedUserList[post.getPostUserId()]) {
                candidates.add(post.getPostUserId());
            }
        }

        // 候補がいない、または確率判定でフォローしない場合は null を返す
        if (candidates.isEmpty() || randomGenerator.dynamics().nextDouble() >= p.followProb()) {
            return new int[]{-1, -1};
        }

        // 2. 新しくフォローする相手を決定
        int newFollowId = candidates.get(randomGenerator.dynamics().nextInt(candidates.size()));

        // 3. 上限チェックと「押し出し（アンフォロー）」処理
        int removeTargetId = -1; // 初期値は -1（誰も削除しない）

        if (admin.followeeCount(this.id) >= p.maxFollowCapacity()) {
            if (p.evictBeta() < 0) {
                // Legacy: deterministically evict the most opinion-distant followee (argmax,
                // ascending-id tie-break).
                double maxDiff = -1.0;
                for (int f : admin.sortedFollowees(this.id)) {
                    double diff = Math.abs(agents[f].getOpinion() - this.opinion);
                    if (diff > maxDiff) {
                        maxDiff = diff;
                        removeTargetId = f;
                    }
                }
            } else {
                // R9: softmax eviction, P(evict k) ∝ exp(beta·|o_k - o_i|). beta=0 = uniform.
                removeTargetId = softmaxEvict(agents, admin);
            }
            if (removeTargetId != -1) {
                admin.removeFollowEdge(this.id, removeTargetId);
            }
        }

        // 4. 新しいフォローを確定
        admin.addFollowEdge(this.id, newFollowId);

        // ★ [0]:追加したID, [1]:削除したID を返す (metrics/logging only now)
        return new int[]{newFollowId, removeTargetId};
    }

    // R9: pick a followee to evict with P(k) ∝ exp(beta·|o_k - o_i|). beta=0 => uniform random.
    // Iterates followees in ascending id order to match the legacy selection for a given draw.
    private int softmaxEvict(Agent[] agents, AdminOptim admin) {
        double beta = p.evictBeta();
        List<Integer> fs = admin.sortedFollowees(this.id);
        double total = 0.0;
        double[] w = new double[fs.size()];
        for (int k = 0; k < fs.size(); k++) {
            w[k] = Math.exp(beta * Math.abs(agents[fs.get(k)].getOpinion() - this.opinion));
            total += w[k];
        }
        if (total <= 0.0) return -1;
        double r = randomGenerator.dynamics().nextDouble() * total;
        double cum = 0.0;
        for (int k = 0; k < w.length; k++) {
            cum += w[k];
            if (r <= cum) return fs.get(k);
        }
        return -1;
    }

    public int unfollow(AdminOptim admin) {
        this.lastBlocks = 0;
        if (this.feed.isEmpty()) {
            return -1;
        }

        List<Integer> dislikeUser = new ArrayList<>();
        if (randomGenerator.dynamics().nextDouble() > p.pU()) {
            return -1;
        }
        for (Post post : this.feed) {
            if (Math.abs(post.getPostOpinion() - this.opinion) > this.bc && admin.follows(this.id, post.getPostUserId())) {
                block(post.getPostUserId());
                admin.removeFollowEdge(this.id, post.getPostUserId());
                return post.getPostUserId();
            }
            if (Math.abs(post.getPostOpinion() - this.opinion) > this.bc && !admin.follows(this.id, post.getPostUserId())) {
                dislikeUser.add(post.getPostUserId());
            }
        }
        if (dislikeUser.size() > 0) { // if there's nobody to unfollow, agents can also "block" others
            block(dislikeUser.get(randomGenerator.dynamics().nextInt(dislikeUser.size())));
        }
        return -1;
    }

    // Mark id as blocked; count new blocks (R1).
    private void block(int id) {
        if (!this.blockedUserList[id]) {
            this.lastBlocks++;
        }
        this.blockedUserList[id] = true;
    }

    public Post makePost(int step) {

        Post post;
        post = new Post(this.id, this.opinion, step);

        this.toPost = 1;

        this.postProb -= Const.POST_COST;
        if (this.postProb < p.minPostProb()) {
            this.postProb = p.minPostProb();
        }

        return post;
    }

}
