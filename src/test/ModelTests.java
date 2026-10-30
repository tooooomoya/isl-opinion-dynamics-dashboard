package test;

import admin.AdminOptim;
import agent.Agent;
import agent.Post;
import analysis.Analysis;
import analysis.SparseIntMatrix;
import dynamics.StepStats;
import experiment.ExperimentConfig;
import experiment.SimParams;
import java.util.List;
import rand.randomGenerator;

/**
 * Lightweight assertion harness for the attention-economy mechanisms (no JUnit dependency):
 *   java -cp bin test.ModelTests
 * Exits non-zero if any check fails. End-to-end properties (out-degree conservation over a full
 * run, action-share trajectories) are covered by the AssertionCheck inside a real run.
 */
public class ModelTests {

    private static int failures = 0;

    private static void check(boolean cond, String name) {
        if (cond) {
            System.out.println("  PASS  " + name);
        } else {
            System.out.println("  FAIL  " + name);
            failures++;
        }
    }

    private static SimParams params(String... tokens) {
        return SimParams.from(ExperimentConfig.fromArgs(tokens));
    }

    public static void main(String[] args) {
        randomGenerator.init(0, 0);
        System.out.println("== ModelTests ==");

        testConfigRoundTrip();
        testTag();
        testPostLifecycle();
        testReshareCreditsResharer();
        testSimilarityAndIdentityFit();
        testRecognition();
        testReshareCreditAndLife();
        testQUpdate();
        testEqualStartEquiprobable();
        testExplorationFloor();
        testActionAvailability();
        testPickFavoursSimilar();
        testOneReactionPerPost();
        testQTargetUsesAvailableActions();
        testRewardWeights();
        testRawFitHasCommonBaseline();
        testRelativeFit();
        testFollowQueue();
        testRewire();
        testWattsStrogatzStart();
        testHomophilyStart();
        testDirectedBAStart();
        testStartDegreeRegulation();
        testLikeGate();
        testDeathSweep();
        testDriftOffByDefault();
        testUniformInit();
        testEmpiricalInit();
        testCalibrationWindows();
        testVelocityRankingCache();
        testTrendCountAndTie();
        testChronoRootDedup();
        testDeadPostsLeaveFeed();
        testForYou();
        testEachPostShownOnce();
        testNotifyOriginal();
        testPostNoise();
        testForYouCandidateCap();
        testForYouHopTerm();
        testNeutralBandExcludesEdgesEntirely();

        System.out.println(failures == 0 ? "ALL PASS" : (failures + " FAILURE(S)"));
        if (failures > 0) System.exit(1);
    }

    private static void testEmpiricalInit() {
        System.out.println("[deduplicated empirical ideology initialization]");
        randomGenerator.init(1827, 1827);
        int[] bins = new int[7];
        SimParams p = params("init_dist=empirical");
        for (int i = 0; i < 20000; i++) bins[Agent.opinionToBin7(new Agent(0, p).getIntrinsicOpinion())]++;
        int[] target = constants.Const.EMPIRICAL_UNIQUE_OPINION_BIN_COUNTS;
        for (int i = 0; i < 7; i++) check(Math.abs(bins[i] / 20000.0 - target[i] / 762.0) < 0.015,
                "empirical bin " + i + " uses unique-person weights");
    }

    private static void testCalibrationWindows() {
        System.out.println("[exact calibration windows and reshare attribution]");
        try {
            java.nio.file.Path dir = java.nio.file.Files.createTempDirectory("calibration-test-");
            Agent[] agents = {new Agent(0, params()), new Agent(1, params()), new Agent(2, params())};
            analysis.CalibrationLog log = new analysis.CalibrationLog(3);
            log.original(0); log.visit(0); log.reshare(1, 0, 0); log.reshare(2, 1, 0);
            log.flush(5000, agents, dir);
            String root = java.nio.file.Files.readString(dir.resolve("calibration_root_5000.csv"));
            String immediate = java.nio.file.Files.readString(dir.resolve("calibration_immediate_5000.csv"));
            check(root.contains("0,2,1") && immediate.contains("1,2,1"), "copy chains preserve separate root and immediate graphs");
            log.flush(10000, agents, dir);
            String activity = java.nio.file.Files.readString(dir.resolve("calibration_activity.csv"));
            check(activity.lines().count() == 7 && activity.contains("5000,10000,0,"), "zero-activity agents and exact window boundaries logged");
            check(java.nio.file.Files.readString(dir.resolve("calibration_root_10000.csv")).lines().count() == 1,
                    "events reset at the window boundary");
            try (var paths = java.nio.file.Files.list(dir)) {
                for (var path : paths.toList()) java.nio.file.Files.delete(path);
            }
            java.nio.file.Files.delete(dir);
        } catch (java.io.IOException e) { throw new java.io.UncheckedIOException(e); }
    }

    private static void testConfigRoundTrip() {
        System.out.println("[config round-trip]");
        ExperimentConfig c = ExperimentConfig.fromArgs(new String[]{
            "seed=7", "net_seed=42", "beta_h=2.5", "dead_after=80", "l_ref=100", "q_eta=0.2",
            "q_gamma=0.5", "q_tau=0.3", "mu=0.01", "network=ba", "n=500", "steps=1234",
            "i_edge_lo=0.5", "i_edge_hi=0.8", "bc_dec=0.9", "p_u=0.3" /* removed knobs: must be ignored */
        });
        check(c.seed == 7 && c.resolvedNetSeed() == 42, "seed / net_seed");
        check(c.betaH == 2.5 && c.deadAfter == 80 && c.lRef == 100.0, "beta_h / dead_after / l_ref");
        check(c.qEta == 0.2 && c.qGamma == 0.5 && c.qTau == 0.3, "Q-learning knobs");
        check(c.mu == 0.01 && c.networkType.equals("ba") && c.n == 500 && c.steps == 1234, "mu / network / n / steps");
        check(c.iEdgeLo == 0.5 && c.iEdgeHi == 0.8, "state-bin edges");
        ExperimentConfig d = ExperimentConfig.fromArgs(new String[]{});
        check(d.mu == 0.0 && d.initOpinionDist.equals("uniform"), "defaults: mu = 0, uniform init");
    }

    private static void testTag() {
        System.out.println("[tag]");
        ExperimentConfig def = ExperimentConfig.fromArgs(new String[]{});
        check(def.tag().equals("ext-NONE_nneutral-0_size-LARGEST_ch-BOTH"), "default tag is the base string");
        ExperimentConfig a = ExperimentConfig.fromArgs(new String[]{"beta_h=5"});
        ExperimentConfig b = ExperimentConfig.fromArgs(new String[]{"dead_after=20", "q_eta=0.3"});
        check(a.tag().contains("_bh-") && !def.tag().contains("_bh-"), "beta_h tagged only when non-default");
        check(b.tag().contains("_L-20") && b.tag().contains("_qeta-"), "multiple knobs tagged");
        check(!a.tag().equals(b.tag()) && !a.tag().equals(def.tag()), "distinct configs => distinct tags");
        ExperimentConfig sampled = ExperimentConfig.fromArgs(new String[]{"metrics_every=100", "calibration_log=true"});
        check(sampled.tag().contains("_me-100_calib"), "optional measurement settings have distinct result tags");
    }

    private static void testPostLifecycle() {
        System.out.println("[post lifecycle]");
        Post orig = new Post(5, 0.8, 100);
        check(!orig.isRelay() && orig.getDepth() == 0 && orig.getRootPostId() == orig.getPostId()
                && orig.getParentPostId() == -1 && orig.getLikesReceived() == 0, "original defaults");
        check(orig.isAlive(150, 50) && !orig.isAlive(151, 50), "alive for exactly deadAfter steps after creation");
        orig.like(140);
        check(orig.getLikesReceived() == 1 && orig.isAlive(190, 50) && !orig.isAlive(191, 50),
                "a like refreshes the post's life");
        orig.receiveRepost(180);
        check(orig.getReceivedReposts() == 1 && orig.isAlive(230, 50), "a reshare refreshes the source's life");
    }

    private static void testReshareCreditsResharer() {
        System.out.println("[reshare is a post authored by the resharer]");
        Post src = new Post(3, 0.5, 0);
        Post copy = Post.reshareOf(src, 8, 10, false);
        check(copy.getPostUserId() == 8 && copy.getRelayerId() == 8, "author of the copy is the resharer");
        check(copy.getPostOpinion() == src.getPostOpinion(), "X is the source's X, undistorted");
        check(copy.getRootPostId() == src.getPostId() && copy.getParentPostId() == src.getPostId()
                && copy.getDepth() == 1 && copy.getPostedStep() == 10, "lineage kept; creation step = reshare step");
        copy.like(12);
        check(copy.getLikesReceived() == 1 && src.getLikesReceived() == 0,
                "a like on the copy is the resharer's, not the source author's");
    }

    private static void testSimilarityAndIdentityFit() {
        System.out.println("[similarity and identity fit]");
        check(Agent.similarity(0.3, 0.3) == 1.0 && Agent.similarity(-1, 1) == 0.0
                && Math.abs(Agent.similarity(0.0, 0.5) - 0.75) < 1e-12, "sim = 1 - |dx|/2");
        SimParams p = params();
        Agent a = new Agent(0, p);
        a.setOpinion(0.0);
        check(a.identityFit() == 0.0, "empty feed => identity fit 0");
        a.addPostToFeed(new Post(1, 0.0, 0));   // sim 1
        a.addPostToFeed(new Post(2, 1.0, 0));   // sim 0.5
        check(Math.abs(a.identityFit() - 0.75) < 1e-12, "identity fit = mean similarity over the feed");
    }

    private static void testRecognition() {
        System.out.println("[recognition]");
        SimParams p = params("l_ref=99", "dead_after=50", "recog_mix=0");
        Agent a = new Agent(0, p);
        Post post = a.makePost(0);
        for (int i = 0; i < 9; i++) post.like(1);
        double expected = Math.log(10.0) / Math.log(100.0); // ln(1+9)/ln(1+99)
        check(Math.abs(a.recognition(2) - expected) < 1e-12, "recognition = ln(1+likes)/ln(1+L_ref)");
        for (int i = 0; i < 1000; i++) post.like(2);
        check(a.recognition(3) == 1.0, "recognition saturates at 1 above L_ref");
        check(a.recognition(200) == 0.0, "after the post dies its likes stop counting");
        // mixed form: 1 like is worth much more than under the pure log; influencers still differ
        SimParams q = params("l_ref=1000", "recog_lambda=2", "recog_mix=0.5", "dead_after=50");
        Agent b = new Agent(0, q);
        Post bp = b.makePost(0);
        bp.like(1);
        double one = 0.5 * (1 - Math.exp(-0.5)) + 0.5 * Math.log(2.0) / Math.log(1001.0);
        check(Math.abs(b.recognition(2) - one) < 1e-12 && one > 0.2, "mixed recognition: one like is worth > 0.2");
        for (int i = 0; i < 99; i++) bp.like(2);
        double r100 = b.recognition(3);
        for (int i = 0; i < 900; i++) bp.like(3);
        double r1000 = b.recognition(4);
        check(r1000 > r100 + 0.15 && r1000 <= 1.0, "influencers still differ: 1000 likes rewards more than 100");
    }

    private static void testReshareCreditAndLife() {
        System.out.println("[likes on a reshare: credit to the resharer only, the original's life is refreshed]");
        SimParams p = params("l_ref=99", "dead_after=50", "recog_mix=0");
        Agent author = new Agent(0, p), relayer = new Agent(1, p);
        Post src = author.makePost(0);
        Post copy = Post.reshareOf(src, 1, 1, false);
        relayer.getOwnPosts().add(copy);
        for (int i = 0; i < 8; i++) copy.like(30);
        check(copy.getLikesReceived() == 8 && src.getLikesReceived() == 0, "the copy's likes stay on the copy");
        check(author.recognition(40) == 0.0, "the original's author gets no credit from likes on a reshare");
        check(Math.abs(relayer.recognition(40) - Math.log1p(8) / Math.log(100.0)) < 1e-12, "the resharer gets all of them");
        check(src.isAlive(60, 50) && !src.isAlive(81, 50), "a like on the copy refreshes the original's life like a like on itself");
    }

    private static void testQUpdate() {
        System.out.println("[Q update]");
        SimParams p = params("q_eta=0.5", "q_gamma=0.9");
        Agent a = new Agent(0, p);
        a.setOpinion(0.0);
        int s0 = a.observeAndLearn(1);          // empty feed, no posts => state (low, low) = 0
        check(s0 == 0, "empty feed + no posts => state 0");
        int act = a.chooseAction(s0);
        a.addPostToFeed(new Post(1, 0.0, 0));   // identical X => identity fit 1
        int s1 = a.observeAndLearn(2);          // next visit: fit 1 (high), recognition 0 => state 6
        check(s1 == 6, "identity fit 1, recognition 0 => state (high, low) = 6");
        check(Math.abs(a.getQ()[0][act] - 0.5) < 1e-12,
                "Q(s,a) += eta*(r + gamma*max Q' - Q) = 0.5*(1 + 0 - 0)");
        double other = 0.0;
        for (int k = 0; k < Agent.NUM_ACTIONS; k++) if (k != act) other += Math.abs(a.getQ()[0][k]);
        check(other == 0.0, "only the action taken is updated");
    }

    private static void testEqualStartEquiprobable() {
        System.out.println("[equal start => equiprobable actions]");
        randomGenerator.init(11, 11);
        SimParams p = params("q_eta=0.0", "q_eps=0.0");
        Agent a = new Agent(0, p);
        a.addPostToFeed(new Post(1, 0.1, 0));
        int[] cnt = new int[Agent.NUM_ACTIONS];
        int N = 8000;
        for (int i = 0; i < N; i++) cnt[a.chooseAction(0)]++;
        boolean ok = true;
        for (int c : cnt) if (Math.abs(c / (double) N - 0.25) > 0.03) ok = false;
        check(ok, "with equal Q all four actions are chosen ~25% of the time");
    }

    // With a dominant action and a small floor, the others are still tried at about eps/available each.
    private static void testExplorationFloor() {
        System.out.println("[exploration floor]");
        randomGenerator.init(21, 21);
        Agent a = new Agent(0, params("q_tau=0.01", "q_eps=0.08", "q_eta=0.0"));
        a.addPostToFeed(new Post(1, 0.1, 0));
        a.getQ()[0][Agent.POST] = 10.0;   // post looks far better; softmax alone would choose it ~always
        int[] cnt = new int[Agent.NUM_ACTIONS];
        int N = 20000;
        for (int i = 0; i < N; i++) cnt[a.chooseAction(0)]++;
        double others = (cnt[1] + cnt[2] + cnt[3]) / (double) N;
        check(Math.abs(others - 0.08 * 0.75) < 0.01, "other actions chosen ~ eps*(3/4) of the time despite a large Q gap");
        Agent b = new Agent(0, params("q_tau=0.01", "q_eps=0.0", "q_eta=0.0"));
        b.addPostToFeed(new Post(1, 0.1, 0));
        b.getQ()[0][Agent.POST] = 10.0;
        int off = 0;
        for (int i = 0; i < 2000; i++) if (b.chooseAction(0) != Agent.POST) off++;
        check(off == 0, "eps = 0 => pure softmax, no exploration beyond the Q gap");
        Agent c = new Agent(0, params("q_eps=1.0"));      // no feed: only post and rewire available
        boolean badAction = false;
        for (int i = 0; i < 500; i++) { int act = c.chooseAction(0); if (act == Agent.LIKE || act == Agent.RESHARE) badAction = true; }
        check(!badAction, "exploration never picks an unavailable action");
    }

    private static void testOneReactionPerPost() {
        System.out.println("[one reaction per post]");
        SimParams p = params("n=4", "q_eps=1.0");
        AdminOptim admin = graph(p, 4, new int[][]{{0, 1}});
        Agent a = new Agent(0, p);
        Post src = new Post(1, 0.0, 0);
        a.addPostToFeed(src);
        check(a.pickFromFeed(Agent.LIKE) == src, "an unliked post can be picked for a like");
        a.like(src, 1, admin);
        check(src.getLikesReceived() == 1, "first like counted");
        check(a.pickFromFeed(Agent.LIKE) == null, "a post already liked cannot be picked again");
        boolean sawLike = false;
        for (int i = 0; i < 500; i++) if (a.chooseAction(0) == Agent.LIKE) sawLike = true;
        check(!sawLike, "like is unavailable when every feed post is already liked");
        a.reshare(src, 2, admin, false);
        check(a.pickFromFeed(Agent.RESHARE) == null, "the same story cannot be reshared twice");
        Post copyOfSame = Post.reshareOf(src, 2, 3, false);              // another copy of the same story
        a.addPostToFeed(copyOfSame);
        check(a.pickFromFeed(Agent.RESHARE) == null, "another copy of a held story is not reshareable either");
        check(a.pickFromFeed(Agent.LIKE) == copyOfSame, "a different copy of the story can still be liked once");
        Agent b = new Agent(1, p);
        Post mine = b.makePost(0);
        b.addPostToFeed(Post.reshareOf(mine, 3, 1, false));
        check(b.pickFromFeed(Agent.RESHARE) == null, "an agent does not reshare its own story");
    }

    private static void testQTargetUsesAvailableActions() {
        System.out.println("[Q target: only actions available at the next state]");
        SimParams p = params("n=3", "q_eps=1.0", "q_eta=1.0", "q_gamma=0.9", "rewire=false");
        Agent a = new Agent(0, p);                       // empty feed: only post is available
        a.chooseAction(0);
        a.getQ()[0][Agent.POST] = 10.0;
        for (double[] row : a.getQ()) row[Agent.REWIRE] = 100.0; // a frozen, unavailable action
        a.observeAndLearn(1);                            // reward 0 (empty feed, no posts): target = 0.9 * best available
        check(Math.abs(a.getQ()[0][Agent.POST] - 9.0) < 1e-9, "unavailable rewire (and like/reshare) do not enter the bootstrap target");
    }

    private static void testRewardWeights() {
        System.out.println("[reward weights]");
        SimParams p = params("n=3", "q_eps=1.0", "q_eta=1.0", "q_gamma=0.0", "rewire=false", "w_fit=0.5", "w_rec=2.0");
        Agent a = new Agent(0, p);
        Agent other = new Agent(1, p);
        a.setOpinion(0.0); other.setOpinion(0.0);
        a.chooseAction(0);
        a.addPostToFeed(new Post(1, 0.0, 0));                  // identical value: identity fit 1
        a.observeAndLearn(1);                                    // no own posts: recognition 0 -> r = 0.5 * 1 + 2 * 0
        check(Math.abs(a.getQ()[0][Agent.POST] - 0.5) < 1e-9 || Math.abs(a.getQ()[0][Agent.LIKE] - 0.5) < 1e-9 || Math.abs(a.getQ()[0][Agent.RESHARE] - 0.5) < 1e-9,
                "reward = w_fit * identity fit + w_rec * recognition");
    }

    private static void testRawFitHasCommonBaseline() {
        System.out.println("[raw identity fit has a common baseline]");
        SimParams p = params("learner=bandit", "q_eta=1", "q_init=0", "q_eps=0",
                "rewire=false", "w_fit=1", "w_rec=0", "fit_mode=raw");
        for (double x : new double[]{-1.0, 0.0, 1.0}) {
            Agent a = new Agent(0, p);
            a.setOpinion(x);
            a.setFitBaseline(0.75 - 0.25 * x * x); // deliberately different; raw mode must ignore it
            a.chooseAction(0); // empty feed and no rewiring: only Post is available
            a.addPostToFeed(new Post(1, x, 0));
            a.observeAndLearn(1);
            check(Math.abs(a.getQ()[0][Agent.POST] - 1.0) < 1e-12,
                    "identical feed similarity earns identical raw reward at opinion " + x);
        }
    }

    private static void testRelativeFit() {
        System.out.println("[relative identity fit]");
        SimParams p = params("n=3", "q_eps=1.0", "q_eta=1.0", "q_gamma=0.0", "rewire=false", "w_fit=1", "w_rec=0", "fit_mode=relative");
        Agent a = new Agent(0, p);
        a.setOpinion(0.0);
        a.setFitBaseline(0.3);
        a.chooseAction(0);
        a.addPostToFeed(new Post(1, 0.0, 0));                  // identical value: raw fit 1
        a.observeAndLearn(1);
        double best = Math.max(a.getQ()[0][Agent.POST], Math.max(a.getQ()[0][Agent.LIKE], a.getQ()[0][Agent.RESHARE]));
        check(Math.abs(best - 0.7) < 1e-9, "reward uses raw fit minus the random-feed baseline (1 - 0.3)");
        check(Math.abs(a.getLastIdentityFit() - 1.0) < 1e-9, "the reported identity fit stays raw");
    }

    private static void testActionAvailability() {
        System.out.println("[action availability]");
        Agent st = new Agent(0, params("rewire=false", "q_eps=0.5"));
        st.addPostToFeed(new Post(1, 0.0, 0));
        boolean sawRewire = false;
        for (int i = 0; i < 1000; i++) if (st.chooseAction(0) == Agent.REWIRE) sawRewire = true;
        check(!sawRewire, "rewire=false => rewire is never chosen (static network)");
        SimParams p = params();
        Agent a = new Agent(0, p);
        boolean sawLikeOrReshare = false;
        for (int i = 0; i < 500; i++) {
            int act = a.chooseAction(0);
            if (act == Agent.LIKE || act == Agent.RESHARE) sawLikeOrReshare = true;
        }
        check(!sawLikeOrReshare, "empty feed => only post and rewire are available");
        a.setChannelMode(Agent.ChannelMode.NONE);
        a.addPostToFeed(new Post(1, 0.0, 0));
        boolean sawPost = false, sawReshare = false;
        for (int i = 0; i < 500; i++) {
            int act = a.chooseAction(0);
            if (act == Agent.POST) sawPost = true;
            if (act == Agent.RESHARE) sawReshare = true;
        }
        check(!sawPost && !sawReshare, "channel NONE disables post and reshare");
    }

    private static void testPickFavoursSimilar() {
        System.out.println("[feed pick favours similar posts]");
        randomGenerator.init(5, 5);
        SimParams p = params("beta_h=20");
        Agent a = new Agent(0, p);
        a.setOpinion(0.5);
        a.addPostToFeed(new Post(1, 0.5, 0));
        a.addPostToFeed(new Post(2, -0.9, 0));
        int near = 0;
        for (int i = 0; i < 500; i++) if (a.pickFromFeed(Agent.LIKE).getPostUserId() == 1) near++;
        check(near > 495, "beta_h large => the close post is picked almost always");
        SimParams flat = params("beta_h=0");
        Agent b = new Agent(0, flat);
        b.setOpinion(0.5);
        b.addPostToFeed(new Post(1, 0.5, 0));
        b.addPostToFeed(new Post(2, -0.9, 0));
        int n1 = 0;
        for (int i = 0; i < 4000; i++) if (b.pickFromFeed(Agent.LIKE).getPostUserId() == 1) n1++;
        check(Math.abs(n1 / 4000.0 - 0.5) < 0.04, "beta_h = 0 => uniform pick");
    }

    private static AdminOptim graph(SimParams p, int n, int[][] edges) {
        AdminOptim admin = new AdminOptim(n, new double[n][n], p);
        for (int[] e : edges) admin.addFollowEdge(e[0], e[1]);
        return admin;
    }

    private static void testFollowQueue() {
        System.out.println("[follow queue]");
        SimParams p = params("n=6");
        AdminOptim admin = graph(p, 6, new int[][]{{0, 1}, {0, 2}, {0, 3}});
        check(admin.frontFollowee(0) == 1, "front of the queue is the oldest followee");
        admin.touchFollowee(0, 1);
        check(admin.frontFollowee(0) == 2, "reacting to a followee moves it to the back");
        admin.touchFollowee(0, 5);   // not a followee: no effect
        check(admin.followeeCount(0) == 3 && admin.frontFollowee(0) == 2, "reacting to a non-followee changes nothing");
    }

    private static void testRewire() {
        System.out.println("[rewire: candidates are the originators of feed posts not yet followed]");
        randomGenerator.init(3, 3);
        SimParams p = params("n=7", "beta_h=50");
        // agent 0 follows 1 (queue front) and 2. Feed: posts originated by 1 (already followed), 0 (self),
        // 3 and 4 (candidates), plus a reshare by 5 of a post originated by 4 (originator 4, not the resharer 5).
        AdminOptim admin = graph(p, 7, new int[][]{{0, 1}, {0, 2}});
        Agent[] ag = new Agent[7];
        for (int i = 0; i < 7; i++) ag[i] = new Agent(i, p);
        ag[0].setOpinion(0.9); ag[3].setOpinion(0.9); ag[4].setOpinion(-0.9);
        Post by4 = new Post(4, -0.9, 0);
        ag[0].addPostToFeed(new Post(1, 0.0, 0));
        ag[0].addPostToFeed(new Post(0, 0.9, 0));
        ag[0].addPostToFeed(new Post(3, 0.9, 0));
        ag[0].addPostToFeed(by4);
        ag[0].addPostToFeed(Post.reshareOf(by4, 5, 1, false));
        check(Post.reshareOf(by4, 5, 1, false).getRootAuthorId() == 4, "originator of a reshare is the root post's author");
        int before = admin.followeeCount(0);
        int added = ag[0].rewire(admin, ag);
        check(added == 3, "new followee is a not-yet-followed originator, weighted toward the similar one (never the resharer 5)");
        check(admin.followeeCount(0) == before, "out-degree conserved");
        check(!admin.follows(0, 1) && admin.follows(0, 2) && admin.follows(0, 3),
                "the oldest followee (front) was dropped and the new one appended");
        check(!admin.getFollowers(1).contains(0), "reverse edge updated");
        // the front followee is at least as similar as the drawn candidate => rewire is refused, nothing changes
        AdminOptim admin3 = graph(p, 7, new int[][]{{0, 1}, {0, 2}});
        ag[1].setOpinion(0.9);
        check(ag[0].rewire(admin3, ag) == -1 && admin3.follows(0, 1) && !admin3.follows(0, 3) && admin3.followeeCount(0) == 2,
                "no candidate closer than the front followee => no rewire, follow list unchanged");
        // without the gate the same situation swaps anyway (the front followee is dropped, a candidate is appended)
        SimParams ng = params("n=7", "beta_h=50", "rewire_gate=false");
        Agent[] ng_ag = new Agent[7];
        for (int i = 0; i < 7; i++) ng_ag[i] = new Agent(i, ng);
        ng_ag[0].setOpinion(0.9); ng_ag[1].setOpinion(0.9); ng_ag[3].setOpinion(0.9); ng_ag[4].setOpinion(-0.9);
        ng_ag[0].addPostToFeed(new Post(3, 0.9, 0));
        AdminOptim admin4 = graph(ng, 7, new int[][]{{0, 1}, {0, 2}});
        check(ng_ag[0].rewire(admin4, ng_ag) == 3 && !admin4.follows(0, 1) && admin4.follows(0, 3) && admin4.followeeCount(0) == 2,
                "rewire_gate=false: the candidate replaces the oldest followee even though that followee is as close");
        ag[1].setOpinion(0.0);
        // feed with only followed / own originators => no candidate => no-op, nothing dropped
        AdminOptim admin2 = graph(p, 7, new int[][]{{0, 1}, {0, 2}});
        Agent lone = new Agent(0, p);
        lone.setOpinion(0.9);
        lone.addPostToFeed(new Post(1, 0.0, 0));
        lone.addPostToFeed(new Post(0, 0.9, 0));
        check(lone.rewire(admin2, ag) == -1 && admin2.follows(0, 1), "no new originator in the feed => no-op, nothing dropped");
        // empty feed
        Agent none = new Agent(0, p);
        check(none.rewire(admin2, ag) == -1, "empty feed => rewire is a no-op");
        // no followees => nothing to drop
        check(ag[6].rewire(graph(p, 7, new int[][]{}), ag) == -1, "no followees => no-op");
    }

    private static void testWattsStrogatzStart() {
        System.out.println("[Watts-Strogatz start]");
        randomGenerator.init(9, 9);
        ExperimentConfig cfg = ExperimentConfig.fromArgs(new String[]{"n=200", "ws_out=15", "ws_beta=0.1"});
        check(cfg.networkType.equals("ws") && cfg.wsOut == 15, "ws is the default start network, out-degree 15");
        network.Network net = network.NetworkFactory.create(cfg, 200);
        net.makeNetwork(new Agent[200]);
        double[][] w = net.getAdjacencyMatrix();
        boolean regular = true, noSelf = true;
        int[] in = new int[200];
        for (int i = 0; i < 200; i++) {
            int out = 0;
            for (int j = 0; j < 200; j++) if (w[i][j] > 0) { out++; in[j]++; if (i == j) noSelf = false; }
            if (out != 15) regular = false;
        }
        int maxIn = 0;
        for (int x : in) maxIn = Math.max(maxIn, x);
        check(regular && noSelf, "every agent starts with out-degree exactly 15, no self-loops");
        check(maxIn < 40, "no initial hubs (max in-degree " + maxIn + ")");
    }

    private static void testDirectedBAStart() {
        System.out.println("[directed BA start]");
        int n = 500;
        int[] maxIn = new int[2];
        double[] attract = {1.0, 1e6};
        for (int g = 0; g < 2; g++) {
            randomGenerator.init(41, 41);
            network.Network net = new network.DirectedBANetwork(n, 15, attract[g]);
            net.makeNetwork(null);
            double[][] w = net.getAdjacencyMatrix();
            boolean regular = true, noSelf = true;
            int[] in = new int[n];
            for (int i = 0; i < n; i++) {
                int out = 0;
                for (int j = 0; j < n; j++) if (w[i][j] > 0) { out++; in[j]++; if (i == j) noSelf = false; }
                if (out != 15) regular = false;
            }
            for (int d : in) maxIn[g] = Math.max(maxIn[g], d);
            check(regular && noSelf, "every agent follows exactly 15 others, none itself (attract=" + attract[g] + ")");
        }
        check(maxIn[0] > 2 * maxIn[1], "small attractiveness gives much bigger hubs than near-uniform attachment (" + maxIn[0] + " vs " + maxIn[1] + ")");
    }

    private static void testHomophilyStart() {
        System.out.println("[homophily start]");
        double[] corr = new double[2];
        double[] gammas = {0.0, 8.0};
        for (int g = 0; g < 2; g++) {
            randomGenerator.init(31, 31);
            SimParams p = params("n=300");
            Agent[] ag = new Agent[300];
            for (int i = 0; i < 300; i++) ag[i] = new Agent(i, p);
            network.Network net = new network.HomophilyNetwork(300, 15, gammas[g]);
            net.makeNetwork(ag);
            double[][] w = net.getAdjacencyMatrix();
            boolean regular = true, noSelf = true;
            double sx = 0, sy = 0, sxy = 0, sxx = 0, syy = 0; int m = 0;
            for (int i = 0; i < 300; i++) {
                int out = 0;
                for (int j = 0; j < 300; j++) if (w[i][j] > 0) {
                    out++; if (i == j) noSelf = false;
                    double x = ag[i].getOpinion(), y = ag[j].getOpinion();
                    sx += x; sy += y; sxy += x * y; sxx += x * x; syy += y * y; m++;
                }
                if (out != 15) regular = false;
            }
            corr[g] = (sxy / m - sx / m * sy / m) / Math.sqrt((sxx / m - sx / m * sx / m) * (syy / m - sy / m * sy / m));
            check(regular && noSelf, "gamma=" + gammas[g] + ": out-degree exactly 15, no self-loops");
        }
        check(Math.abs(corr[0]) < 0.08, "gamma = 0 is a uniform random graph (assortativity " + String.format("%.3f", corr[0]) + ")");
        check(corr[1] > 0.35, "gamma = 8 wires similar agents together (assortativity " + String.format("%.3f", corr[1]) + ")");
    }

    private static void testDeathSweep() {
        System.out.println("[death sweep]");
        SimParams p = params("n=3", "dead_after=10");
        AdminOptim admin = graph(p, 3, new int[][]{});
        Post forgotten = new Post(0, 0.0, 0);
        Post liked = new Post(1, 0.0, 0);
        admin.addRecentPost(forgotten);
        admin.addRecentPost(liked);
        liked.like(8);
        admin.sweepDead(11);
        check(admin.getAlivePostCount() == 1 && admin.getDiedPostCount() == 1, "unreacted post dies after L steps, liked one survives");
        admin.sweepDead(18);
        check(admin.getAlivePostCount() == 1, "liked post still alive 10 steps after its like (18 - 8 = 10 <= L)");
        admin.sweepDead(19);
        check(admin.getAlivePostCount() == 0 && admin.getDiedPostCount() == 2, "it dies one step later (19 - 8 = 11 > L)");
    }

    private static void testDriftOffByDefault() {
        System.out.println("[drift]");
        SimParams p = params();
        Agent a = new Agent(0, p);
        a.setOpinion(0.4);
        a.addPostToFeed(new Post(1, -0.9, 0));
        a.updateValues();
        check(a.getOpinion() == 0.4, "mu = 0 => X never moves");
        SimParams drift = params("mu=0.5");
        Agent b = new Agent(0, drift);
        double x0 = b.getIntrinsicOpinion();
        b.addPostToFeed(new Post(1, 1.0, 0));
        b.updateValues();
        check(Math.abs(b.getOpinion() - (0.5 * x0 + 0.5 * 1.0)) < 1e-12, "mu > 0 => x = (1-mu) x0 + mu * feed mean");
    }

    private static void testUniformInit() {
        System.out.println("[uniform init]");
        randomGenerator.init(123, 123);
        SimParams p = params();
        double sum = 0, sumAbs = 0;
        int N = 4000;
        boolean inRange = true;
        for (int i = 0; i < N; i++) {
            double x = new Agent(i, p).getIntrinsicOpinion();
            sum += x; sumAbs += Math.abs(x);
            if (x < -1 || x > 1) inRange = false;
        }
        check(inRange, "all X within [-1,1]");
        check(Math.abs(sum / N) < 0.05 && Math.abs(sumAbs / N - 0.5) < 0.03, "U[-1,1]: mean ~ 0, mean |x| ~ 0.5");
    }

    // The windowed velocity ranking should cache between refreshes and, once it refreshes, demote
    // a stalled early burst below a post that is gaining reshares now.
    private static void testVelocityRankingCache() {
        System.out.println("[velocity ranking cache]");
        SimParams p = params("access_prob=0.2", "vel_mode=windowed", "n=5");
        AdminOptim admin = new AdminOptim(5, new double[5][5], p);
        Post stalledBurst = new Post(0, 0.1, 0);
        Post currentlyRising = new Post(1, -0.1, 0);
        admin.addRecentPost(stalledBurst);
        admin.addRecentPost(currentlyRising);
        for (int i = 0; i < 20; i++) stalledBurst.receiveRepost(0);

        List<Post> r0 = admin.rankByVelocity(0);
        check(r0.get(0).getPostId() == stalledBurst.getPostId(), "initial ranking: early burst leads");
        for (int i = 0; i < 6; i++) currentlyRising.receiveRepost(3);
        List<Post> r3 = admin.rankByVelocity(3);
        check(r3 == r0, "cached ranking within the refresh interval");
        List<Post> r5 = admin.rankByVelocity(5);
        check(r5 != r0 && r5.get(0).getPostId() == currentlyRising.getPostId(),
                "after the interval the stalled burst is demoted below the rising post");
    }

    // Trend velocity: likes count like reshares (trend_count=both), and equal scores are ordered at random (trend_tie=random)
    // instead of oldest-first.
    private static void testTrendCountAndTie() {
        System.out.println("[trend count and tie-break]");
        SimParams legacy = params("access_prob=0.2", "vel_mode=windowed", "n=5");
        AdminOptim a0 = new AdminOptim(5, new double[5][5], legacy);
        Post liked = new Post(0, 0.1, 0), reshared = new Post(1, -0.1, 0);
        a0.addRecentPost(liked); a0.addRecentPost(reshared);
        for (int i = 0; i < 4; i++) liked.like(1);
        reshared.receiveRepost(1);
        check(a0.rankByVelocity(5).get(0) == reshared, "legacy: likes do not count (a reshared post beats a liked one)");
        SimParams both = params("access_prob=0.2", "vel_mode=windowed", "n=5", "trend_count=both");
        AdminOptim a1 = new AdminOptim(5, new double[5][5], both);
        Post liked1 = new Post(0, 0.1, 0), reshared1 = new Post(1, -0.1, 0);
        a1.addRecentPost(liked1); a1.addRecentPost(reshared1);
        for (int i = 0; i < 4; i++) liked1.like(1);
        reshared1.receiveRepost(1);
        check(a1.rankByVelocity(5).get(0) == liked1, "trend_count=both: 4 likes outrank 1 reshare");
        // ties: 20 posts with no reaction; legacy keeps creation order, random reshuffles (first place not always the oldest)
        SimParams oldest = params("access_prob=1", "n=5"), rnd = params("access_prob=1", "n=5", "trend_tie=random");
        AdminOptim t0 = new AdminOptim(5, new double[5][5], oldest), t1 = new AdminOptim(5, new double[5][5], rnd);
        List<Post> pool = new java.util.ArrayList<>();
        for (int i = 0; i < 20; i++) { Post q = new Post(0, 0.0, i); pool.add(q); t0.addRecentPost(q); t1.addRecentPost(q); }
        check(t0.rankByVelocity(30).get(0) == pool.get(0), "trend_tie=oldest: zero-score ties keep creation order");
        int oldestFirst = 0;
        for (int step = 31; step < 231; step++) if (t1.rankByVelocity(step).get(0) == pool.get(0)) oldestFirst++;
        check(oldestFirst > 0 && oldestFirst < 40, "trend_tie=random: the oldest post leads only ~1/20 of the time (" + oldestFirst + "/200)");
    }

    // Chrono selection dedups reshares of the same story by rootPostId.
    private static void testChronoRootDedup() {
        System.out.println("[chrono rootPostId dedup]");
        SimParams p = params("alpha=0", "n=5");
        AdminOptim admin = new AdminOptim(5, new double[5][5], p);
        admin.addFollowEdge(2, 0);
        admin.addFollowEdge(2, 1);
        Agent[] agentSet = new Agent[5];
        for (int i = 0; i < 5; i++) agentSet[i] = new Agent(i, p);
        Agent reader = agentSet[2];

        Post original = new Post(4, 0.3, 0);
        Post reshareByA = Post.reshareOf(original, 0, 0, false);
        Post reshareByB = Post.reshareOf(original, 1, 0, false);
        check(reshareByA.getPostId() != reshareByB.getPostId() && reshareByA.getRootPostId() == reshareByB.getRootPostId(),
                "two reshares of one story: distinct postId, shared rootPostId");
        reader.addToPostCash(reshareByA);
        reader.addToPostCash(reshareByB);
        admin.AdminFeedback(2, agentSet, 0, null, new StepStats());
        check(reader.getFeed().size() == 1, "only one of the two same-root reshares is delivered");
    }

    private static void testDeadPostsLeaveFeed() {
        System.out.println("[dead posts are never delivered]");
        SimParams p = params("alpha=0", "n=5", "dead_after=10");
        AdminOptim admin = new AdminOptim(5, new double[5][5], p);
        admin.addFollowEdge(2, 0);
        Agent[] agentSet = new Agent[5];
        for (int i = 0; i < 5; i++) agentSet[i] = new Agent(i, p);
        Post old = new Post(0, 0.3, 0);
        agentSet[2].addToPostCash(old);
        admin.AdminFeedback(2, agentSet, 50, null, new StepStats());   // 50 - 0 > 10
        check(agentSet[2].getFeed().isEmpty(), "a forgotten post is not delivered to the feed");
    }

    private static void testForYou() {
        System.out.println("[For You: perspective-similarity stream]");
        randomGenerator.init(5, 5);
        int n = 12;
        boolean threw = false;
        try { params("trend_share=0.7", "foryou_share=0.5"); } catch (IllegalArgumentException e) { threw = true; }
        check(threw, "trend_share + foryou_share > 1 is rejected");
        int ownSeen = 0, far5 = 0, hop2With5 = 0, dupRoot = 0, nearMissing = 0;
        int reps = 200;
        for (int hop = 1; hop <= 2; hop++) {
            SimParams p = params("n=12", "trend_share=0", "foryou_share=0.3", "feed_capacity=10",
                    "foryou_hop=" + hop, "fy_beta=50", "fy_profile=false");
            for (int rep = 0; rep < reps; rep++) {
                AdminOptim admin = graph(p, n, new int[][]{{0, 1}, {0, 2}, {0, 3}, {0, 4}, {1, 5}});
                Agent[] ag = new Agent[n];
                for (int i = 0; i < n; i++) ag[i] = new Agent(i, p);
                ag[0].setOpinion(0.5);
                Post a1 = new Post(1, 0.5, 0), a2 = new Post(2, -0.9, 0), a3 = new Post(3, 0.45, 0),
                     a4 = new Post(4, -0.8, 0), a5 = new Post(5, 0.5, 0), own = new Post(0, 0.5, 0);
                Post reshare = Post.reshareOf(a1, 2, 1, false);   // another post of a1's root, by a followee
                for (Post q : new Post[]{a1, a2, a3, a4, a5, own, reshare}) admin.addRecentPost(q);
                admin.rebuildAuthorIndex();
                admin.AdminFeedback(0, ag, 2, null, new StepStats());
                java.util.List<Post> feed = ag[0].getFeed();
                int rootsOf1 = 0;
                for (Post q : feed) {
                    if (q.getPostUserId() == 0) ownSeen++;
                    if (q.getRootPostId() == a1.getRootPostId()) rootsOf1++;
                    if (hop == 1 && q.getPostUserId() == 5) far5++;
                    if (hop == 2 && q.getPostUserId() == 5) hop2With5++;
                }
                if (rootsOf1 > 1) dupRoot++;
                boolean has3 = false;
                for (Post q : feed) if (q.getPostUserId() == 3) has3 = true;
                if (hop == 1 && !has3) nearMissing++;
            }
        }
        check(ownSeen == 0, "never shows the reader's own posts");
        check(far5 == 0, "foryou_hop = 1: a 2-hop author's post is never shown");
        check(hop2With5 > reps / 2, "foryou_hop = 2: the 2-hop author with an identical X is often shown (" + hop2With5 + "/" + reps + ")");
        check(dupRoot == 0, "two posts of one root never share the feed");
        check(nearMissing == 0, "a sharp beta picks the near-X post over the far-X ones");
        // the platform's estimate: Xhat <- (1-rho) Xhat + rho X_post, different weights for like / reshare
        SimParams q = params("n=3", "foryou_share=0.3", "trend_share=0.3", "rho_l=0.2", "rho_r=0.5");
        AdminOptim admin = new AdminOptim(3, new double[3][3], q);
        admin.initEstimates(randomGenerator.network());
        double x0 = admin.getEstimate(1);
        check(x0 >= -1.0 && x0 <= 1.0, "initial estimate is a random X in [-1,1]");
        admin.updateEstimate(1, 0.8, q.rhoLike());
        check(Math.abs(admin.getEstimate(1) - (0.8 * x0 + 0.2 * 0.8)) < 1e-12, "like moves the estimate by rho_l toward the post's X");
        double x1 = admin.getEstimate(1);
        admin.updateEstimate(1, -0.4, q.rhoReshare());
        check(Math.abs(admin.getEstimate(1) - (0.5 * x1 + 0.5 * -0.4)) < 1e-12, "reshare moves the estimate by rho_r toward the post's X");
    }

    private static void testEachPostShownOnce() {
        System.out.println("[each post is shown to an agent at most once]");
        randomGenerator.init(6, 6);
        SimParams p = params("n=6", "trend_share=0.3", "foryou_share=0.3", "feed_capacity=10", "foryou_hop=0", "trend_hop=0");
        AdminOptim admin = graph(p, 6, new int[][]{{0, 1}});
        Agent[] ag = new Agent[6];
        for (int i = 0; i < 6; i++) ag[i] = new Agent(i, p);
        java.util.List<Post> all = new java.util.ArrayList<>();
        for (int a = 1; a <= 5; a++) for (int k = 0; k < 2; k++) {
            Post q = new Post(a, 0.1 * a, 0);
            all.add(q);
            admin.addRecentPost(q);
        }
        admin.rebuildAuthorIndex();
        java.util.Set<Integer> shown = new java.util.HashSet<>();
        boolean repeated = false;
        int total = 0;
        for (int visit = 0; visit < 6; visit++) {
            ag[0].resetFeed();
            admin.AdminFeedback(0, ag, 1, admin.rankByVelocity(1), new StepStats());
            for (Post q : ag[0].getFeed()) { total++; if (!shown.add(q.getPostId())) repeated = true; }
        }
        check(!repeated, "no post reaches the same agent's feed twice (Trend, For You and chrono)");
        check(total == all.size(), "every post is eventually shown once, then the pool is exhausted (" + total + " of " + all.size() + ")");
    }

    private static void testNotifyOriginal() {
        System.out.println("[reshares of my own post join my candidate pool (notify_original)]");
        // chrono: the author does not follow the resharers, so without the extra pool the copies could never reach the feed
        for (String mode : new String[]{"chrono", "foryou", "trend"}) {
            randomGenerator.init(8, 8);
            String[] mix = mode.equals("chrono") ? new String[]{"trend_share=0", "foryou_share=0"}
                    : mode.equals("foryou") ? new String[]{"trend_share=0", "foryou_share=1", "foryou_hop=1", "fy_beta=0"}
                    : new String[]{"trend_share=1", "foryou_share=0", "trend_hop=1"};
            java.util.List<String> t = new java.util.ArrayList<>(java.util.List.of("n=6", "feed_capacity=10", "notify_original=1"));
            t.addAll(java.util.List.of(mix));
            SimParams p = params(t.toArray(new String[0]));
            AdminOptim admin = graph(p, 6, new int[][]{{0, 1}});
            Agent[] ag = new Agent[6];
            for (int i = 0; i < 6; i++) ag[i] = new Agent(i, p);
            Post mine = ag[0].makePost(0);
            Post c1 = Post.reshareOf(mine, 3, 1, false), c2 = Post.reshareOf(mine, 4, 1, false);
            admin.addRecentPost(mine); admin.addRecentPost(c1); admin.addRecentPost(c2);
            admin.notifyOriginal(0, c1);
            if (mode.equals("chrono")) { // chrono ignores the notify queue; OpinionDynamics delivers the copy to the author's postCash
                ag[0].resetFeed();
                admin.AdminFeedback(0, ag, 2, admin.rankByVelocity(2), new StepStats());
                check(ag[0].getFeed().isEmpty(), "chrono: the notify queue itself no longer feeds chrono");
                ag[0].addToPostCash(c1);
            }
            admin.rebuildAuthorIndex();
            ag[0].resetFeed();
            admin.AdminFeedback(0, ag, 2, admin.rankByVelocity(2), new StepStats());
            check(ag[0].getFeed().contains(c1), mode + ": a reshare of my post (author out of hop reach) reaches my feed");
            check(!ag[0].getFeed().contains(c2), mode + ": un-notified copy of the same story does not");
            ag[0].resetFeed();
            admin.AdminFeedback(0, ag, 3, admin.rankByVelocity(3), new StepStats());
            check(!ag[0].getFeed().contains(c1), mode + ": delivered once only");
        }
        randomGenerator.init(8, 9);
        SimParams off = params("n=6", "trend_share=0", "foryou_share=0");
        AdminOptim admin2 = graph(off, 6, new int[][]{{0, 1}});
        Agent[] bg = new Agent[6];
        for (int i = 0; i < 6; i++) bg[i] = new Agent(i, off);
        Post own = bg[0].makePost(0);
        admin2.notifyOriginal(0, Post.reshareOf(own, 2, 1, false));
        bg[0].resetFeed();
        admin2.AdminFeedback(0, bg, 2, admin2.rankByVelocity(2), new StepStats());
        check(bg[0].getFeed().isEmpty(), "off by default");
    }

    private static void testPostNoise() {
        System.out.println("[post noise: imperfect expression of X]");
        randomGenerator.init(11, 11);
        Agent exact = new Agent(0, params("post_noise=0"));
        exact.setOpinion(0.4);
        check(exact.makePost(0).getPostOpinion() == 0.4 && exact.observedOpinion() == 0.4, "no noise: the post carries X exactly");
        SimParams p = params("post_noise=0.3");
        Agent a = new Agent(1, p);
        a.setOpinion(0.9);
        double sum = 0; boolean differs = false, inRange = true;
        for (int i = 0; i < 4000; i++) {
            double x = a.makePost(i).getPostOpinion();
            sum += x; differs |= x != 0.9; inRange &= x >= -1.0 && x <= 1.0;
        }
        check(differs && inRange, "noisy posts differ from X and stay in [-1, 1]");
        Agent b = new Agent(2, p);
        b.setOpinion(0.0);
        for (int i = 0; i < 4000; i++) b.makePost(i);
        check(Math.abs(b.observedOpinion()) < 0.03, "at X = 0 the mean of many posts recovers X (observed " + b.observedOpinion() + ")");
        Agent c = new Agent(3, p);
        check(c.observedOpinion() == 0.0, "before any post an agent is observed as neutral (0)");
    }

    private static void testForYouCandidateCap() {
        System.out.println("[For You candidate cap]");
        for (int cap : new int[]{0, 3}) {
            randomGenerator.init(12, 12);
            SimParams p = params("n=12", "trend_share=0", "foryou_share=1", "foryou_hop=0", "feed_capacity=10", "foryou_cand_max=" + cap);
            AdminOptim admin = graph(p, 12, new int[][]{{0, 1}});
            Agent[] ag = new Agent[12];
            for (int i = 0; i < 12; i++) ag[i] = new Agent(i, p);
            java.util.Set<Post> pool = new java.util.HashSet<>();
            for (int a = 1; a <= 10; a++) { Post q = new Post(a, 0.05 * a, 0); pool.add(q); admin.addRecentPost(q); }
            admin.rebuildAuthorIndex();
            ag[0].resetFeed();
            admin.AdminFeedback(0, ag, 1, admin.rankByVelocity(1), new StepStats());
            int expect = cap == 0 ? 10 : cap;
            check(ag[0].getFeed().size() == expect && pool.containsAll(ag[0].getFeed()),
                    "foryou_cand_max=" + cap + ": " + expect + " posts delivered, all from the candidate pool (got " + ag[0].getFeed().size() + ")");
        }
        // the cap keeps a uniform sample: over many feeds every pool post appears about equally often
        randomGenerator.init(12, 13);
        SimParams p = params("n=12", "trend_share=0", "foryou_share=1", "foryou_hop=0", "feed_capacity=10", "foryou_cand_max=2", "fy_beta=0");
        int[] hits = new int[10];
        for (int rep = 0; rep < 2000; rep++) {
            AdminOptim admin = graph(p, 12, new int[][]{{0, 1}});
            Agent[] ag = new Agent[12];
            for (int i = 0; i < 12; i++) ag[i] = new Agent(i, p);
            Post[] pool = new Post[10];
            for (int a = 1; a <= 10; a++) { pool[a - 1] = new Post(a, 0.0, 0); admin.addRecentPost(pool[a - 1]); }
            admin.rebuildAuthorIndex();
            ag[0].resetFeed();
            admin.AdminFeedback(0, ag, 1, admin.rankByVelocity(1), new StepStats());
            for (Post q : ag[0].getFeed()) for (int k = 0; k < 10; k++) if (q == pool[k]) hits[k]++;
        }
        int min = Integer.MAX_VALUE, max = 0;
        for (int h : hits) { min = Math.min(min, h); max = Math.max(max, h); }
        check(min > 300 && max < 500, "the capped candidate sample is uniform (each of 10 posts in about 400 of 2000 feeds: " + min + ".." + max + ")");
        check(params("fit_mode=relative", "fit_baseline=analytic").fitBaselineAnalytic() && !params().fitBaselineAnalytic(), "fit_baseline=analytic parsed, off by default");
    }

    private static void testForYouHopTerm() {
        System.out.println("[For You score = similarity x hop term]");
        randomGenerator.init(14, 14);
        // path 0 -> 1 -> 2 -> 3: authors 1, 2, 3 sit at hop 1, 2, 3 from reader 0; equal X, one post each
        for (String cap : new String[]{"foryou_cand_max=50", "foryou_cand_max=0"}) {
            SimParams p = params("n=6", "trend_share=0", "foryou_share=1", "foryou_hop=5", "feed_capacity=1", "fy_beta=0", "foryou_hop_lambda=0.7", cap);
            int[] hits = new int[4];
            for (int rep = 0; rep < 6000; rep++) {
                AdminOptim admin = graph(p, 6, new int[][]{{0, 1}, {1, 2}, {2, 3}});
                Agent[] ag = new Agent[6];
                for (int i = 0; i < 6; i++) ag[i] = new Agent(i, p);
                for (int a = 1; a <= 3; a++) admin.addRecentPost(new Post(a, 0.0, 0));
                admin.rebuildAuthorIndex();
                ag[0].resetFeed();
                admin.AdminFeedback(0, ag, 1, admin.rankByVelocity(1), new StepStats());
                for (Post q : ag[0].getFeed()) hits[q.getPostUserId()]++;
            }
            double r13 = hits[1] / (double) hits[3];   // expected exp(0.7 * 2) = 4.06
            double r12 = hits[1] / (double) hits[2];   // expected exp(0.7) = 2.01
            check(r13 > 3.4 && r13 < 4.8 && r12 > 1.7 && r12 < 2.4,
                    cap + ": selection frequency falls with hop like exp(-lambda (d-1)) (1:2 = " + String.format("%.2f", r12) + ", 1:3 = " + String.format("%.2f", r13) + ")");
        }
    }

    private static void testStartDegreeRegulation() {
        System.out.println("[start networks share the same mean degree]");
        for (String net : new String[]{"random", "dcsbm", "hk"}) {
            randomGenerator.init(21, 21);
            ExperimentConfig c = ExperimentConfig.fromArgs(new String[]{"n=300", "network=" + net, "sbm_deg=12", "start_deg=12"});
            network.Network nw = network.NetworkFactory.create(c, 300);
            Agent[] ag = new Agent[300];
            SimParams p = SimParams.from(c);
            for (int i = 0; i < 300; i++) ag[i] = new Agent(i, p);
            nw.makeNetwork(ag);
            nw.enforceEdgeCount(300 * c.startDeg, randomGenerator.network());
            boolean loops = false;
            for (int i = 0; i < 300; i++) loops |= nw.getEdge(i, i) != 0.0;
            check(nw.countEdges() == 300 * 12 && !loops, net + ": exactly n x 12 directed edges, no self-loops (" + nw.countEdges() + ")");
        }
    }

    private static void testLikeGate() {
        System.out.println("[like range gate: filter vs noop]");
        randomGenerator.init(31, 31);
        SimParams filter = params("like_max_dist=0.3", "like_gate=filter"), noop = params("like_max_dist=0.3", "like_gate=noop");
        for (SimParams p : new SimParams[]{filter, noop}) {
            Agent a = new Agent(0, p);
            a.setOpinion(0.9);
            a.addPostToFeed(new Post(1, -0.9, 0));   // far away: |dx| = 1.8 > 0.3
            Post picked = a.pickFromFeed(Agent.LIKE);
            boolean isFilter = !p.likeGateNoop();
            check(isFilter ? picked == null : (picked != null && a.likeGatedFor(picked)),
                    isFilter ? "filter: an out-of-range post is not a like candidate" : "noop: the out-of-range post is drawn and the like is gated (does nothing)");
        }
        Agent near = new Agent(1, noop);
        near.setOpinion(0.9);
        near.addPostToFeed(new Post(2, 0.8, 0));
        check(!near.likeGatedFor(near.pickFromFeed(Agent.LIKE)), "noop: an in-range post is not gated");
    }

    // Sign-based camp metrics ignore agents inside the neutral band (analysis code, unchanged).
    private static void testNeutralBandExcludesEdgesEntirely() {
        System.out.println("[neutral band: excludes neutral agents' edges from sign modularity]");
        Analysis analyzer = new Analysis(5);
        Agent[] agents = new Agent[5];
        SimParams p = params();
        for (int i = 0; i < 5; i++) agents[i] = new Agent(i, p);
        agents[0].setOpinion(0.5);
        agents[1].setOpinion(0.6);
        agents[2].setOpinion(-0.5);
        agents[3].setOpinion(-0.6);
        agents[4].setOpinion(0.05);
        SparseIntMatrix onlyNeutralEdges = new SparseIntMatrix();
        onlyNeutralEdges.increment(4, 0);
        onlyNeutralEdges.increment(1, 4);
        check(analyzer.computeSignModularityFromMatrix(agents, onlyNeutralEdges, 0.2) == 0.0,
                "only neutral-touching edges => Q = 0");
        SparseIntMatrix mixed = new SparseIntMatrix();
        mixed.increment(0, 1);
        mixed.increment(2, 3);
        mixed.increment(0, 2);
        double q0 = analyzer.computeSignModularityFromMatrix(agents, mixed, 0.2);
        mixed.increment(4, 0);
        mixed.increment(1, 4);
        double q1 = analyzer.computeSignModularityFromMatrix(agents, mixed, 0.2);
        check(Math.abs(q0 - q1) < 1e-9, "adding a neutral agent's edges does not change Q");
    }
}
