package admin;

import agent.*;
import constants.Const;
import dynamics.StepStats;
import experiment.SimParams;
import java.util.*;
import rand.randomGenerator;

public class AdminOptim {
    private int n;
    private final SimParams p; // R20: instance-scoped runtime params
    private Set<Integer>[] followees; // adjacency list: users that userId follows
    private Set<Integer>[] followers; // reverse adjacency list: users that follow userId
    private int[] followerNumArray;

    // ---- Velocity-primary "For You" recommender state (research-direction.md §3 item 6) ----
    // Sliding window of recently-created original posts; ranked by absolute (not
    // follower-normalised, see velocityScore below) velocity for the For-You slots. Only
    // populated/used when FEED_ALGO_SHARE > 0.
    private final List<Post> recentPosts = new ArrayList<>(); // all alive posts (originals and reshares), creation order
    private long createdPostCount = 0;
    private long diedPostCount = 0;
    // R11.1 (2026-07-16): cached ranking + last-refresh step, so rankByVelocity only rescores/
    // resorts every velocityRankInterval() steps instead of every step (see rankByVelocity).
    private List<Post> cachedRanked = null;
    private int lastRankStep = Integer.MIN_VALUE;
    // Cached hop-distance maps (directed follow-out graph, see computeReachable), refreshed every
    // REACH_REFRESH_INTERVAL steps since the graph evolves slowly. reachDistCache[src].get(v) =
    // shortest hop distance from src to v (>=1), absent if v is unreached within the depth cap.
    private Map<Integer, Integer>[] reachDistCache;
    private int reachCachedStep = -1;
    private int reachCachedH = Integer.MIN_VALUE;
    // 2026-07-29: cumulative (whole-run) post-lifespan diagnostics, updated as posts age out of the
    // For-You candidate window (pruneRecentPosts). Motivation: velocity ranking creates a
    // surfaced -> reposted -> stays-surfaced feedback loop (research-direction.md's self-
    // reinforcement risk); these track whether posts are naturally dying out well within
    // VELOCITY_WINDOW, or are still actively accumulating reposts when the hard window cutoff
    // forcibly evicts them (a sign the window is truncating real, ongoing virality rather than
    // measuring it). See docs/report/2026-07-29-feed-reach-redesign.md.
    private long lifespanSum = 0;         // sum of (lastRepostStep - postedStep) over reposted, evicted posts
    private int lifespanCount = 0;        // denominator for the above (posts with >=1 repost)
    private int stillActiveAtEvictionCount = 0; // of those, last repost was in the final 10% of the window
    // reshares of an agent's own posts, waiting to be shown to that agent (notify_original > 0); newest last
    private final java.util.ArrayDeque<Post>[] notifications;
    private static final int NOTIFY_BACKLOG = 50;

    /** A reshare {@code copy} of the post authored by {@code authorId} (the root author) is queued for that author's next feed. */
    public void notifyOriginal(int authorId, Post copy) {
        if (p.notifyMax() <= 0 || authorId == copy.getPostUserId()) return;
        java.util.ArrayDeque<Post> q = notifications[authorId];
        q.addLast(copy);
        while (q.size() > NOTIFY_BACKLOG) q.pollFirst();
    }

    /**
     * The user's extra candidate pool: alive, unseen reshares of the user's own posts. It is added to the pool every stream
     * draws from (and is exempt from the hop filter); slots and ranking rules are unchanged. Seen or dead entries are dropped.
     */
    private List<Post> extraPool(Agent user, int step) {
        List<Post> out = new ArrayList<>();
        if (p.notifyMax() <= 0) return out;
        java.util.Iterator<Post> it = notifications[user.getId()].iterator();
        while (it.hasNext()) {
            Post post = it.next();
            if (!post.isAlive(step, p.deadAfter()) || user.hasSeen(post)) it.remove(); else out.add(post);
        }
        return out;
    }

    private int evictedRepostedCount = 0; // denominator for the above (same as lifespanCount, kept separate for clarity)


    @SuppressWarnings("unchecked")
    public AdminOptim(int userNum, double[][] W, SimParams params) {
        this.n = userNum;
        this.p = params;
        this.followees = new HashSet[n];
        this.followers = new HashSet[n];
        this.followerNumArray = new int[n];
        this.notifications = new java.util.ArrayDeque[n];
        for (int i = 0; i < n; i++) notifications[i] = new java.util.ArrayDeque<>();
        for (int i = 0; i < n; i++) {
            followees[i] = new LinkedHashSet<>(); // insertion order = the follow queue (front = oldest)
            followers[i] = new HashSet<>();
        }
        for (int i = 0; i < n; i++) {
            List<Integer> outs = new ArrayList<>();
            for (int j = 0; j < n; j++) {
                if (W[i][j] > 0.0) {
                    outs.add(j);
                    followers[j].add(i);
                    followerNumArray[j]++;
                }
            }
            // initial queue order is random, not by id (id order would make rewire drop low ids first)
            Collections.shuffle(outs, randomGenerator.network());
            followees[i].addAll(outs);
        }
    }

    /** Front of agent's follow queue (the followee it has reacted to least recently), or null. */
    public Integer frontFollowee(int userId) {
        Iterator<Integer> it = followees[userId].iterator();
        return it.hasNext() ? it.next() : null;
    }

    /** Agent reacted to a post by {@code authorId}: if followed, move that followee to the back. */
    public void touchFollowee(int userId, int authorId) {
        if (followees[userId].remove(authorId)) followees[userId].add(authorId);
    }

    public double[][] getAdjacencyMatrix() {
        double[][] matrix = new double[n][n];
        for (int i = 0; i < n; i++) {
            for (int j : followees[i]) {
                matrix[i][j] = 1.0;
            }
        }
        return matrix;
    }

    public Set<Integer> getFollowees(int userId) {
        return followees[userId];
    }

    // R22: AdminOptim is the sole owner of the follow graph. Agents query/mutate via these.
    public boolean follows(int follower, int followee) {
        return followees[follower].contains(followee);
    }

    public int followeeCount(int userId) {
        return followees[userId].size();
    }

    /** Followees of userId in ascending id order — deterministic iteration for eviction. */
    public List<Integer> sortedFollowees(int userId) {
        List<Integer> list = new ArrayList<>(followees[userId]);
        Collections.sort(list);
        return list;
    }

    public void addFollowEdge(int follower, int followee) {
        if (followees[follower].add(followee)) {
            followers[followee].add(follower);
            followerNumArray[followee]++;
        }
    }

    public void removeFollowEdge(int follower, int followee) {
        if (followees[follower].remove(followee)) {
            followers[followee].remove(follower);
            followerNumArray[followee]--;
        }
    }

    public Set<Integer> getFollowers(int userId) {
        return followers[userId];
    }

    public int[] getFollowerList() {
        return this.followerNumArray.clone();
    }

    public List<Map.Entry<Integer, Integer>> getFollowerRanking() {
        List<Map.Entry<Integer, Integer>> rankingList = new ArrayList<>();

        for (int i = 0; i < n; i++) {
            rankingList.add(new AbstractMap.SimpleEntry<>(i, followerNumArray[i]));
        }

        rankingList.sort((a, b) -> Integer.compare(b.getValue(), a.getValue()));

        return rankingList;
    }

    public void setFollowerNumArray() {
        Arrays.fill(this.followerNumArray, 0);
        for (int i = 0; i < n; i++) {
            followerNumArray[i] = followers[i].size();
        }
    }

    // ================= Velocity-primary "For You" recommender =================

    /** Register a freshly-created original post into the For-You candidate window. */
    public void addRecentPost(Post post) {
        recentPosts.add(post);
        createdPostCount++;
    }

    public int getAlivePostCount() { return recentPosts.size(); }
    public long getCreatedPostCount() { return createdPostCount; }
    public long getDiedPostCount() { return diedPostCount; }
    public List<Post> getAlivePosts() { return recentPosts; }

    /**
     * Death sweep: a post is dead once {@code step - lastReactionStep > deadAfter}. Dead posts leave
     * the pool for good (a dead post is never seen or reshared again). Call once per step.
     */
    private final List<Post> evictedBuf = new ArrayList<>();

    /** Posts evicted by the last sweepDead (every dead post, reacted-to or not); drained by the caller once per step. */
    public List<Post> drainEvicted() {
        if (evictedBuf.isEmpty()) return List.of();
        List<Post> out = new ArrayList<>(evictedBuf);
        evictedBuf.clear();
        return out;
    }

    public void sweepDead(int step) {
        int L = p.deadAfter();
        Iterator<Post> it = recentPosts.iterator();
        while (it.hasNext()) {
            Post post = it.next();
            if (!post.isAlive(step, L)) {
                recordLifespan(post, step);
                evictedBuf.add(post);
                it.remove();
                diedPostCount++;
            }
        }
    }

    /** One per-post eviction event (dashboard/diagnostic logging) -- see drainLifespanEvents. */
    public record LifespanEvent(Post post, boolean stillActive) {}
    private final List<LifespanEvent> pendingLifespanEvents = new ArrayList<>();

    // 2026-07-29: lifespan/self-reinforcement diagnostics, recorded once per post at the moment it
    // ages out of the candidate window (see field comments above). Only posts that were ever
    // reposted count -- posts that never took off have no "life" to measure here (they're already
    // visible via originalPostCount/repostCount volume metrics elsewhere).
    private void recordLifespan(Post post, int evictionStep) {
        if (post.getReceivedReposts() <= 0) return;
        lifespanSum += (post.getLastRepostStep() - post.getPostedStep());
        lifespanCount++;
        evictedRepostedCount++;
        int quietSteps = evictionStep - post.getLastRepostStep();
        boolean stillActive = quietSteps <= Math.max(1, p.deadAfter() / 10);
        if (stillActive) stillActiveAtEvictionCount++;
        pendingLifespanEvents.add(new LifespanEvent(post, stillActive));
    }

    /**
     * Drain (and clear) lifespan-eviction events recorded since the last call. Caller (
     * OpinionDynamics) logs these to posts/post_lifespan.csv for the dashboard's top-reposted-
     * lifespan ranking; polled once per step alongside rankByVelocity so nothing is dropped.
     */
    public List<LifespanEvent> drainLifespanEvents() {
        if (pendingLifespanEvents.isEmpty()) return List.of();
        List<LifespanEvent> out = new ArrayList<>(pendingLifespanEvents);
        pendingLifespanEvents.clear();
        return out;
    }

    /** Mean (lastRepostStep - postedStep) over all evicted posts that received >=1 repost, cumulative to date. */
    public double getPostLifespanMean() {
        return lifespanCount > 0 ? lifespanSum / (double) lifespanCount : 0.0;
    }

    /**
     * Of evicted, reposted posts, the fraction still receiving reposts in the final 10% of
     * VELOCITY_WINDOW when forcibly evicted -- i.e. cut off mid-virality rather than having
     * organically gone quiet. High values here mean VELOCITY_WINDOW is truncating genuine ongoing
     * self-reinforcement, not just bounding candidate-pool memory.
     */
    public double getPostStillActiveAtEvictionFrac() {
        return evictedRepostedCount > 0 ? stillActiveAtEvictionCount / (double) evictedRepostedCount : 0.0;
    }

    // R11: per-post snapshot for windowed velocity — {repostsAtLastRank, stepAtLastRank}.
    private final Map<Integer, int[]> velSnapshot = new HashMap<>();

    // Cumulative ("soaring") velocity: cumulative reposts per unit time. Opinion-blind, and — as of
    // 2026-07-09 — deliberately NOT normalised by the author's follower count, superseding the
    // 2026-06-23 "anti-rich-get-richer" decision (research-direction.md §3 item 6). Reasoning for
    // the reversal: real engagement-ranked feeds (the recommender's actual referent) do not divide
    // by poster reach — a small account's post surfaces because its RAW engagement is large
    // relative to peers, not because the algorithm artificially discounts big accounts. Dividing by
    // (followers+1) was found to actively suppress the neutral hub's own content in the algorithmic
    // slots (docs/report/2026-07-09-oat-sweep-findings.md: alpha>0 made moderate-hub follower growth
    // reliably *worse*, confirmed at 10 seeds) — the opposite of the mechanism's intended role.
    // Known tradeoff, accepted: this also removes the throttle on the EXTREME hubs (the largest
    // accounts in the network), so it may entrench them further, not just help the neutral one —
    // watch for this in the re-run.
    private double velocityScore(Post post, int step) {
        int age = step - post.getPostedStep();
        return post.getReceivedReposts() / (age + 1.0) * timeDecayFactor(age);
    }

    // 2026-07-29: optional extra recency dampener (SimParams.feedTimeDecayTau), off by default (tau
    // <= 0 => factor 1, no behavior change from before this existed). Independent of the age
    // normalisation already in velocityScore/windowedVelocityScore above: that division makes the
    // score a RATE (reposts per step), which does not by itself guarantee an old-but-still-active
    // post gets surfaced less than a young one -- a sustained high repost rate keeps the rate high
    // indefinitely. This multiplies in an explicit exp(-age/tau) decay so raw age counts against a
    // post regardless of its current repost rate, as a direct, calibratable knob on the
    // self-reinforcement risk (see docs/report/2026-07-29-feed-reach-redesign.md).
    private double timeDecayFactor(int age) {
        double tau = p.feedTimeDecayTau();
        return tau > 0.0 ? Math.exp(-age / tau) : 1.0;
    }

    // R11: windowed velocity — reposts GAINED since the previous ranking pass, per elapsed step.
    // Demotes a stalled early-burst below a currently-rising post (a cumulative-average score
    // cannot). Snapshots updated by the caller after scoring. See velocityScore's comment above for
    // why this is no longer normalised by follower count (2026-07-09).
    private double windowedVelocityScore(Post post, int step) {
        int[] snap = velSnapshot.get(post.getPostId());
        int lastLikes = (snap == null) ? 0 : snap[0];
        int lastStep = (snap == null) ? post.getPostedStep() : snap[1];
        int gained = post.getReceivedReposts() - lastLikes;
        int dt = Math.max(1, step - lastStep);
        return gained / (double) dt * timeDecayFactor(step - post.getPostedStep());
    }

    // R11.1 (2026-07-16, DECIDED): the ranking refresh cadence, decoupled from VELOCITY_WINDOW
    // (candidate-pool lifetime, a different concept — see docs/report/2026-07-16-feed-mechanism-
    // design-review.md issue 1). Using VELOCITY_WINDOW itself as the refresh interval was rejected:
    // it would give each post ~1 scoring pass over its entire eligible lifetime (defeating windowed
    // mode's purpose) and freeze the delivered For-You list for the whole window. Instead, derive
    // it from 1/accessProb — the model's own "population turnover" timescale (SimParams.accessProb
    // doc comment) — so chrono's implicit accumulation window (postCash, gated by the same
    // accessProb check) and For-You's ranking cadence move at the same tempo.
    private int velocityRankInterval() {
        double ap = p.accessProb();
        return ap > 0.0 ? Math.max(1, (int) Math.round(1.0 / ap)) : 1;
    }

    /**
     * Return recent posts sorted by descending velocity (mode per config). Rescored/resorted only
     * every {@link #velocityRankInterval()} steps; intervening calls return the cached ranking
     * unchanged (see R11.1 above — gives windowedVelocityScore's dt a real, non-unit value).
     */
    public List<Post> rankByVelocity(int step) {
        if (cachedRanked != null && step - lastRankStep < velocityRankInterval()) {
            return cachedRanked;
        }
        List<Post> ranked = new ArrayList<>(recentPosts);
        boolean windowed = p.velMode().equals("windowed");
        // Precompute scores once (safe with the comparator; and windowed updates snapshots after).
        Map<Integer, Double> score = new HashMap<>();
        for (Post post : ranked) {
            score.put(post.getPostId(), windowed ? windowedVelocityScore(post, step)
                                                 : velocityScore(post, step));
        }
        if (windowed) {
            for (Post post : ranked) {
                velSnapshot.put(post.getPostId(), new int[]{post.getReceivedReposts(), step});
            }
            velSnapshot.keySet().retainAll(score.keySet()); // drop snapshots for expired posts
        }
        ranked.sort((a, b) -> Double.compare(score.get(b.getPostId()), score.get(a.getPostId())));
        cachedRanked = ranked;
        lastRankStep = step;
        return ranked;
    }

    // 2026-07-29: reach direction fixed to OUT-edges only (followees) -- "your For-You network is
    // who you (transitively) follow," not an undirected blob of followers-of-followers too.
    // Previously undirected (see git history), which the research-direction.md hop-direction
    // caveat flagged as an unresolved realism gap: a hub's huge in-degree (people following it)
    // should not, by itself, put every one of ITS followers' followers inside a random OTHER
    // agent's reach just because they all touch the hub as a followee-of-a-followee in either
    // direction. h<=0 means global (no spatial limit, decay disabled too -- see acceptProbability).
    private void ensureReachable(int step, int h, Set<Integer> excludeIds) {
        if (h <= 0) return; // global reach: no cache needed
        boolean stale = (reachDistCache == null) || (reachCachedH != h)
                || (step - reachCachedStep >= Const.REACH_REFRESH_INTERVAL);
        if (!stale) return;
        reachDistCache = computeReachable(h, excludeIds);
        reachCachedStep = step;
        reachCachedH = h;
    }

    // 2026-07-26: excludeIds are skipped entirely during BFS expansion -- never added to any
    // agent's reachable set (their own posts can't surface via anyone else's For-You feed) AND
    // never expanded through as an intermediate hop (they can't serve as a bridge connecting two
    // OTHER agents' h-hop neighborhoods either). This is "excluded from the network" for
    // hop-reachability purposes specifically, not just a post-authorship filter on the final
    // candidate list (the prior, narrower version of this feature) -- the follow graph itself
    // (`followees`/`followers`) is untouched; only what this BFS is willing to traverse through
    // changes. An excluded agent's OWN reachDistCache[src] is still computed normally (their own
    // feed as a reader is unaffected -- only how OTHERS reach them/through them changes).
    //
    // 2026-07-29: BFS now traverses followees[] only (directed out-edges: "src follows u, u follows
    // v, ..."), not followers[] too -- see comment on ensureReachable. Same asymptotic cost as the
    // old undirected version (actually slightly cheaper: half the edge set per node), still capped
    // at depth h, so this is not a computation-time regression. Distance (BFS layer, 1-based) is
    // recorded per node instead of a flat boolean, feeding acceptProbability's decay below.
    @SuppressWarnings("unchecked")
    private Map<Integer, Integer>[] computeReachable(int h, Set<Integer> excludeIds) {
        Map<Integer, Integer>[] reachDistCache = new HashMap[n];
        for (int src = 0; src < n; src++) {
            Map<Integer, Integer> dist = new HashMap<>();
            Deque<Integer> frontier = new ArrayDeque<>();
            frontier.add(src);
            dist.put(src, 0);
            for (int depth = 0; depth < h && !frontier.isEmpty(); depth++) {
                int sz = frontier.size();
                for (int f = 0; f < sz; f++) {
                    int u = frontier.poll();
                    for (int v : followees[u]) {
                        if (!excludeIds.contains(v) && !dist.containsKey(v)) {
                            dist.put(v, depth + 1);
                            frontier.add(v);
                        }
                    }
                }
            }
            dist.remove(src);
            reachDistCache[src] = dist;
        }
        return reachDistCache;
    }

    /** Distance-decay acceptance factor for a candidate d hops away (d >= 1); 1.0 in "hard" mode. */
    /** The hop term of the For You score: exp(-foryou_hop_lambda (d-1)); with the default (<0) the legacy feed_decay machinery. */
    private double hopTerm(int d) {
        if (hopTab == null) {
            double lam = p.foryouHopLambda();
            hopTab = new double[128];
            for (int k = 1; k < 128; k++) hopTab[k] = lam < 0.0 ? decayFactor(k) : Math.exp(-lam * (k - 1));
        }
        return hopTab[Math.min(d, 127)];
    }

    /** Hop distances (out-edges, depth <= h) from every reader, as flat byte arrays; excluded agents are neither reached nor traversed. */
    private void computeReachBytes(int h) {
        int[][] adj = new int[n][];
        for (int u = 0; u < n; u++) {
            adj[u] = new int[followees[u].size()];
            int k = 0;
            for (int v : followees[u]) adj[u][k++] = v;
        }
        byte[][] dist = new byte[n][n];
        int[] cnt = new int[n];
        int[] queue = new int[n];
        int hMax = Math.min(h, 126);
        for (int src = 0; src < n; src++) {
            byte[] d = dist[src];
            int head = 0, tail = 0;
            queue[tail++] = src;
            d[src] = 127; // visited marker, cleared below
            for (int depth = 0; depth < hMax && head < tail; depth++) {
                int levelEnd = tail;
                while (head < levelEnd) {
                    int u = queue[head++];
                    for (int v : adj[u]) {
                        if (!exclArr[v] && d[v] == 0) { d[v] = (byte) (depth + 1); queue[tail++] = v; }
                    }
                }
            }
            d[src] = 0;
            cnt[src] = tail - 1;
        }
        fyDist = dist;
        fyReachCount = cnt;
    }

    private double decayFactor(int d) {
        double lambda = p.feedDecayLambda();
        return switch (p.feedDecayMode()) {
            case "exp" -> Math.exp(-lambda * (d - 1));
            case "inverse" -> 1.0 / (1.0 + lambda * (d - 1));
            default -> 1.0;
        };
    }

    /**
     * Probability that a For-You candidate at hop distance {@code d} from {@code userId} is
     * accepted. h<=0 (global) or unreached-within-h => handled by the caller/cache. Modes (see
     * ExperimentConfig.feedDecayMode): "hard" reproduces the legacy binary cutoff (d<=h captured by
     * presence in reachDistCache already, so always 1.0 here); "exp"/"inverse" apply distance
     * decay, lambda=0 degenerating both to "no decay" (matches "hard").
     */
    private double acceptProbability(int userId, int authorId, int h) {
        if (h <= 0) return 1.0; // global: no spatial restriction, no decay
        if (reachDistCache == null) return 0.0;
        Integer d = reachDistCache[userId].get(authorId);
        if (d == null) return 0.0; // beyond the search-depth cap => treated as unreachable
        double lambda = p.feedDecayLambda();
        return switch (p.feedDecayMode()) {
            case "exp" -> Math.exp(-lambda * (d - 1));
            case "inverse" -> 1.0 / (1.0 + lambda * (d - 1));
            default -> 1.0; // "hard": presence within the depth-h cache already means d<=h
        };
    }

    // ================= For You: perspective-similarity recommender =================
    // The platform holds an estimate Xhat_i of every agent's X (random start, then pulled toward the X
    // of the posts the agent likes or reshares). For You ranks candidates by closeness to Xhat_i.

    private double[] xhat;                                   // platform's estimate of each agent's X
    private byte[][] fyDist;                                 // For You hop distances: fyDist[reader][author] = d >= 1 within reach, 0 = unreachable / self
    private int[] fyReachCount;                              // number of authors within each reader's For You reach
    private boolean[] exclArr;                               // algoExcludeIds as a flat lookup
    private double[] hopTab;                                 // hopTerm(d) for d = 0..127
    private int fyReachStep = -1, fyReachH = Integer.MIN_VALUE;
    private List<Post>[] postsByAuthor;                      // alive posts per author, rebuilt once per step
    private double[] fyW = new double[1024];                 // scratch buffers for one candidate scan
    private Post[] fyP = new Post[1024];

    /** Start the estimates at random X in [-1,1], independent of the true X. */
    public void initEstimates(java.util.Random rng) {
        xhat = new double[n];
        for (int i = 0; i < n; i++) xhat[i] = 2.0 * rng.nextDouble() - 1.0;
    }

    public double getEstimate(int i) { return xhat == null ? Double.NaN : xhat[i]; }

    /** Like or reshare of a post with X = xp: Xhat <- (1-rho) Xhat + rho xp. Post/rewire leave it unchanged. */
    public void updateEstimate(int i, double xp, double rho) {
        if (xhat == null) return;
        xhat[i] = (1.0 - rho) * xhat[i] + rho * xp;
    }

    /** Mean |Xhat_i - X_i| over the given agents (how far the platform's picture is from the truth). */
    public double meanEstimateError(Agent[] agents) {
        if (xhat == null) return Double.NaN;
        double s = 0; int c = 0;
        for (int i = 0; i < n; i++) {
            if (agents[i].getTarget()) continue;
            s += Math.abs(xhat[i] - agents[i].getOpinion());
            c++;
        }
        return c > 0 ? s / c : 0.0;
    }

    /** Rebuild the per-author index of alive posts (call once per step, after sweepDead). */
    @SuppressWarnings("unchecked")
    public void rebuildAuthorIndex() {
        if (postsByAuthor == null) {
            postsByAuthor = new List[n];
            for (int i = 0; i < n; i++) postsByAuthor[i] = new ArrayList<>();
        }
        for (List<Post> l : postsByAuthor) l.clear();
        for (Post post : recentPosts) postsByAuthor[post.getPostUserId()].add(post);
    }

    /**
     * Draw up to {@code slots} posts for {@code userId}, without replacement, with probability
     * proportional to exp(-beta |xr - X_post|) x decay(hop distance), over the alive posts of authors
     * within the For You reach (all authors when foryou_hop <= 0). Never the reader's own posts, posts already shown to the reader before, posts
     * whose root is already in the feed ({@code seenRoots}), or two posts of one root.
     */
    private void selectForYou(Agent user, Agent[] agentSet, int step, int slots, Set<Integer> seenRoots, List<Post> out, List<Post> extras) {
        if (postsByAuthor == null) return;
        int userId = user.getId();
        int h = p.foryouHopH();
        double xr = (p.foryouProfile() && xhat != null) ? xhat[userId] : agentSet[userId].getOpinion();
        double beta = p.foryouBeta();
        if (exclArr == null) {
            exclArr = new boolean[n];
            for (int id : p.algoExcludeIds()) exclArr[id] = true;
        }
        if (h > 0) {
            boolean stale = fyDist == null || fyReachH != h || step - fyReachStep >= Const.REACH_REFRESH_INTERVAL;
            if (stale) {
                computeReachBytes(h);
                fyReachStep = step;
                fyReachH = h;
            }
        }
        int m = 0;
        fyN = 0;
        int cap = p.foryouCandMax();
        byte[] reach = h > 0 ? fyDist[userId] : null;
        // Large reach (most authors reachable) + a cap: draw the candidate sample directly from the array of live posts by
        // rejection (alive, unseen, author within reach), so the cost is about the cap, not the number of live posts.
        boolean sampled = cap > 0 && (h <= 0 || fyReachCount[userId] * 4 >= n);
        if (sampled) {
            m = sampleCandidates(user, userId, step, seenRoots, reach, cap);
        } else if (h > 0) {
            for (int author = 0; author < n; author++) {
                if (reach[author] == 0 || exclArr[author]) continue;
                m = scanAuthor(user, postsByAuthor[author], hopTerm(reach[author]), step, seenRoots, m, true);
            }
        } else {
            for (int author = 0; author < n; author++) {
                if (author == userId || exclArr[author]) continue;
                m = scanAuthor(user, postsByAuthor[author], 1.0, step, seenRoots, m, true);
            }
        }
        // score = similarity x hop term, for the candidates that survived the (optional) cap
        for (int j = 0; j < m; j++) fyW[j] = Math.exp(-beta * Math.abs(xr - fyP[j].getPostOpinion())) * fyD[j];
        if (!extras.isEmpty()) { // reshares of the user's own posts: same weight rule, no hop decay, never capped; skip ones already scanned via their author
            int before = m;
            m = scanAuthor(user, extras, 1.0, step, seenRoots, m, false);
            for (int j = m - 1; j >= before; j--) {
                boolean dup = false;
                for (int k = 0; k < before; k++) if (fyP[k] == fyP[j]) { dup = true; break; }
                if (dup) { fyP[j] = fyP[m - 1]; fyD[j] = fyD[m - 1]; m--; }
                else fyW[j] = Math.exp(-beta * Math.abs(xr - fyP[j].getPostOpinion()));
            }
        }
        // weighted draws without replacement (inverse CDF over the scratch weights)
        for (int slot = 0; slot < slots && m > 0; slot++) {
            double total = 0.0;
            for (int j = 0; j < m; j++) total += fyW[j];
            if (total <= 0.0) break;
            double r = randomGenerator.dynamics().nextDouble() * total;
            double cum = 0.0;
            int pick = -1;
            for (int j = 0; j < m; j++) {
                if (fyW[j] <= 0.0) continue;
                cum += fyW[j];
                pick = j;
                if (r < cum) break;
            }
            if (pick < 0) break;
            Post chosen = fyP[pick];
            out.add(chosen);
            int root = chosen.getRootPostId();
            for (int j = 0; j < m; j++) if (fyP[j].getRootPostId() == root) fyW[j] = 0.0; // no second post of this root
        }
    }

    /**
     * Uniform random sample (rejection) of up to {@code cap} valid For You candidates from the live-post array: a drawn post is
     * kept if it is alive, not the reader's own, unseen, its root is not already in the feed, and its author is within reach
     * (all authors when {@code reach} is null). Stops after 30 x cap draws. Fills fyP / fyD (hop term of the author's distance).
     */
    private int sampleCandidates(Agent user, int userId, int step, Set<Integer> seenRoots, byte[] reach, int cap) {
        int total = recentPosts.size();
        if (total == 0) return 0;
        int deadAfter = p.deadAfter();
        java.util.Random rng = randomGenerator.dynamics();
        Set<Integer> picked = new HashSet<>();
        int m = 0;
        for (int tries = 0, maxTries = 30 * cap; tries < maxTries && m < cap; tries++) {
            Post post = recentPosts.get(rng.nextInt(total));
            int author = post.getPostUserId();
            if (author == userId || exclArr[author]) continue;
            if (!post.isAlive(step, deadAfter) || user.hasSeen(post) || seenRoots.contains(post.getRootPostId())) continue;
            double hop = 1.0;
            if (reach != null) {
                int d = reach[author];
                if (d == 0) continue;
                hop = hopTerm(d);
            }
            if (!picked.add(post.getPostId())) continue;
            if (m == fyW.length) {
                fyW = java.util.Arrays.copyOf(fyW, m * 2);
                fyP = java.util.Arrays.copyOf(fyP, m * 2);
                fyD = java.util.Arrays.copyOf(fyD, m * 2);
            }
            fyP[m] = post;
            fyD[m] = hop;
            fyW[m] = 0.0;
            m++;
        }
        return m;
    }

    private int fyN;                                         // valid candidates seen in the current scan (for reservoir sampling)
    private double[] fyD = new double[1024];                 // hop-decay factor per scratch candidate

    /**
     * Append the valid candidates of {@code posts} (alive, unseen, root not already in the feed) to the scratch arrays.
     * When {@code capped} and foryou_cand_max > 0, the scratch holds a uniform random sample (reservoir) of at most that many
     * candidates out of everything the hop filter let through; weights are computed afterwards, only for the survivors.
     */
    private int scanAuthor(Agent user, List<Post> posts, double decay, int step, Set<Integer> seenRoots, int m, boolean capped) {
        int deadAfter = p.deadAfter();
        int cap = capped ? p.foryouCandMax() : 0;
        for (Post post : posts) {
            if (!post.isAlive(step, deadAfter)) continue;
            if (seenRoots.contains(post.getRootPostId()) || user.hasSeen(post)) continue;
            if (capped) fyN++;
            int slot;
            if (cap > 0 && m >= cap) {
                slot = randomGenerator.dynamics().nextInt(fyN);
                if (slot >= cap) continue;
            } else {
                if (m == fyW.length) {
                    fyW = java.util.Arrays.copyOf(fyW, m * 2);
                    fyP = java.util.Arrays.copyOf(fyP, m * 2);
                    fyD = java.util.Arrays.copyOf(fyD, m * 2);
                }
                slot = m++;
            }
            fyP[slot] = post;
            fyD[slot] = decay;
            fyW[slot] = 0.0;
        }
        return m;
    }

    /**
     * Build user {@code userId}'s feed for this step: floor(alpha*S) For-You slots
     * (velocity-ranked, opinion-blind, reachable within h hops) + remainder chronological
     * from follows. {@code velocityRanked} is the per-step global ranking (null when
     * alpha=0, in which case this reduces to the legacy chronological feed).
     * {@code stepStats} accumulates feed-composition-by-camp counts (chrono/For-You x
     * repost/original, split by reader's 5-bin opinionClass) for population agents.
     */
    public void AdminFeedback(int userId, Agent[] agentSet, int step, List<Post> velocityRanked, StepStats stepStats) {
        Agent user = agentSet[userId];
        int deadAfter = p.deadAfter();

        // reshares of the user's own posts join every stream's candidate pool (hop-exempt); slots are unchanged
        List<Post> extras = extraPool(user, step);
        Set<Integer> extraIds = new HashSet<>();
        for (Post post : extras) extraIds.add(post.getPostId());
        int capacity = p.feedCapacity();
        int algoSlots = (int) Math.floor(p.trendShare() * capacity);         // Trend slots
        int fySlots = (int) Math.floor(p.foryouShare() * capacity);          // For You slots
        int chronoSlots = capacity - algoSlots - fySlots;

        // ---- chronological-from-follows stream (legacy substrate) ----
        // Uniform sample of the postCash window (PostCash itself is a fixed-size FIFO, so
        // staleness is already bounded there regardless of how we sample here). Dedup by
        // rootPostId: multiple followees relaying the same story each broadcast a distinct
        // Post object (fresh postId, shared rootPostId, see Agent.relay()/Post.relayOf), so
        // without this a widely-relayed story could occupy multiple chrono slots and receive
        // multiplicity-weighted selection probability under the shuffle below — an implicit,
        // unintended popularity signal leaking into the "popularity-blind" chrono channel.
        List<Post> chrono = new ArrayList<>();
        List<Post> chronoCandidates = new ArrayList<>();
        for (Post post : user.getPostCash().getAllPosts()) {
            if (post.isAlive(step, deadAfter) && !user.hasSeen(post)) chronoCandidates.add(post);
        }
        // (notified copies reach chrono through the author's postCash, delivered like any followee post; extras serve For You only)
        Collections.shuffle(chronoCandidates, randomGenerator.dynamics());
        Set<Integer> seenRoots = new HashSet<>();
        for (Post post : chronoCandidates) {
            if (chrono.size() >= chronoSlots) break;
            if (seenRoots.add(post.getRootPostId())) chrono.add(post);
        }

        // ---- For You (perspective-similarity) stream ----
        // Personalised by X, not by popularity: candidates are the alive posts of authors within the
        // For You reach, drawn without replacement with weight exp(-beta |Xhat_i - X_post|) (x the
        // reach decay acceptance). Taken before Trend so a post is never in two streams.
        List<Post> forYouPersonal = new ArrayList<>();
        if (fySlots > 0) {
            selectForYou(user, agentSet, step, fySlots, seenRoots, forYouPersonal, extras);
            for (Post post : forYouPersonal) seenRoots.add(post.getRootPostId());
        }

        // ---- Trend (velocity-primary, popularity) stream ----
        List<Post> forYou = new ArrayList<>(); // the Trend stream
        if (algoSlots > 0 && velocityRanked != null && !velocityRanked.isEmpty()) {
            int h = p.trendHopH();
            ensureReachable(step, h, p.algoExcludeIds());
            // velocityRanked candidates are always originals (rootPostId == postId, see
            // AdminOptim.addRecentPost), so comparing against chrono's rootPostIds catches a
            // relayed copy of the same story occupying a chrono slot too.
            for (Post post : velocityRanked) {
                if (forYou.size() >= algoSlots) break;
                int author = post.getPostUserId();
                if (author == userId) continue;            // not your own post
                if (!post.isAlive(step, deadAfter)) continue; // forgotten posts are gone
                if (user.hasSeen(post)) continue;             // each post is shown to an agent at most once
                // 2026-07-26: bridging-role isolation -- author excluded from algorithmic surfacing
                // specifically; organic/chrono reach to them (if the reader follows them) is untouched.
                if (p.algoExcludeIds().contains(author)) continue;
                if (seenRoots.contains(post.getRootPostId())) continue; // avoid duplicate slot
                // 2026-07-29: hard hop cutoff replaced by a distance-decay ACCEPTANCE PROBABILITY --
                // stochastic thinning over the velocity-sorted scan, so higher-velocity candidates
                // are still preferred first (order untouched), but farther candidates are less
                // likely to fill a slot rather than flatly excluded. Skips the RNG draw at p=1.0
                // (h<=0 or "hard" mode within range) to avoid burning draws in the common case.
                double pAccept = extraIds.contains(post.getPostId()) ? 1.0 : acceptProbability(userId, author, h);
                if (pAccept <= 0.0) continue;
                if (pAccept < 1.0 && randomGenerator.dynamics().nextDouble() >= pAccept) continue;
                forYou.add(post);
                seenRoots.add(post.getRootPostId()); // a reshare and its source never share a slot
            }
        }

        // Feed-composition-by-camp bookkeeping (population agents only, R1-style hub exclusion).
        // Must happen here, before chrono/forYou are merged below: channel provenance isn't
        // retained on Post/Agent.feed once delivered, so this is the only point it's knowable.
        // camp = reader's 5-bin opinionClass (matches feedPostOpinionMean_i/cRateMean_i convention).
        if (!user.getTarget()) {
            int cls = user.getOpinionClass();
            stepStats.feedClassAgentCount[cls]++;
            stepStats.feedTrendCountSum[cls] += forYou.size();
            stepStats.feedForYouCountSum[cls] += forYouPersonal.size();
            stepStats.feedChronoCountSum[cls] += chrono.size();
            int repostCount = 0, originalCount = 0;
            // 2026-08-06: author-hub-tier tally (StepStats.feedNeutCountSum/feedHubCountSum
            // javadoc) -- rel_attrib=original keeps postUserId as the original creator, so this is
            // "authored by," not "relayed by."
            int neutCount = 0, hubCount = 0;
            for (Post post : chrono) {
                if (post.isRelay()) repostCount++; else originalCount++;
                Agent author = agentSet[post.getPostUserId()];
                int authorTier = author.getHubTier();
                if (authorTier >= 0) { hubCount++; if (authorTier == 2) neutCount++; }
                stepStats.feedAuthorClassCountSum[cls][author.getOpinionClass()]++;
            }
            List<Post> algoPosts = new ArrayList<>(forYou);
            algoPosts.addAll(forYouPersonal);
            for (Post post : algoPosts) {
                if (post.isRelay()) repostCount++; else originalCount++;
                Agent author = agentSet[post.getPostUserId()];
                int authorTier = author.getHubTier();
                if (authorTier >= 0) { hubCount++; if (authorTier == 2) neutCount++; }
                stepStats.feedAuthorClassCountSum[cls][author.getOpinionClass()]++;
            }
            stepStats.feedRepostCountSum[cls] += repostCount;
            stepStats.feedOriginalCountSum[cls] += originalCount;
            stepStats.feedNeutCountSum[cls] += neutCount;
            stepStats.feedHubCountSum[cls] += hubCount;
        }

        // 2026-07-30: record which rootPostIds this step's forYou stream delivered, so a later
        // repost() call this same step can tag the relay's channel provenance -- the only point
        // this is knowable (chrono/forYou are merged+shuffled into feed right below, see the
        // channel-provenance comment above). chrono/forYou are mutually exclusive by rootPostId
        // (forYou's build loop skips anything already in chrono's seenRoots), so membership here
        // is unambiguous.
        Set<Integer> forYouRoots = new HashSet<>();
        for (Post post : forYou) forYouRoots.add(post.getRootPostId());
        for (Post post : forYouPersonal) forYouRoots.add(post.getRootPostId());
        user.setAlgoRootIds(forYouRoots);

        // ---- deliver: chronological + For-You, order-neutral for reading ----
        List<Post> feed = new ArrayList<>(chrono);
        feed.addAll(forYou);
        feed.addAll(forYouPersonal);
        Collections.shuffle(feed, randomGenerator.dynamics());
        for (Post post : feed) {
            user.addPostToFeed(post);
        }
    }

    public List<Integer> getTopInfluencers(int topK) {
        List<Map.Entry<Integer, Integer>> rankingList = getFollowerRanking();
        List<Integer> topInfluencers = new ArrayList<>();

        for (int i = 0; i < Math.min(topK, rankingList.size()); i++) {
            topInfluencers.add(rankingList.get(i).getKey());
        }

        return topInfluencers;
    }

}
