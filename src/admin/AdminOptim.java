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
    private final Deque<Post> recentPosts = new ArrayDeque<>();
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
    private int evictedRepostedCount = 0; // denominator for the above (same as lifespanCount, kept separate for clarity)


    @SuppressWarnings("unchecked")
    public AdminOptim(int userNum, double[][] W, SimParams params) {
        this.n = userNum;
        this.p = params;
        this.followees = new HashSet[n];
        this.followers = new HashSet[n];
        this.followerNumArray = new int[n];
        for (int i = 0; i < n; i++) {
            followees[i] = new HashSet<>();
            followers[i] = new HashSet<>();
        }
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < n; j++) {
                if (W[i][j] > 0.0) {
                    followees[i].add(j);
                    followers[j].add(i);
                    followerNumArray[j]++;
                }
            }
        }
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

    public void updateAdjacencyMatrix(int userId, int[] followedIds, int unfollowedId) {
        if (followedIds[0] >= 0) {
            followees[userId].add(followedIds[0]);
            followers[followedIds[0]].add(userId);
            followerNumArray[followedIds[0]]++;
        }
        if (followedIds[1] >= 0) {
            followees[userId].remove(followedIds[1]);
            followers[followedIds[1]].remove(userId);
            followerNumArray[followedIds[1]]--;
        }
        if (unfollowedId >= 0) {
            followees[userId].remove(unfollowedId);
            followers[unfollowedId].remove(userId);
            followerNumArray[unfollowedId]--;
        }
    }

    // ================= Velocity-primary "For You" recommender =================

    /** Register a freshly-created original post into the For-You candidate window. */
    public void addRecentPost(Post post) {
        recentPosts.addLast(post);
    }

    /** Drop posts older than the velocity window from the candidate pool. */
    private void pruneRecentPosts(int step) {
        int cutoff = step - Const.VELOCITY_WINDOW;
        while (!recentPosts.isEmpty() && recentPosts.peekFirst().getPostedStep() < cutoff) {
            recordLifespan(recentPosts.removeFirst(), step);
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
        boolean stillActive = quietSteps <= Const.VELOCITY_WINDOW / 10;
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
        pruneRecentPosts(step);
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
        computeReachable(h, excludeIds);
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
    private void computeReachable(int h, Set<Integer> excludeIds) {
        reachDistCache = new HashMap[n];
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
        boolean[] blocked = user.getBlockedUserList();

        int capacity = p.feedCapacity();
        int algoSlots = (int) Math.floor(p.feedAlgoShare() * capacity);
        int chronoSlots = capacity - algoSlots;

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
            if (!blocked[post.getPostUserId()]) chronoCandidates.add(post);
        }
        Collections.shuffle(chronoCandidates, randomGenerator.dynamics());
        Set<Integer> seenRoots = new HashSet<>();
        for (Post post : chronoCandidates) {
            if (chrono.size() >= chronoSlots) break;
            if (seenRoots.add(post.getRootPostId())) chrono.add(post);
        }

        // ---- For-You (velocity-primary) stream ----
        List<Post> forYou = new ArrayList<>();
        if (algoSlots > 0 && velocityRanked != null && !velocityRanked.isEmpty()) {
            int h = p.feedHopH();
            ensureReachable(step, h, p.algoExcludeIds());
            // velocityRanked candidates are always originals (rootPostId == postId, see
            // AdminOptim.addRecentPost), so comparing against chrono's rootPostIds catches a
            // relayed copy of the same story occupying a chrono slot too.
            for (Post post : velocityRanked) {
                if (forYou.size() >= algoSlots) break;
                int author = post.getPostUserId();
                if (author == userId) continue;            // not your own post
                if (blocked[author]) continue;             // respect blocks (self-limiting filter)
                // 2026-07-26: bridging-role isolation -- author excluded from algorithmic surfacing
                // specifically; organic/chrono reach to them (if the reader follows them) is untouched.
                if (p.algoExcludeIds().contains(author)) continue;
                if (seenRoots.contains(post.getRootPostId())) continue; // avoid duplicate slot
                // 2026-07-29: hard hop cutoff replaced by a distance-decay ACCEPTANCE PROBABILITY --
                // stochastic thinning over the velocity-sorted scan, so higher-velocity candidates
                // are still preferred first (order untouched), but farther candidates are less
                // likely to fill a slot rather than flatly excluded. Skips the RNG draw at p=1.0
                // (h<=0 or "hard" mode within range) to avoid burning draws in the common case.
                double pAccept = acceptProbability(userId, author, h);
                if (pAccept <= 0.0) continue;
                if (pAccept < 1.0 && randomGenerator.dynamics().nextDouble() >= pAccept) continue;
                forYou.add(post);
            }
        }

        // Feed-composition-by-camp bookkeeping (population agents only, R1-style hub exclusion).
        // Must happen here, before chrono/forYou are merged below: channel provenance isn't
        // retained on Post/Agent.feed once delivered, so this is the only point it's knowable.
        // camp = reader's 5-bin opinionClass (matches feedPostOpinionMean_i/cRateMean_i convention).
        if (!user.getTarget()) {
            int cls = user.getOpinionClass();
            stepStats.feedClassAgentCount[cls]++;
            stepStats.feedForYouCountSum[cls] += forYou.size();
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
            for (Post post : forYou) {
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
        user.setForYouRootIds(forYouRoots);

        // ---- deliver: chronological + For-You, order-neutral for reading ----
        List<Post> feed = new ArrayList<>(chrono);
        feed.addAll(forYou);
        Collections.shuffle(feed, randomGenerator.dynamics());
        for (Post post : feed) {
            user.addPostToFeed(post); // re-checks blockedUserList; block-on-For-You handled by unfollow()
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
