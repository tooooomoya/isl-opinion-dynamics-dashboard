package dynamics;

import admin.*;
import agent.*;
import analysis.*;
import constants.Const;
import experiment.*;
import gephi.*;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import network.*;
import rand.randomGenerator;
import writer.*;

public class OpinionDynamics {

    private final int t;         // MAX_SIMULATION_STEP, config-driven (cfg.steps)
    private final int agentNum;  // agent count, config-driven (cfg.n)
    private Network network;
    private final Agent[] agentSet;
    private Writer writer;
    private Analysis analyzer;
    private AssertionCheck ASChecker;
    private final SimParams params; // instance-scoped runtime params
    private final String folerPath;
    private GraphVisualize gephi;
    private RepostVisualize repostGephi;
    private double connectionProbability = Const.CONNECTION_PROB_OF_RANDOM_NW;
    private AdminOptim admin;

    private static final class PendingDelivery {
        final int followerId;
        final Post post;
        PendingDelivery(int followerId, Post post) { this.followerId = followerId; this.post = post; }
    }
    // sparse repost/relay counters (was dense int[N][N]). repostNetwork resets every 5000
    // steps for the periodic gephi snapshot; repostNetworkCumulative never resets.
    private SparseIntMatrix repostNetwork;

    // Cumulative interaction graph: who relays whom, over the whole run. Used for the
    // structural-separation axis instead of the static follow graph (Conover 2011: follow/retweet
    // graphs are segregated by construction; the cross-cutting signal lives in who-relays-whom,
    // not who-follows-whom). 
    private SparseIntMatrix repostNetworkCumulative;

    // windowed interaction graph — reset every cfg.interactionWindow steps, so its
    // assortativity/cross-cutting reflect recent (transient) relaying, not the whole run.
    private SparseIntMatrix repostNetworkWindow;

    // Homophily/hostile repost-edge split: a repost is tagged by whether it crossed
    // the relayer's own bc window at read time (Post.isOutOfBcRelay(), set in Agent.relay()) --
    // repostProb-gated ("homophily") vs outOfBCRepostProb-gated ("hostile") relays. This is a
    // mechanism-level split (which probability gate fired), independent of the sign-based
    // cross-cutting/homophily camp metrics already computed elsewhere (computeSignModularityFromMatrix
    // etc.), which stay measured as an outcome over the combined graph and are NOT redefined by
    // this split. Mirrors repostNetwork's reset-every-5000-steps snapshot semantics (feeds the
    // gephi edge-type export) and repostNetworkCumulative's whole-run semantics (feeds type-specific
    // structural read-outs); repostNetworkWindow is intentionally not split -- not needed yet.
    private SparseIntMatrix repostNetworkHomophily;
    private SparseIntMatrix repostNetworkHostile;
    private SparseIntMatrix repostNetworkCumulativeHomophily;
    private SparseIntMatrix repostNetworkCumulativeHostile;
    
    // Empirical 7-bin posting-activity fit (Const.EMPIRICAL_POST_BIN_WEIGHTS):
    // cumulative ORIGINAL post count by intrinsic-opinion bin, whole run, never reset -- unlike
    // analyzer's postOpinionVar/postShare (Analysis.clearPostCash() every step, a per-step
    // snapshot). Binned by intrinsic (fixed at spawn) opinion, not current (drifting) opinion, to
    // match how the empirical target itself was built: self-reported ideology is a fixed trait
    // measured once, not a moving daily quantity. Same population filter as postOpinionVar
    // (excludes target/hub posts). A parallel accumulator, not a change to existing per-step
    // metrics -- same pattern as the homophily/hostile repost-edge split above.
    private final long[] postCountByBin7 = new long[Const.NUM_OF_BINS_EMPIRICAL_7];

    // cumulative likes + reshares received by each author's posts (attention received), whole run
    private final long[] reactionsReceived;

    // Per-state learning diagnostics, aggregated over a logging window (STATE_LOG_INTERVAL steps):
    // how often each action was chosen in each of the 9 states, how many visits each state got, and
    // the distribution of identity fit / recognition at visit time (to set the state-bin edges).
    private static final int STATE_LOG_INTERVAL = 500;
    private final long[][] stateActionCount = new long[Agent.NUM_STATES][Agent.NUM_ACTIONS];
    private final java.util.ArrayList<Double> fitSamples = new java.util.ArrayList<>();
    private final java.util.ArrayList<Double> recSamples = new java.util.ArrayList<>();

    // per-step behavioral-event accumulators (population actors only unless noted), reset each step.
    private final StepStats stepStats = new StepStats();

    private final ExperimentConfig cfg;
    private final CalibrationLog calibration;

    // constructor
    public OpinionDynamics(ExperimentConfig cfg) {
        this.cfg = cfg;
        this.params = SimParams.from(cfg);
        this.folerPath = params.resultFolder();
        this.agentNum = cfg.n;      
        this.calibration = cfg.calibrationLog ? new CalibrationLog(agentNum) : null;
        this.t = cfg.steps;         
        this.agentSet = new Agent[agentNum];
        this.reactionsReceived = new long[agentNum];
        setFromInitial();
        this.analyzer = new Analysis(agentNum);
        this.writer = new Writer(folerPath);
        // skip all gephi construction/export when log_gexf=false (large sweeps).
        this.gephi = cfg.logGexf ? new GraphVisualize(0.00, agentSet, network) : null;
        this.repostGephi = cfg.logGexf ? new RepostVisualize(agentSet) : null;
        this.admin = new AdminOptim(agentNum, network.getAdjacencyMatrix(), params);
        if (params.fitRelative()) { // expected identity fit of a random feed = mean similarity to the whole population
            for (Agent a : agentSet) {
                if (params.fitBaselineAnalytic()) { // random feed, X uniform on [-1, 1]: E[sim] = 1 - (1 + x^2) / 4
                    a.setFitBaseline(1.0 - (1.0 + a.getOpinion() * a.getOpinion()) / 4.0);
                    continue;
                }
                double sum = 0.0;
                for (Agent b : agentSet) if (b != a) sum += Agent.similarity(a.getOpinion(), b.getOpinion());
                a.setFitBaseline(sum / Math.max(1, agentSet.length - 1));
            }
        }
        if (params.foryouShare() > 0.0 && params.foryouProfile()) {
            admin.initEstimates(randomGenerator.network()); // platform's initial estimate of every agent's X: random
        }
        this.repostNetwork = new SparseIntMatrix();
        this.repostNetworkCumulative = new SparseIntMatrix();
        this.repostNetworkWindow = new SparseIntMatrix();
        this.repostNetworkHomophily = new SparseIntMatrix();
        this.repostNetworkHostile = new SparseIntMatrix();
        this.repostNetworkCumulativeHomophily = new SparseIntMatrix();
        this.repostNetworkCumulativeHostile = new SparseIntMatrix();
    }

    private void setFromInitial() {
        // agents first: some start networks (homophily) need each agent's X to wire the graph
        setAgents();
        setNetwork();
        // network=read carries node opinions in the .gexf; load them onto the agents.
        if (cfg.networkType.equals("read")) {
            GephiReader.readGraphNodes(agentSet, cfg.readPath);
        }
    }

    // initial network resolved by NetworkFactory from cfg.
    private void setNetwork() {
        this.network = NetworkFactory.create(cfg, agentNum);
        this.network.makeNetwork(agentSet);
        if (cfg.startDeg > 0) this.network.enforceEdgeCount(agentNum * cfg.startDeg, randomGenerator.network());
        System.out.println("finish making network");
    }

    private void setAgents() {
        // the follow graph lives in AdminOptim (built from the same adjacency after this),
        // so agents no longer keep a private followList to seed here.
        for (int i = 0; i < agentNum; i++) {
            agentSet[i] = new Agent(i, params);
        }
    }


    private void errorReport() {
        ASChecker.reportASError();
    }

    // reset per-step behavioral-event accumulators.
    private void resetStepStats() {
        stepStats.reset();
    }

    //////////
    // main part of the experimental dynamics
    //////////
    public void evolve(ExperimentConfig cfg) {
        this.ASChecker = new AssertionCheck(agentSet, network, agentNum, t);
        ASChecker.snapshotOutDegrees(admin); // rewire must conserve these

        // Apply experiment configuration at t=0 and log the
        // per-run config (covariates for the randomize-then-regress analysis).
        List<InterventionSetup.HubRecord> hubs = InterventionSetup.apply(agentSet, admin, cfg);
        InterventionSetup.writeConfigLog(cfg, hubs, folerPath);

        // Model Intervention:
        // 1. Exogenously fix designated hubs' intrinsic and current opinions to assigned target positions
        for (var e : cfg.pinOpinionIds.entrySet()) {
            agentSet[e.getKey()].setIntrinsicOpinion(e.getValue());
            agentSet[e.getKey()].setOpinion(e.getValue());
            agentSet[e.getKey()].setTarget();
            agentSet[e.getKey()].setHubTier(agentSet[e.getKey()].getOpinionClass());
        }
        // 2. Silenced hubs (N-silent condition): channel set to NONE at t=0 (cannot post/repost,
        // but follow ties and feed reading remain active)
        for (int id : cfg.silentUntilIds) agentSet[id].setChannelMode(Agent.ChannelMode.NONE);

        // export gexf (R25: gated)
        if (cfg.logGexf) {
            gephi.updateGraph(agentSet, network);
            gephi.exportGraph(0, folerPath);
        }

        // export metrics (R21: build the full metrics row so the CSV header/schema is fixed
        // from step 0; empty-input metrics take their natural defaults, e.g. postOpinionVar=-1).
        writer.setSimulationStep(0);
        writer.setMetrics(buildMetricsRow());
        writer.setOpinionBins(agentSet);
        writer.write();
        writer.writeDegrees(network.getAdjacencyMatrix(), folerPath);
        // 2026-07-15: t=0 clustering was missing (only the step%5000==0 checkpoints wrote it),
        // so there was no way to fit the pure generator's own network (e.g. HK's m/A/pt) without
        // the fit being contaminated by 5000 steps of follow/unfollow dynamics. Needed for the
        // systematic-A Stage-1a calibration (generator params vs. Kwak et al. 2010's degree
        // exponent + clustering coefficient), which must be measured before any dynamics run.
        writer.writeClusteringCoefficients(analyzer.computeClusteringCoefficients(network.getAdjacencyMatrix()), folerPath);
        writer.writeAgentSnapshot(agentSet, admin, folerPath, "t0");
        if (!cfg.pinOpinionIds.isEmpty()) {
            writer.writeClassFollowerComposition(agentSet, network.getAdjacencyMatrix(), cfg.pinOpinionIds.keySet(), folerPath);
        }

        // Hoisted out of the end-of-run block below (2026-07-25): population-by-bin is fixed at
        // construction (intrinsic opinion never changes), so it's identical at every checkpoint --
        // computed once here and reused for both the periodic step%5000==0 snapshots (added below,
        // to inspect how the 7-bin posting-rate shape evolves/stabilizes over the run rather than
        // only seeing the final cumulative fit) and the final write.
        long[] popCountByBin7 = new long[Const.NUM_OF_BINS_EMPIRICAL_7];
        for (Agent a : agentSet) {
            if (!a.getTarget()) popCountByBin7[Agent.opinionToBin7(a.getIntrinsicOpinion())]++;
        }

        writeEdges("edges_t0.csv");
        for (int step = 1; step <= t; step++) {
            if (step % 1000 == 0) System.out.println("step = " + step);
            resetStepStats();

            // delayed-conduit-entry activation (inherited intervention machinery)
            if (!cfg.silentUntilIds.isEmpty() && step == cfg.activationStep) {
                for (int id : cfg.silentUntilIds) agentSet[id].setChannelMode(cfg.channel);
            }

            analyzer.clearPostCash();
            analyzer.resetFeedMap();
            writer.clearPostBins();
            writer.setSimulationStep(step);

            List<Post> postList = new ArrayList<>();
            // Deliveries are buffered and flushed after every agent has acted, so what a follower
            // sees next step does not depend on shuffle order within this step.
            List<PendingDelivery> pendingDeliveries = new ArrayList<>();

            // forgotten posts die: remove every post that has gone deadAfter steps without a like
            // or reshare (their likes stop counting toward recognition at the author's next visit).
            admin.sweepDead(step);
            for (Post dead : admin.drainEvicted()) {
                if (dead.getPostedStep() <= t - CONV_WINDOW) continue;
                int kind = dead.isRelay() ? 1 : 0;
                lifeHist[kind][Math.min(HIST_MAX, step - dead.getPostedStep())]++;
                likesHist[kind][Math.min(HIST_MAX, dead.getLikesReceived())]++;
                resharesHist[kind][Math.min(HIST_MAX, dead.getReceivedReposts())]++;
            }
            if (params.foryouShare() > 0.0) admin.rebuildAuthorIndex();

            List<Agent> shuffledAgents = new ArrayList<>(Arrays.asList(agentSet));
            Collections.shuffle(shuffledAgents, randomGenerator.dynamics());

            // Per-step global velocity ranking for the For-You feed (null when alpha=0).
            List<Post> velocityRanked = (params.trendShare() > 0.0) ? admin.rankByVelocity(step) : null;
            if (cfg.logPostLifespan) {
                for (AdminOptim.LifespanEvent ev : admin.drainLifespanEvents()) {
                    writer.logPostLifespan(step, ev.post(), ev.stillActive());
                }
            } else {
                admin.drainLifespanEvents();
            }

            for (Agent agent : shuffledAgents) {
                int agentId = agent.getId();
                agent.setTimeStep(step);
                agent.resetUsed();

                // decide whether to visit the platform at this step
                if (randomGenerator.dynamics().nextDouble() > agent.getAccessProb()) {
                    continue;
                }
                agent.setUsed();

                // the platform builds this visit's feed
                admin.AdminFeedback(agentId, agentSet, step, velocityRanked, stepStats);
                analyzer.setFeedMap(agent);

                boolean population = !agent.getTarget(); // behavioral metrics exclude pinned hubs

                // read state, learn from the transition since the previous visit, choose an action
                int state = agent.observeAndLearn(step);
                int action = agent.chooseAction(state);
                if (calibration != null) calibration.visit(agentId);
                if (population) {
                    stepStats.activeCount++;
                    stepStats.identityFitSum += agent.getLastIdentityFit();
                    stepStats.feedSizeSum += agent.getFeed().size();
                    if (agent.getFeed().isEmpty()) stepStats.emptyFeedCount++;
                    stepStats.recognitionSum += agent.getLastRecognition();
                    stepStats.actionCount[action]++;
                    stateActionCount[state][action]++;
                    fitSamples.add(agent.getLastIdentityFit());
                    recSamples.add(agent.getLastRecognition());
                    double xi = agent.getOpinion();
                    for (Post fp : agent.getFeed()) {
                        if (xi * fp.getPostOpinion() < 0) stepStats.outGroupExposureCount++;
                    }
                }

                switch (action) {
                    case Agent.POST -> {
                        Post post = agent.makePost(step);
                        if (calibration != null) calibration.original(agentId);
                        stepStats.originalPostCount++;
                        admin.addRecentPost(post);
                        for (int followerId : admin.getFollowers(agentId)) {
                            pendingDeliveries.add(new PendingDelivery(followerId, post));
                        }
                        if (population) {
                            writer.setPostBins(post);
                            analyzer.setPostCash(post);
                            postCountByBin7[Agent.opinionToBin7(agent.getIntrinsicOpinion())]++;
                        }
                        postList.add(post);
                    }
                    case Agent.LIKE -> {
                        Post src = agent.pickFromFeed(Agent.LIKE);
                        if (agent.likeGatedFor(src)) { // like_gate = noop: the drawn post is out of the like range, the like does nothing
                            agent.addGatedLike();
                        } else {
                            agent.like(src, step, admin);
                            if (step > t - CONV_WINDOW) likeConv.increment(agentId, src.getPostUserId());
                            admin.updateEstimate(agentId, src.getPostOpinion(), params.rhoLike());
                            reactionsReceived[src.getPostUserId()]++;
                            if (population) stepStats.likeCount++;
                        }
                    }
                    case Agent.RESHARE -> {
                        Post src = agent.pickFromFeed(Agent.RESHARE);
                        Post copy = agent.reshare(src, step, admin, agent.receivedViaAlgo(src));
                        if (calibration != null) calibration.reshare(agentId, src.getPostUserId(), src.getRootAuthorId());
                        admin.updateEstimate(agentId, src.getPostOpinion(), params.rhoReshare());
                        admin.notifyOriginal(copy.getRootAuthorId(), copy);
                        reactionsReceived[src.getPostUserId()]++;
                        stepStats.allRepostCount++;
                        if (population) {
                            stepStats.repostCount++;
                            if (agent.getOpinion() * src.getPostOpinion() < 0) stepStats.crossRepostCount++;
                        }
                        int srcAuthor = src.getPostUserId();
                        repostNetwork.increment(agentId, srcAuthor);
                        if (step > t - CONV_WINDOW) reshareConv.increment(agentId, srcAuthor);
                        repostNetworkCumulative.increment(agentId, srcAuthor);
                        repostNetworkWindow.increment(agentId, srcAuthor);
                        repostNetworkHomophily.increment(agentId, srcAuthor); // all reshares; no bc gate any more
                        repostNetworkCumulativeHomophily.increment(agentId, srcAuthor);
                        if (cfg.logRepostCascade) writer.logRepostCascade(step, copy, agent.getOpinion());
                        admin.addRecentPost(copy);
                        for (int followerId : admin.getFollowers(agentId)) {
                            pendingDeliveries.add(new PendingDelivery(followerId, copy));
                        }
                        // notify_original: the original author also receives the copy in the chrono FIFO cache, like a followee's post
                        int origAuthor = copy.getRootAuthorId();
                        if (params.notifyMax() > 0 && origAuthor != agentId && !admin.getFollowers(agentId).contains(origAuthor)) {
                            pendingDeliveries.add(new PendingDelivery(origAuthor, copy));
                        }
                    }
                    default -> { // Agent.REWIRE
                        int m = agent.rewire(admin, agentSet);
                        if (m >= 0 && population) stepStats.rewireCount++;
                    }
                }

                agent.updateValues(); // value drift; a no-op while mu = 0
                agent.resetPostCash();
                agent.resetFeed();
            }

            // flush this step's buffered deliveries now that every agent has taken its turn
            for (PendingDelivery pd : pendingDeliveries) {
                agentSet[pd.followerId].addToPostCash(pd.post);
            }

            if (step % params.assertInterval() == 0) {
                ASChecker.assertionChecker(agentSet, admin, agentNum, step);
            }

            if (step % 5000 == 0) {
                double[][] currentW = admin.getAdjacencyMatrix();
                if (cfg.logGexf) {
                    network.setAdjacencyMatrix(currentW);
                    gephi.updateGraph(agentSet, network);
                    gephi.exportGraph(step, folerPath);
                    repostGephi.updateGraph(agentSet, repostNetworkHomophily.toDense(agentNum),
                            repostNetworkHostile.toDense(agentNum), step);
                    repostGephi.exportGraph(step, folerPath);
                }
                int[][] repostAdjInt = repostNetwork.toDense(agentNum);
                double[][] repostAdj = new double[repostAdjInt.length][];
                for (int i = 0; i < repostAdjInt.length; i++) {
                    repostAdj[i] = new double[repostAdjInt[i].length];
                    for (int j = 0; j < repostAdjInt[i].length; j++) repostAdj[i][j] = repostAdjInt[i][j];
                }
                writer.writeRepostDegrees(repostAdj, folerPath);
                writer.writeRepostClusteringCoefficients(analyzer.computeClusteringCoefficients(repostAdj), folerPath);
                double qSignRepost = analyzer.computeSignModularityFromMatrix(agentSet, repostNetwork, params.neutralBandHalfWidth());
                repostNetwork.clear();
                repostNetworkHomophily.clear();
                repostNetworkHostile.clear();
                writer.writeDegrees(currentW, folerPath);
                if (!cfg.pinOpinionIds.isEmpty()) {
                    writer.writeClassFollowerComposition(agentSet, currentW, cfg.pinOpinionIds.keySet(), folerPath);
                }
                writer.writeClusteringCoefficients(analyzer.computeClusteringCoefficients(currentW), folerPath);
                writer.writeModularity(step, analyzer.computeSignModularity(agentSet, admin, params.neutralBandHalfWidth()), qSignRepost, folerPath);
                writer.writeEchoChamberByClass(analyzer.computeEchoChamberByClass(agentSet, currentW), folerPath);
                writer.writePostBin7(postCountByBin7, popCountByBin7, folerPath, step);
            }
            if (step % STATE_LOG_INTERVAL == 0) writeStateLog(step);
            curStep = step;
            if (step % cfg.metricsEvery == 0 || step == t) exportStepMetrics();
            if (calibration != null && (step % 5000 == 0 || step == t)) {
                try {
                    calibration.flush(step, agentSet, Path.of(folerPath, "metrics"));
                } catch (java.io.IOException e) {
                    throw new java.io.UncheckedIOException("Calibration log failed", e);
                }
            }
            if (step == t / 2) writeEdges("edges_mid.csv");
            if (step % cfg.interactionWindow == 0) repostNetworkWindow.clear();
        }
        writer.writeAgentSnapshot(agentSet, admin, folerPath, "final");
        writeQTable();
        // Empirical 7-bin fit artifact (2026-07-21): population-by-bin is a diagnostic (should
        // trivially match Const.EMPIRICAL_OPINION_BIN_COUNTS' proportions when init_dist=empirical,
        // up to sampling noise -- confirms the sampler is working, not itself a fitted quantity);
        // postCountByBin7 is the actual calibration-loss target (see app_pol_baseline_bo_calibration.py).
        // popCountByBin7 computed once, before the loop (see above).
        writer.writePostBin7(postCountByBin7, popCountByBin7, folerPath);
        // Final flush for batch writer
        writer.flush();
    }

    // metrics/agent_actions.csv: per window and agent, how many times each action was chosen (agents with no visit omitted).
    private long[][] prevActionTotals;
    private long[] prevGated;
    private void writeAgentActions(int step, Path dir) throws java.io.IOException {
        if (prevActionTotals == null) { prevActionTotals = new long[agentSet.length][Agent.NUM_ACTIONS]; prevGated = new long[agentSet.length]; }
        Path f = dir.resolve("agent_actions.csv");
        StringBuilder sb = new StringBuilder();
        if (!Files.exists(f)) sb.append("step,agentId,nPost,nLike,nReshare,nRewire,nLikeGated\n");
        for (Agent ag : agentSet) {
            long[] d = new long[Agent.NUM_ACTIONS];
            long any = 0;
            for (int a = 0; a < Agent.NUM_ACTIONS; a++) {
                long tot = 0;
                for (int st = 0; st < Agent.NUM_STATES; st++) tot += ag.getDecisions()[st][a];
                d[a] = tot - prevActionTotals[ag.getId()][a];
                prevActionTotals[ag.getId()][a] = tot;
                any += d[a];
            }
            long gated = ag.getLikeGated() - prevGated[ag.getId()];
            prevGated[ag.getId()] = ag.getLikeGated();
            if (any == 0) continue;
            sb.append(step).append(',').append(ag.getId());
            for (int a = 0; a < Agent.NUM_ACTIONS; a++) sb.append(',').append(d[a]);
            sb.append(',').append(gated).append('\n');
        }
        Files.writeString(f, sb.toString(), java.nio.file.StandardOpenOption.CREATE, java.nio.file.StandardOpenOption.APPEND);
    }

    // End-of-run dump of every agent's Q table: degrees/q_table_final.csv, one row per (agent, state) with the four
    // Q values and how often that agent chose each action in that state (zero counts = Q still at its initial value).
    /** Follow edges (follower,followee) as of now, to degrees/<fileName>. */
    private void writeEdges(String fileName) {
        try {
            StringBuilder eb = new StringBuilder("follower,followee\n");
            for (Agent ag : agentSet) for (int fe : admin.getFollowees(ag.getId())) eb.append(ag.getId()).append(',').append(fe).append('\n');
            Files.writeString(Path.of(folerPath, "degrees", fileName), eb.toString());
        } catch (java.io.IOException e) {
            System.err.println("[edges] failed: " + e.getMessage());
        }
    }

    private void writeQTable() {
        try {
            StringBuilder sb = new StringBuilder("agentId,followerCount,state,qPost,qLike,qReshare,qRewire,nPost,nLike,nReshare,nRewire\n");
            for (Agent ag : agentSet) {
                for (int st = 0; st < Agent.NUM_STATES; st++) {
                    double[] qq = ag.getQ()[st];
                    long[] dd = ag.getDecisions()[st];
                    sb.append(ag.getId()).append(',').append(admin.getFollowers(ag.getId()).size()).append(',').append(st);
                    for (int a = 0; a < Agent.NUM_ACTIONS; a++) sb.append(',').append(String.format("%.5f", qq[a]));
                    for (int a = 0; a < Agent.NUM_ACTIONS; a++) sb.append(',').append(dd[a]);
                    sb.append('\n');
                }
            }
            Files.writeString(Path.of(folerPath, "degrees", "q_table_final.csv"), sb.toString());
            writeEdges("edges_final.csv");
            StringBuilder rc = new StringBuilder("type,actor,author,count\n");
            for (var row : likeConv.rowEntries()) for (var e : row.getValue().entrySet()) rc.append("like,").append(row.getKey()).append(',').append(e.getKey()).append(',').append(e.getValue()).append('\n');
            for (var row : reshareConv.rowEntries()) for (var e : row.getValue().entrySet()) rc.append("reshare,").append(row.getKey()).append(',').append(e.getKey()).append(',').append(e.getValue()).append('\n');
            Files.writeString(Path.of(folerPath, "metrics", "reactions_conv.csv"), rc.toString());
            StringBuilder ph = new StringBuilder("kind,value,life,likes,reshares\n");
            for (int k = 0; k < 2; k++) for (int v = 0; v <= HIST_MAX; v++) {
                if (lifeHist[k][v] + likesHist[k][v] + resharesHist[k][v] > 0)
                    ph.append(k == 0 ? "orig" : "copy").append(',').append(v).append(',').append(lifeHist[k][v]).append(',').append(likesHist[k][v]).append(',').append(resharesHist[k][v]).append('\n');
            }
            Files.writeString(Path.of(folerPath, "metrics", "post_life_hist.csv"), ph.toString());
        } catch (java.io.IOException e) {
            System.err.println("[q table] failed: " + e.getMessage());
        }
    }

    // Window report: metrics/state_action.csv has one row per (step, state, action) with the count of
    // choices in the window and the population-mean learned Q(state, action); metrics/fit_quantiles.csv
    // has quantiles of identity fit and recognition over the window's visits.
    // State index = 3 * identity-fit level + recognition level (levels 0 = low, 1 = mid, 2 = high).
    private void writeStateLog(int step) {
        try {
            Path dir = Path.of(folerPath, "metrics");
            Path sa = dir.resolve("state_action.csv");
            Path fq = dir.resolve("fit_quantiles.csv");
            StringBuilder sb = new StringBuilder();
            if (!Files.exists(sa)) sb.append("step,state,fit_level,rec_level,action,count,visits_in_state,meanQ\n");
            for (int st = 0; st < Agent.NUM_STATES; st++) {
                long visits = 0;
                for (int a = 0; a < Agent.NUM_ACTIONS; a++) visits += stateActionCount[st][a];
                for (int a = 0; a < Agent.NUM_ACTIONS; a++) {
                    double qSum = 0.0;
                    int pop = 0;
                    for (Agent ag : agentSet) {
                        if (ag.getTarget()) continue;
                        qSum += ag.getQ()[st][a];
                        pop++;
                    }
                    sb.append(step).append(',').append(st).append(',').append(st / 3).append(',').append(st % 3)
                      .append(',').append(Agent.ACTION_NAMES[a]).append(',').append(stateActionCount[st][a])
                      .append(',').append(visits).append(',')
                      .append(String.format("%.5f", pop > 0 ? qSum / pop : 0.0)).append('\n');
                }
            }
            Files.writeString(sa, sb.toString(), java.nio.file.StandardOpenOption.CREATE, java.nio.file.StandardOpenOption.APPEND);

            StringBuilder qb = new StringBuilder();
            if (!Files.exists(fq)) qb.append("step,variable,n,q10,q33,q50,q67,q90\n");
            appendQuantiles(qb, step, "identityFit", fitSamples);
            appendQuantiles(qb, step, "recognition", recSamples);
            Files.writeString(fq, qb.toString(), java.nio.file.StandardOpenOption.CREATE, java.nio.file.StandardOpenOption.APPEND);
            Agent.flushLearningLog(step, dir);
            writeAgentActions(step, dir);
        } catch (java.io.IOException e) {
            System.err.println("[state log] failed: " + e.getMessage());
        }
        for (long[] row : stateActionCount) Arrays.fill(row, 0L);
        fitSamples.clear();
        recSamples.clear();
    }

    private static void appendQuantiles(StringBuilder sb, int step, String name, java.util.List<Double> v) {
        sb.append(step).append(',').append(name).append(',').append(v.size());
        if (v.isEmpty()) { sb.append(",,,,,\n"); return; }
        double[] a = v.stream().mapToDouble(Double::doubleValue).toArray();
        Arrays.sort(a);
        for (double q : new double[]{0.10, 0.33, 0.50, 0.67, 0.90}) {
            sb.append(',').append(String.format("%.4f", a[(int) Math.min(a.length - 1, Math.floor(q * a.length))]));
        }
        sb.append('\n');
    }

    // Per-step metric export: build the metrics row, set the opinion-bin stream, write.
    private void exportStepMetrics() {
        writer.setMetrics(buildMetricsRow());
        writer.setOpinionBins(agentSet);
        writer.write();
    }

    // Gini coefficient of non-negative values (0 = equal, 1 = one holder has everything).
    private static double gini(double[] v) {
        int m = v.length;
        if (m == 0) return 0.0;
        double[] a = v.clone();
        Arrays.sort(a);
        double sum = 0.0, weighted = 0.0;
        for (int i = 0; i < m; i++) { sum += a[i]; weighted += (i + 1) * a[i]; }
        if (sum <= 0.0) return 0.0;
        return (2.0 * weighted) / (m * sum) - (m + 1.0) / m;
    }

    // Share of all received reactions held by the top 1% of authors.
    private static double topShare(double[] v, double frac) {
        int m = v.length;
        if (m == 0) return 0.0;
        double[] a = v.clone();
        Arrays.sort(a);
        double total = 0.0;
        for (double x : a) total += x;
        if (total <= 0.0) return 0.0;
        int k = Math.max(1, (int) Math.ceil(frac * m));
        double top = 0.0;
        for (int i = 0; i < k; i++) top += a[m - 1 - i];
        return top / total;
    }

    // Assemble the per-step metrics row. Insertion order here IS the CSV column order.
    // Network-wide metrics (assortativity, cross-cutting, disagreement) cost O(edges) each; with metrics_heavy_every = k they are recomputed
    // every k steps and carried forward in between (the cheap per-step counters stay exact). k = 1 reproduces the old behaviour.
    private int curStep = 0;

    // Converged-window diagnostics (last CONV_WINDOW steps): who reacted to whom, and how long / how much posts live.
    private static final int CONV_WINDOW = 5000, HIST_MAX = 20000;
    private final SparseIntMatrix likeConv = new SparseIntMatrix();      // liker -> author of the liked post
    private final SparseIntMatrix reshareConv = new SparseIntMatrix();   // resharer -> author of the reshared post
    private final long[][] lifeHist = new long[2][HIST_MAX + 1];         // [original|reshare copy][lifetime in steps], posts created in the window
    private final long[][] likesHist = new long[2][HIST_MAX + 1];        // likes received by a post over its life
    private final long[][] resharesHist = new long[2][HIST_MAX + 1];     // reshares received by a post over its life
    private final java.util.Map<String, Double> heavyCache = new java.util.HashMap<>();
    private double heavy(String name, java.util.function.DoubleSupplier f) {
        int k = cfg.metricsHeavyEvery;
        Double cached = heavyCache.get(name);
        if (k <= 1 || cached == null || curStep % k == 0) { double v = f.getAsDouble(); heavyCache.put(name, v); return v; }
        return cached;
    }

    private MetricsRow buildMetricsRow() {
        MetricsRow row = new MetricsRow();
        row.put("opinionVar", analyzer.computeVarianceOpinion(agentSet));
        analyzer.computePostVariance();
        row.put("postOpinionVar", analyzer.getPostOpinionVar());
        analyzer.computeExposureMetrics(agentSet);
        row.put("exposureOpinionVar", analyzer.getExposureOpinionVar());
        row.put("exposureOpinionMean", analyzer.getExposureOpinionMean());
        row.put("rewire", stepStats.rewireCount);
        row.put("opinionAvg", analyzer.computeMeanOpinion(agentSet));
        row.put("shannonIndex", analyzer.computeShannonWienerIndex(agentSet));
        row.put("disagreement", heavy("disagreement", () -> analyzer.computeDisagreement(agentSet, admin)));
        row.put("opinionAssortativity", heavy("opinionAssortativity", () -> analyzer.computeOpinionAssortativity(agentSet, admin)));
        row.put("crossCuttingFraction", heavy("crossCuttingFraction", () -> analyzer.computeCrossCuttingFraction(agentSet, admin, params.neutralBandHalfWidth())));
        row.put("opinionKurtosis", analyzer.computeOpinionKurtosis(agentSet));
        row.put("interactionAssortativity", heavy("interactionAssortativity", () -> analyzer.computeInteractionAssortativity(agentSet, repostNetworkCumulative)));
        row.put("interactionCrossCuttingFraction", heavy("interactionCrossCuttingFraction", () -> analyzer.computeInteractionCrossCuttingFraction(agentSet, repostNetworkCumulative, params.neutralBandHalfWidth())));
        row.put("interactionAssortativityW", heavy("interactionAssortativityW", () -> analyzer.computeInteractionAssortativity(agentSet, repostNetworkWindow)));
        row.put("interactionCrossCuttingFractionW", heavy("interactionCrossCuttingFractionW", () -> analyzer.computeInteractionCrossCuttingFraction(agentSet, repostNetworkWindow, params.neutralBandHalfWidth())));
        analyzer.computeFeedMetrics(agentSet);
        double[] feedMean = analyzer.getFeedMeanArray();
        double[] feedVar = analyzer.getFeedVarArray();
        for (int i = 0; i < Const.NUM_OF_BINS_OF_OPINION; i++) row.put("feedPostOpinionMean_" + i, feedMean[i]);
        for (int i = 0; i < Const.NUM_OF_BINS_OF_OPINION; i++) row.put("feedPostOpinionVar_" + i, feedVar[i]);
        analyzer.computePostShareArray(agentSet);
        double[] postShare = analyzer.getPostShareArray();
        for (int i = 0; i < Const.NUM_OF_BINS_OF_OPINION; i++) row.put("postShare_" + i, postShare[i]);
        row.put("bimodalityCoeff", analyzer.computeBimodalityCoefficient(agentSet));

        // ---- action choice and learning (population visits this step) ----
        int visits = stepStats.activeCount;
        row.put("visitCount", visits);
        for (int a = 0; a < Agent.NUM_ACTIONS; a++) {
            row.put("actionShare_" + Agent.ACTION_NAMES[a], visits > 0 ? (double) stepStats.actionCount[a] / visits : 0.0);
        }
        row.put("meanIdentityFit", visits > 0 ? stepStats.identityFitSum / visits : 0.0);
        row.put("meanFeedSize", visits > 0 ? stepStats.feedSizeSum / visits : 0.0);
        row.put("emptyFeedShare", visits > 0 ? stepStats.emptyFeedCount / (double) visits : 0.0);
        row.put("meanRecognition", visits > 0 ? stepStats.recognitionSum / visits : 0.0);
        // mean learned value of each action, over population agents and all 9 states
        double[] qMean = new double[Agent.NUM_ACTIONS];
        int pop = 0;
        for (Agent ag : agentSet) {
            if (ag.getTarget()) continue;
            pop++;
            for (double[] rowQ : ag.getQ()) for (int a = 0; a < Agent.NUM_ACTIONS; a++) qMean[a] += rowQ[a];
        }
        for (int a = 0; a < Agent.NUM_ACTIONS; a++) {
            row.put("meanQ_" + Agent.ACTION_NAMES[a], pop > 0 ? qMean[a] / (pop * Agent.NUM_STATES) : 0.0);
        }
        row.put("likeCount", stepStats.likeCount);
        row.put("crossRepostRate", stepStats.repostCount > 0 ? (double) stepStats.crossRepostCount / stepStats.repostCount : 0.0);
        row.put("originalPostCount", stepStats.originalPostCount);
        row.put("repostCount", stepStats.allRepostCount);

        // ---- attention economy: who receives reactions, how long posts live ----
        // reactionsReceived = cumulative likes + reshares of posts whose source author is i.
        double[] rr = new double[pop];
        int k = 0;
        for (Agent ag : agentSet) if (!ag.getTarget()) rr[k++] = reactionsReceived[ag.getId()];
        row.put("attnGini", gini(rr));
        row.put("attnTop1pctShare", topShare(rr, 0.01));
        row.put("alivePosts", admin.getAlivePostCount());
        row.put("createdPosts", admin.getCreatedPostCount());
        row.put("diedPosts", admin.getDiedPostCount());
        // supply/demand: posts created per step relative to reactions available per step (one per visit)
        row.put("postsPerVisit", visits > 0 ? (double) (stepStats.originalPostCount + stepStats.allRepostCount) / visits : 0.0);
        row.put("postLifespanMean", admin.getPostLifespanMean());
        row.put("postStillActiveAtEvictionFrac", admin.getPostStillActiveAtEvictionFrac());
        row.put("estError", admin.meanEstimateError(agentSet)); // mean |Xhat - X| (NaN when the platform holds no estimates)

        // Feed-composition-by-camp (reader's 5-bin opinionClass; _0.._4 suffix for dashboard families)
        for (int i = 0; i < Const.NUM_OF_BINS_OF_OPINION; i++) {
            int cnt = stepStats.feedClassAgentCount[i];
            row.put("popCountByClass_" + i, cnt);
            row.put("feedTrendCountMean_" + i, cnt > 0 ? stepStats.feedTrendCountSum[i] / cnt : 0.0);
            row.put("feedForYouCountMean_" + i, cnt > 0 ? stepStats.feedForYouCountSum[i] / cnt : 0.0);
            row.put("feedChronoCountMean_" + i, cnt > 0 ? stepStats.feedChronoCountSum[i] / cnt : 0.0);
            row.put("feedRepostCountMean_" + i, cnt > 0 ? stepStats.feedRepostCountSum[i] / cnt : 0.0);
            row.put("feedOriginalCountMean_" + i, cnt > 0 ? stepStats.feedOriginalCountSum[i] / cnt : 0.0);
            row.put("feedNeutCountMean_" + i, cnt > 0 ? stepStats.feedNeutCountSum[i] / cnt : 0.0);
            row.put("feedHubCountMean_" + i, cnt > 0 ? stepStats.feedHubCountSum[i] / cnt : 0.0);
        }
        for (int r = 0; r < Const.NUM_OF_BINS_OF_OPINION; r++) {
            int cnt = stepStats.feedClassAgentCount[r];
            for (int a = 0; a < Const.NUM_OF_BINS_OF_OPINION; a++) {
                row.put("feedAuthorClass" + a + "CountMean_" + r,
                        cnt > 0 ? stepStats.feedAuthorClassCountSum[r][a] / cnt : 0.0);
            }
        }
        return row;
    }

    // R27: recursive delete for force=true (Files.delete alone refuses non-empty directories).
    private static void deleteRecursively(Path dir) throws java.io.IOException {
        try (var stream = Files.walk(dir)) {
            for (Path p : stream.sorted(Comparator.reverseOrder()).toList()) {
                Files.delete(p);
            }
        }
    }

    public static void main(String[] args) {

        ExperimentConfig cfg = ExperimentConfig.fromArgs(args);
        randomGenerator.init(cfg.seed, cfg.resolvedNetSeed()); // R15: named streams

        // R20: all runtime knobs now flow through the immutable SimParams built inside the
        // simulator from cfg — no mutable Const globals to overwrite here.
        String resultFolder = cfg.resultFolder();

        String[] subfolders = {
            "clusterings",
            "degrees",
            "figures",
            "GEXF",
            "metrics",
            "opinion",
            "posts"
        };

        try {
            Path resultDir = Path.of(resultFolder);
            // R26: never overwrite an existing run — abort instead (results are precious;
            // the tag()-based folder name makes a collision a real configuration collision).
            // R27: force=true is an explicit opt-in to delete and redo it anyway.
            if (Files.exists(resultDir)) {
                if (!cfg.force) {
                    System.err.println("[ABORT] result folder already exists: " + resultDir
                            + " — move/delete it, change seed/config, or pass force=true.");
                    return;
                }
                System.err.println("[force=true] deleting pre-existing result folder: " + resultDir);
                deleteRecursively(resultDir);
            }
            Files.createDirectories(resultDir);

            // サブフォルダ作成
            for (String sub : subfolders) {
                Path subDir = resultDir.resolve(sub);
                if (!Files.exists(subDir)) {
                    Files.createDirectories(subDir);
                }
            }
        } catch (Exception e) {
            System.err.println("Failed to create result folders: " + e.getMessage());
            e.printStackTrace();
            return;
        }

        Instant start = Instant.now();

        OpinionDynamics simulator = new OpinionDynamics(cfg);
        simulator.evolve(cfg);

        Instant end = Instant.now();

        Duration timeElapsed = Duration.between(start, end);
        long s = timeElapsed.getSeconds();
        long h = s / 3600;
        long m = (s % 3600) / 60;
        long sec = s % 60;

        System.out.printf("Elapsed time:   %02d:%02d:%02d\n", h, m, sec);

        // print some major information about the simulation parameter
        simulator.errorReport();
    }
}
