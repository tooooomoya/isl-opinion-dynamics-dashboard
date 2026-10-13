package agent;

import admin.AdminOptim;
import constants.Const;
import experiment.SimParams;
import java.util.*;
import rand.randomGenerator;

/**
 * An agent of the attention-economy model (spec rev 9). One value X in [-1,1], a private table of
 * action values Q(state, action), and a list of its own posts. At each visit it sees a feed, reads
 * its state (identity fit of the feed, recognition of its surviving posts), learns from the
 * transition since its previous visit, and takes exactly one action: post, like, reshare or rewire.
 */
public class Agent {
    // Activity-channel control for hub manipulation (inherited intervention machinery).
    public enum ChannelMode { BOTH, POST_ONLY, REPOST_ONLY, NONE }

    public static final int POST = 0, LIKE = 1, RESHARE = 2, REWIRE = 3;
    public static final int NUM_ACTIONS = 4;
    public static final int NUM_STATES = 9; // 3 identity-fit levels x 3 recognition levels
    public static final String[] ACTION_NAMES = {"post", "like", "reshare", "rewire"};

    private final int id;
    private double opinion;           // X (current)
    private double intrinsicX;        // X at t = 0 (anchor of the drift rule; pinned hubs overwrite it)
    private double stubbornness;      // 1 - mu ; kept for the pinned-hub machinery and the snapshot log
    private int opinionClass;
    private PostCash postCash;        // posts delivered by followees, window for the chronological feed
    private final List<Post> feed = new ArrayList<>();
    private double accessProb;
    private boolean target = false;
    private int hubTier = -1;
    private int timeStep;
    private boolean used;
    // One reaction per post: a post can be liked at most once by an agent, and an agent holds at most one
    // copy of a story (reshare once per root post, own stories included). Without this, repeated likes of
    // the same post would inflate its author's recognition and keep the post alive indefinitely.
    private final java.util.BitSet seenPostIds = new java.util.BitSet(); // ids of every post ever shown to this agent
    private final java.util.HashSet<Integer> likedPostIds = new java.util.HashSet<>();
    private final java.util.HashSet<Integer> resharedRoots = new java.util.HashSet<>();
    private boolean postEnabled = true;
    private boolean repostEnabled = true;
    private final SimParams p;

    // ---- learning state ----
    private final double[][] q = new double[NUM_STATES][NUM_ACTIONS];
    private final long[][] decisions = new long[NUM_STATES][NUM_ACTIONS]; // how often each (state, action) was chosen
    public long[][] getDecisions() { return decisions; }
    public static void flushLearningLog(int step, java.nio.file.Path dir) throws java.io.IOException { LearningLog.flush(step, dir); }
    private int lastState = -1;
    private int lastAction = -1;
    private double lastIdentityFit = 0.0;
    private double lastRecognition = 0.0;
    private final List<Post> ownPosts = new ArrayList<>(); // own originals + reshares, alive ones only after purge

    public Agent(int agentID, SimParams params) {
        this.id = agentID;
        this.p = params;
        if (p.initOpinionDist().equals("gaussian")) {
            double x;
            do {
                x = randomGenerator.dynamics().nextGaussian() * Const.INITIAL_OPINION_STD;
            } while (Math.abs(x) > 1.0);
            this.intrinsicX = x;
        } else { // uniform: X ~ U[-1, 1]
            this.intrinsicX = -1.0 + randomGenerator.dynamics().nextDouble() * 2.0;
        }
        this.opinion = this.intrinsicX;
        this.stubbornness = 1.0 - p.mu();
        this.accessProb = p.accessProb();
        for (double[] row : q) Arrays.fill(row, p.qInit());
        setPostCash(p.feedCapacity());
        setOpinionClass();
    }

    /** 7 equal-width bins spanning [-1,1], ascending; used by the cumulative post-count-by-bin log. */
    public static int opinionToBin7(double opinion) {
        int bin = (int) Math.floor((opinion + 1.0) / (2.0 / Const.NUM_OF_BINS_EMPIRICAL_7));
        return Math.max(0, Math.min(Const.NUM_OF_BINS_EMPIRICAL_7 - 1, bin));
    }

    // ---------------- getters ----------------
    public int getId() { return id; }
    public double getOpinion() { return opinion; }
    public double getIntrinsicOpinion() { return intrinsicX; }
    public double getStubbornness() { return stubbornness; }
    public int getOpinionClass() { return opinionClass; }
    public List<Post> getFeed() { return feed; }
    public double getAccessProb() { return accessProb; }
    public PostCash getPostCash() { return postCash; }
    public boolean getTarget() { return target; }
    public int getHubTier() { return hubTier; }
    public boolean isPostEnabled() { return postEnabled; }
    public boolean isRepostEnabled() { return repostEnabled; }
    public double getLastIdentityFit() { return lastIdentityFit; }
    public double getLastRecognition() { return lastRecognition; }
    public double[][] getQ() { return q; }
    public int getLastState() { return lastState; }
    public int getLastAction() { return lastAction; }
    public List<Post> getOwnPosts() { return ownPosts; }

    // Retained so the inherited analysis/export code (Gephi, snapshots) still compiles: the
    // bounded-confidence, posting-rate and comfort quantities no longer exist in this model.
    public double getBc() { return 0.0; }
    public double getPostProb() { return 0.0; }
    public double getAverageComfortRate() { return 0.0; }

    // ---------------- setters ----------------
    public void setOpinion(double value) { this.opinion = value; setOpinionClass(); }
    public void setTimeStep(int time) { this.timeStep = time; }
    public void setStubbornness(double value) { this.stubbornness = value; }
    public void setAccessProb(double value) { this.accessProb = value; }
    public void setUsed() { this.used = true; }
    public void resetUsed() { this.used = false; }
    public void setTarget() { this.target = true; }
    public void setHubTier(int tier) { this.hubTier = tier; }
    public void setPostCash(int value) { this.postCash = new PostCash(value); }
    // which root post ids this visit's feed received through the algorithmic For-You stream
    private java.util.Set<Integer> algoRootIds = java.util.Set.of();
    public void setAlgoRootIds(java.util.Set<Integer> ids) { this.algoRootIds = ids; }
    public boolean receivedViaAlgo(Post post) { return algoRootIds.contains(post.getRootPostId()); }
    // GEXF round-trip (GephiReader) writes these back; they are inert in this model.
    public void setBoundedConfidence(double value) { }
    public void setPostProb(double value) { }

    /** Hub machinery: fixes the intrinsic value (the drift anchor) as well as the current one. */
    public void setIntrinsicOpinion(double value) { this.intrinsicX = value; this.opinion = value; setOpinionClass(); }

    public void setOpinionClass() {
        double shifted = this.opinion + 1;
        double width = 2.0 / Const.NUM_OF_BINS_OF_OPINION;
        this.opinionClass = (int) Math.min(shifted / width, Const.NUM_OF_BINS_OF_OPINION - 1);
    }

    public void setChannelMode(ChannelMode mode) {
        this.postEnabled = (mode == ChannelMode.BOTH || mode == ChannelMode.POST_ONLY);
        this.repostEnabled = (mode == ChannelMode.BOTH || mode == ChannelMode.REPOST_ONLY);
    }

    // ---------------- feed / cache plumbing ----------------
    public void addToPostCash(Post post) {
        if (post.getPostUserId() != this.id) this.postCash.addPost(post);
    }
    public void resetPostCash() { this.postCash.reset(); }
    public void addPostToFeed(Post post) { this.feed.add(post); seenPostIds.set(post.getPostId()); }
    /** True if this post was already shown to the agent in an earlier (or the current) feed: each post is shown at most once. */
    public boolean hasSeen(Post post) { return seenPostIds.get(post.getPostId()); }
    public void resetFeed() { this.feed.clear(); }
    public void shufflePostCash() { this.postCash.shuffle(); }

    // ---------------- similarity, state, reward ----------------

    /** sim(x, y) = 1 - |x - y| / 2, in [0, 1] for X in [-1, 1]. */
    public static double similarity(double x, double y) {
        return 1.0 - Math.abs(x - y) / 2.0;
    }

    /** Identity fit: mean similarity between my X and the posts in my feed; 0 for an empty feed. */
    public double identityFit() {
        if (feed.isEmpty()) return 0.0;
        double s = 0.0;
        for (Post post : feed) s += similarity(opinion, post.getPostOpinion());
        return s / feed.size();
    }

    /**
     * Recognition of my surviving posts' likes L: mix * (1 - exp(-L/lambda)) + (1 - mix) * min(1, ln(1+L)/ln(1+L_ref)). Dead posts
     * are dropped from my list here (a dead post is never revived), so their likes stop counting.
     */
    public double recognition(int step) {
        long likes = 0;
        for (Iterator<Post> it = ownPosts.iterator(); it.hasNext(); ) {
            Post post = it.next();
            if (!post.isAlive(step, p.deadAfter())) it.remove();
            else likes += post.getLikesReceived();
        }
        // fast term: first likes matter a lot (peripheral agents); slow term: keeps separating influencers
        double fast = 1.0 - Math.exp(-likes / Math.max(1e-9, p.recogLambda()));
        double slow = Math.min(1.0, Math.log1p((double) likes) / Math.log1p(p.lRef()));
        return p.recogMix() * fast + (1.0 - p.recogMix()) * slow;
    }

    private static int bin(double v, double lo, double hi) {
        return v < lo ? 0 : (v < hi ? 1 : 2);
    }

    /** State index = 3 * identity-fit level + recognition level. */
    public int stateOf(double identityFit, double recognition) {
        return 3 * bin(identityFit, p.iEdgeLo(), p.iEdgeHi()) + bin(recognition, p.lEdgeLo(), p.lEdgeHi());
    }

    /**
     * Observe this visit's state and reward r = identityFit + recognition (equal weights, both in
     * [0,1]), and learn from the transition since the previous visit:
     * Q(s,a) += eta * (r + gamma * max_a' Q(s',a') - Q(s,a)).
     * Returns the new state.
     */
    public int observeAndLearn(int step) {
        double fit = identityFit();
        double rec = recognition(step);
        this.lastIdentityFit = fit;
        this.lastRecognition = rec;
        int s = stateOf(fit, rec);
        if (lastAction >= 0) {
            // bootstrap only from actions that can be taken at s' (an unavailable action's Q is never
            // updated, and under optimistic initialisation it would otherwise dominate the target)
            boolean[] ok = availableActions();
            double best = Double.NEGATIVE_INFINITY;
            for (int a = 0; a < NUM_ACTIONS; a++) if (ok[a]) best = Math.max(best, q[s][a]);
            if (best == Double.NEGATIVE_INFINITY) best = 0.0; // nothing can be done at s': no future value
            double r = p.wFit() * fit + p.wRec() * rec;
            double delta = r + p.qGamma() * best - q[lastState][lastAction];
            LearningLog.recordTd(lastState, lastAction, r, delta);
            q[lastState][lastAction] += p.qEta() * delta;
        }
        return s;
    }

    private boolean canLike(Post post) { return !likedPostIds.contains(post.getPostId()); }
    private boolean canReshare(Post post) { return !resharedRoots.contains(post.getRootPostId()); }

    /**
     * Actions that can be taken with the current feed: post (if posting is enabled); like needs a feed
     * post this agent has not liked yet; reshare needs a feed post whose story it does not hold yet (and
     * reposting enabled); rewire unless the network is static (rewire=false).
     */
    private boolean[] availableActions() {
        boolean[] ok = new boolean[NUM_ACTIONS];
        ok[POST] = postEnabled;
        for (Post post : feed) {
            if (canLike(post)) ok[LIKE] = true;
            if (repostEnabled && canReshare(post)) ok[RESHARE] = true;
        }
        ok[REWIRE] = p.rewireOn();
        return ok;
    }

    /**
     * Epsilon-softmax choice over the available actions: with probability qEps a uniformly random
     * available action (exploration floor, so an action that happened to look bad early is still
     * retried), otherwise softmax P(a|s) ~ exp(Q(s,a)/tau). Post needs posting
     * enabled; like and reshare need a non-empty feed (reshare also needs reposting enabled).
     * Rewire is available unless rewire=false (static network); it is a no-op without a valid candidate. Records (s, a) so the
     * next visit can credit it.
     */
    public int chooseAction(int state) {
        boolean[] ok = availableActions();
        if (!ok[POST] && !ok[LIKE] && !ok[RESHARE] && !ok[REWIRE]) ok[POST] = true; // never stuck with no action
        if (p.qEps() > 0.0 && randomGenerator.dynamics().nextDouble() < p.qEps()) {
            int avail = 0;
            for (boolean b : ok) if (b) avail++;
            int pick = randomGenerator.dynamics().nextInt(avail);
            int chosenU = POST;
            for (int a = 0; a < NUM_ACTIONS; a++) {
                if (!ok[a]) continue;
                if (pick-- == 0) { chosenU = a; break; }
            }
            this.lastState = state;
            this.lastAction = chosenU;
            logChoice(state, ok, chosenU);
            return chosenU;
        }
        double tau = Math.max(1e-9, p.qTau());
        double max = Double.NEGATIVE_INFINITY;
        for (int a = 0; a < NUM_ACTIONS; a++) if (ok[a]) max = Math.max(max, q[state][a]);
        double[] w = new double[NUM_ACTIONS];
        double total = 0.0;
        for (int a = 0; a < NUM_ACTIONS; a++) {
            if (!ok[a]) continue;
            w[a] = Math.exp((q[state][a] - max) / tau);
            total += w[a];
        }
        double r = randomGenerator.dynamics().nextDouble() * total;
        double cum = 0.0;
        int chosen = POST;
        for (int a = 0; a < NUM_ACTIONS; a++) {
            if (!ok[a]) continue;
            cum += w[a];
            chosen = a;
            if (r < cum) break;
        }
        this.lastState = state;
        this.lastAction = chosen;
        logChoice(state, ok, chosen);
        return chosen;
    }

    /** Diagnostics only (no randomness): the policy's probability of each offered action and its Q-gap to the best offered one. */
    private void logChoice(int state, boolean[] ok, int pick) {
        decisions[state][pick]++;
        double tau = Math.max(1e-9, p.qTau());
        double max = Double.NEGATIVE_INFINITY;
        int k = 0;
        for (int a = 0; a < NUM_ACTIONS; a++) if (ok[a]) { max = Math.max(max, q[state][a]); k++; }
        double[] gap = new double[NUM_ACTIONS], pr = new double[NUM_ACTIONS];
        double z = 0.0;
        for (int a = 0; a < NUM_ACTIONS; a++) {
            if (!ok[a]) continue;
            gap[a] = q[state][a] - max;
            pr[a] = Math.exp(gap[a] / tau);
            z += pr[a];
        }
        double eps = p.qEps();
        for (int a = 0; a < NUM_ACTIONS; a++) if (ok[a]) pr[a] = (1.0 - eps) * pr[a] / z + eps / k;
        LearningLog.recordChoice(ok, gap, pr, pick);
    }

    // ---------------- actions ----------------

    /**
     * Pick the post to react to with P(j) ~ exp(-betaH * |x_i - x_j|), among the feed posts this
     * agent may still react to in the given way ({@link #LIKE}: not liked before; {@link #RESHARE}:
     * story not held yet). Null if there is none.
     */
    public Post pickFromFeed(int action) {
        java.util.List<Post> eligible = new java.util.ArrayList<>();
        for (Post post : feed) {
            if (action == LIKE ? canLike(post) : canReshare(post)) eligible.add(post);
        }
        if (eligible.isEmpty()) return null;
        double[] w = new double[eligible.size()];
        double total = 0.0;
        for (int k = 0; k < w.length; k++) {
            w[k] = Math.exp(-p.betaH() * Math.abs(opinion - eligible.get(k).getPostOpinion()));
            total += w[k];
        }
        double r = randomGenerator.dynamics().nextDouble() * total;
        double cum = 0.0;
        for (int k = 0; k < w.length; k++) {
            cum += w[k];
            if (r < cum) return eligible.get(k);
        }
        return eligible.get(eligible.size() - 1);
    }

    /** Post: a new original carrying my current X. */
    public Post makePost(int step) {
        Post post = new Post(this.id, this.opinion, step);
        ownPosts.add(post);
        resharedRoots.add(post.getRootPostId()); // my own story: I never reshare it
        return post;
    }

    /**
     * Like: consume {@code src}; the like is credited to its author and refreshes its life.
     * Reacting to a post by someone I follow moves that followee to the back of my queue.
     */
    public void like(Post src, int step, AdminOptim admin) {
        src.like(step);
        likedPostIds.add(src.getPostId());
        admin.touchFollowee(this.id, src.getPostUserId());
    }

    /**
     * Reshare: a new post with {@code src}'s X, authored by me (so its future likes are mine). The
     * source is refreshed and counted as reshared (velocity ranking). Returns the new post.
     */
    public Post reshare(Post src, int step, AdminOptim admin, boolean viaAlgo) {
        src.receiveRepost(step);
        resharedRoots.add(src.getRootPostId());
        admin.touchFollowee(this.id, src.getPostUserId());
        Post copy = Post.reshareOf(src, this.id, step, viaAlgo);
        ownPosts.add(copy);
        return copy;
    }

    /**
     * Rewire: replace my oldest followee (front of the follow queue) by one agent drawn, with
     * weight exp(-betaH * |x_i - x_m|), from the originators of the posts in my current feed whom I
     * do not follow yet (the originator of a reshare is the author of the post it traces back to,
     * not the resharer). The drawn candidate replaces the front followee only if it is strictly more
     * similar to me (smaller |x_i - x_m|); otherwise nothing changes (queue and follow list stay as they
     * are). Out-degree is conserved. If there is no candidate nothing happens.
     * Returns the newly followed id, or -1 when no rewire was executed.
     */
    public int rewire(AdminOptim admin, Agent[] agents) {
        Integer front = admin.frontFollowee(this.id);
        if (front == null) return -1;
        Set<Integer> mine = admin.getFollowees(this.id);
        LinkedHashSet<Integer> cand = new LinkedHashSet<>();
        for (Post post : feed) {
            int m = post.getRootAuthorId();
            if (m != this.id && !mine.contains(m)) cand.add(m);
        }
        if (cand.isEmpty()) return -1;
        int[] ids = new int[cand.size()];
        double[] w = new double[ids.length];
        double total = 0.0;
        int k = 0;
        for (int m : cand) {
            ids[k] = m;
            w[k] = Math.exp(-p.betaH() * Math.abs(opinion - agents[m].getOpinion()));
            total += w[k];
            k++;
        }
        double r = randomGenerator.dynamics().nextDouble() * total;
        double cum = 0.0;
        int chosen = ids[ids.length - 1];
        for (k = 0; k < ids.length; k++) {
            cum += w[k];
            if (r < cum) { chosen = ids[k]; break; }
        }
        if (Math.abs(opinion - agents[chosen].getOpinion()) >= Math.abs(opinion - agents[front].getOpinion())) return -1;
        admin.removeFollowEdge(this.id, front);
        admin.addFollowEdge(this.id, chosen);
        return chosen;
    }

    /** Value drift (off in the baseline mu = 0): x <- (1-mu) x0 + mu * mean(feed X). */
    public void updateValues() {
        double mu = p.mu();
        if (mu <= 0.0 || feed.isEmpty()) return;
        double s = 0.0;
        for (Post post : feed) s += post.getPostOpinion();
        this.opinion = (1.0 - mu) * intrinsicX + mu * (s / feed.size());
        this.opinion = Math.max(-1.0, Math.min(1.0, this.opinion));
        setOpinionClass();
    }
}
