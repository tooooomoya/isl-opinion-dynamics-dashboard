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

    // per-step behavioral-event accumulators (population actors only unless noted), reset each step.
    private final StepStats stepStats = new StepStats();

    private final ExperimentConfig cfg;

    // constructor
    public OpinionDynamics(ExperimentConfig cfg) {
        this.cfg = cfg;
        this.params = SimParams.from(cfg);
        this.folerPath = params.resultFolder();
        this.agentNum = cfg.n;      
        this.t = cfg.steps;         
        this.agentSet = new Agent[agentNum];
        setFromInitial();
        this.analyzer = new Analysis(agentNum);
        this.writer = new Writer(folerPath);
        // skip all gephi construction/export when log_gexf=false (large sweeps).
        this.gephi = cfg.logGexf ? new GraphVisualize(0.00, agentSet, network) : null;
        this.repostGephi = cfg.logGexf ? new RepostVisualize(agentSet) : null;
        this.admin = new AdminOptim(agentNum, network.getAdjacencyMatrix(), params);
        this.repostNetwork = new SparseIntMatrix();
        this.repostNetworkCumulative = new SparseIntMatrix();
        this.repostNetworkWindow = new SparseIntMatrix();
        this.repostNetworkHomophily = new SparseIntMatrix();
        this.repostNetworkHostile = new SparseIntMatrix();
        this.repostNetworkCumulativeHomophily = new SparseIntMatrix();
        this.repostNetworkCumulativeHostile = new SparseIntMatrix();
    }

    private void setFromInitial() {
        setNetwork();
        //　trim over-cap out-degree at t=0 so the initial condition satisfies the model's own
        // follow cap (maxFollowCapacity)
        if (cfg.initPrune.equals("trim")) {
            pruneOverCapacity();
        }
        setAgents();
        // network=read carries node opinions in the .gexf; load them onto the agents.
        if (cfg.networkType.equals("read")) {
            GephiReader.readGraphNodes(agentSet, cfg.readPath);
        }
    }

    // randomly remove followees from over-cap nodes (network stream) down to the cap, so the
    // agent follow-lists and admin (both derived from this adjacency) start consistent with it.
    private void pruneOverCapacity() {
        int cap = (int) params.maxFollowCapacity();
        double[][] w = network.getAdjacencyMatrix();
        for (int i = 0; i < agentNum; i++) {
            List<Integer> outs = new ArrayList<>();
            for (int j = 0; j < agentNum; j++) if (w[i][j] > 0.0) outs.add(j);
            if (outs.size() <= cap) continue;
            Collections.shuffle(outs, randomGenerator.network());
            for (int k = cap; k < outs.size(); k++) network.removeEdge(i, outs.get(k));
        }
    }

    // initial network resolved by NetworkFactory from cfg.
    private void setNetwork() {
        this.network = NetworkFactory.create(cfg, agentNum);
        this.network.makeNetwork(agentSet);
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
        writer.setMetrics(buildMetricsRow(0, 0));
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

        int followActionNum;
        int unfollowActionNum;

        for (int step = 1; step <= t; step++) {
            if (step % 1000 == 0) System.out.println("step = " + step);
            followActionNum = 0;
            unfollowActionNum = 0;
            resetStepStats(); // R1/R6 per-step behavioral-event counters

            // 2026-08-02: delayed-conduit-entry activation (see ExperimentConfig.silentUntilIds).
            if (!cfg.silentUntilIds.isEmpty() && step == cfg.activationStep) {
                for (int id : cfg.silentUntilIds) agentSet[id].setChannelMode(cfg.channel);
            }

            analyzer.clearPostCash();
            analyzer.resetFeedMap();
            writer.clearPostBins();
            writer.setSimulationStep(step);

            List<Post> postList = new ArrayList<>();
            // 2026-08-03: buffered postCash deliveries, flushed after the shuffledAgents loop
            // below completes (see PendingDelivery javadoc above) -- decouples "who posted when"
            // from "who sees it this step vs next step."
            List<PendingDelivery> pendingDeliveries = new ArrayList<>();

            List<Agent> shuffledAgents = new ArrayList<>(Arrays.asList(agentSet));
            Collections.shuffle(shuffledAgents, randomGenerator.dynamics());

            // Per-step global velocity ranking for the For-You feed (null when alpha=0).
            List<Post> velocityRanked = (params.feedAlgoShare() > 0.0) ? admin.rankByVelocity(step) : null;
            // 2026-07-29: drain this step's post-eviction lifespan events (accumulated inside
            // rankByVelocity's pruneRecentPosts call above) to the dashboard's per-post log.
            if (cfg.logPostLifespan) {
                for (AdminOptim.LifespanEvent ev : admin.drainLifespanEvents()) {
                    writer.logPostLifespan(step, ev.post(), ev.stillActive());
                }
            }

            for (Agent agent : shuffledAgents) {
                int agentId = agent.getId();
                agent.setTimeStep(step);
                agent.resetUsed();

                // decide whether to use platform at this step
                if (randomGenerator.dynamics().nextDouble() > agent.getAccessProb()) {
                    continue;
                }
                agent.setUsed();

                // admin sets user's feed
                admin.AdminFeedback(agentId, agentSet, step, velocityRanked, stepStats);
                analyzer.setFeedMap(agent);

                boolean population = !agent.getTarget(); // R1: behavioral metrics exclude hubs
                if (population) {
                    stepStats.activeCount++;
                    double oi = agent.getOpinion();
                    for (Post fp : agent.getFeed()) {
                        if (oi * fp.getPostOpinion() < 0) stepStats.outGroupExposureCount++;
                    }
                }

                /////// repost (like)
                List<Post> repostedPostList = agent.repost(agentSet);
                if (population) {
                    stepStats.repostCount += agent.getLastReposts();
                    stepStats.crossRepostCount += agent.getLastCrossReposts();
                }
                stepStats.allRepostCount += repostedPostList.size();
                for (Post repostedPost : repostedPostList) {
                    repostNetwork.increment(agentId, repostedPost.getPostUserId());
                    repostNetworkCumulative.increment(agentId, repostedPost.getPostUserId());
                    repostNetworkWindow.increment(agentId, repostedPost.getPostUserId()); // R16.3
                    if (repostedPost.isOutOfBcRelay()) {
                        repostNetworkHostile.increment(agentId, repostedPost.getPostUserId());
                        repostNetworkCumulativeHostile.increment(agentId, repostedPost.getPostUserId());
                    } else {
                        repostNetworkHomophily.increment(agentId, repostedPost.getPostUserId());
                        repostNetworkCumulativeHomophily.increment(agentId, repostedPost.getPostUserId());
                    }
                    if (cfg.logRepostCascade) writer.logRepostCascade(step, repostedPost, agent.getOpinion()); // R19
                    // Optimized post distribution using adjacency list; delivery batched to
                    // end-of-step (see PendingDelivery above), not immediate.
                    for (int followerId : admin.getFollowers(agentId)) {
                        pendingDeliveries.add(new PendingDelivery(followerId, repostedPost));
                    }
                }

                /////// follow
                int[] followedIds = agent.follow(agentSet, admin);

                /////// unfollow
                int unfollowedId = agent.unfollow(admin);

                // R1: behavioral-hostility events (population actors only).
                if (population) {
                    stepStats.blockCount += agent.getLastBlocks();
                    if (followedIds[0] >= 0) stepStats.followCount++; // 2026-08-06: population-only counterpart to unfollowCount below
                    if (followedIds[1] >= 0) { // eviction
                        stepStats.evictionCount++;
                        if (agent.getOpinion() * agentSet[followedIds[1]].getOpinion() < 0) stepStats.outGroupSanctionCount++;
                    }
                    if (unfollowedId >= 0) {
                        stepStats.unfollowCount++;
                        if (agent.getOpinion() * agentSet[unfollowedId].getOpinion() < 0) stepStats.outGroupSanctionCount++;
                    }
                }

                /////// post
                // Exp A: a hub with posting disabled broadcasts no original posts.
                if (agent.isPostEnabled() && randomGenerator.dynamics().nextDouble() < agent.getPostProb()) {
                    Post post = agent.makePost(step);
                    stepStats.originalPostCount++; // R6
                    // Register into the For-You candidate window (velocity accrues via reposts).
                    if (params.feedAlgoShare() > 0.0) {
                        admin.addRecentPost(post);
                    }
                    // Optimized post distribution using adjacency list; delivery batched to
                    // end-of-step (see PendingDelivery above), not immediate.
                    for (int followerId : admin.getFollowers(agentId)) {
                        pendingDeliveries.add(new PendingDelivery(followerId, post));
                    }
                    // C3: manipulated hubs' own posts are excluded from the polarization
                    // metric (postOpinionVar) so it reflects the population, not the
                    // exogenously fixed hub opinion. The post is still broadcast above.
                    if (!agent.getTarget()) {
                        writer.setPostBins(post);
                        analyzer.setPostCash(post);
                        postCountByBin7[Agent.opinionToBin7(agent.getIntrinsicOpinion())]++;
                    }
                    postList.add(post);
                }

                agent.updateMyself(agentSet, stepStats);
                // R22: follow/unfollow mutate the admin-owned graph inline; no deferred update.
                agent.resetPostCash();
                agent.resetFeed();

                if (followedIds[0] >= 0) {
                    followActionNum++;
                }

                if (unfollowedId >= 0) {
                    unfollowActionNum++;
                }
            }

            // 2026-08-03: flush this step's buffered postCash deliveries now that every agent has
            // taken its turn (see PendingDelivery javadoc above) -- a follower's feed next step
            // will see everything posted/reposted this step regardless of shuffle order, and no
            // follower can see this step's content within this same step.
            for (PendingDelivery pd : pendingDeliveries) {
                agentSet[pd.followerId].addToPostCash(pd.post);
            }

            // R23a: invariant checks run every ASSERT_INTERVAL steps (adjacency-list based,
            // no per-step dense-matrix materialization; assert_int=1 restores legacy cadence)
            if (step % params.assertInterval() == 0) {
                ASChecker.assertionChecker(agentSet, admin, agentNum, step);
            }

            if (step % 5000 == 0) {
                double[][] currentW = admin.getAdjacencyMatrix();
                if (cfg.logGexf) { // R25
                    network.setAdjacencyMatrix(currentW);
                    gephi.updateGraph(agentSet, network);
                    gephi.exportGraph(step, folerPath);
                    // R23b: dense snapshot materialized only here (export cadence, not per step)
                    repostGephi.updateGraph(agentSet, repostNetworkHomophily.toDense(agentNum),
                            repostNetworkHostile.toDense(agentNum), step);
                    repostGephi.exportGraph(step, folerPath);
                }
                // 2026-07-15: repost-graph structural fit (degree/clustering/modularity), computed
                // on this same repostNetwork matrix BEFORE it clears below, so these numbers
                // describe exactly the graph repostGephi just exported (see Writer.writeRepostDegrees).
                int[][] repostAdjInt = repostNetwork.toDense(agentNum);
                double[][] repostAdj = new double[repostAdjInt.length][];
                for (int i = 0; i < repostAdjInt.length; i++) {
                    repostAdj[i] = new double[repostAdjInt[i].length];
                    for (int j = 0; j < repostAdjInt[i].length; j++) repostAdj[i][j] = repostAdjInt[i][j];
                }
                writer.writeRepostDegrees(repostAdj, folerPath);
                writer.writeRepostClusteringCoefficients(analyzer.computeClusteringCoefficients(repostAdj), folerPath);
                double qSignRepost = analyzer.computeSignModularityFromMatrix(agentSet, repostNetwork, params.neutralBandHalfWidth());
                repostNetwork.clear(); // always: bound the resettable window's memory
                repostNetworkHomophily.clear();
                repostNetworkHostile.clear();
                writer.writeDegrees(currentW, folerPath);
                if (!cfg.pinOpinionIds.isEmpty()) {
                    writer.writeClassFollowerComposition(agentSet, currentW, cfg.pinOpinionIds.keySet(), folerPath);
                }
                writer.writeClusteringCoefficients(analyzer.computeClusteringCoefficients(currentW), folerPath);
                writer.writeModularity(step, analyzer.computeSignModularity(agentSet, admin, params.neutralBandHalfWidth()), qSignRepost, folerPath); // R16.4
                // 2026-08-06: per-opinion-class echo-chamber structure on the follow graph (Analysis.
                // computeEchoChamberByClass javadoc) -- same periodic cadence as the follow-graph
                // metrics just above, on the same currentW snapshot.
                writer.writeEchoChamberByClass(analyzer.computeEchoChamberByClass(agentSet, currentW), folerPath);
                // 2026-07-25: periodic bin7 snapshot -- postCountByBin7 is cumulative-since-t=0, so
                // this shows how the posting-rate-by-ideology-bin shape evolves/stabilizes over the
                // run (not just the final cumulative fit). popCountByBin7 hoisted above (fixed at
                // construction, identical at every checkpoint).
                writer.writePostBin7(postCountByBin7, popCountByBin7, folerPath, step);
            }
            exportStepMetrics(followActionNum, unfollowActionNum);
            // R16.3: reset the windowed interaction graph at window boundaries (after this step's
            // metrics have already read it).
            if (step % cfg.interactionWindow == 0) repostNetworkWindow.clear();
        }
        writer.writeAgentSnapshot(agentSet, admin, folerPath, "final");
        // Empirical 7-bin fit artifact (2026-07-21): population-by-bin is a diagnostic (should
        // trivially match Const.EMPIRICAL_OPINION_BIN_COUNTS' proportions when init_dist=empirical,
        // up to sampling noise -- confirms the sampler is working, not itself a fitted quantity);
        // postCountByBin7 is the actual calibration-loss target (see app_pol_baseline_bo_calibration.py).
        // popCountByBin7 computed once, before the loop (see above).
        writer.writePostBin7(postCountByBin7, popCountByBin7, folerPath);
        // Final flush for batch writer
        writer.flush();
    }

    // Per-step metric export (R21): build the metrics row, set the opinion-bin stream, write.
    private void exportStepMetrics(int followActionNum, int unfollowActionNum) {
        writer.setMetrics(buildMetricsRow(followActionNum, unfollowActionNum));
        writer.setOpinionBins(agentSet);
        writer.write();
    }

    // R21: assemble the per-step metrics row. Insertion order here IS the CSV column order;
    // it reproduces the legacy Const.RESULT_LIST order exactly. Adding a metric = one put().
    private MetricsRow buildMetricsRow(int followActionNum, int unfollowActionNum) {
        MetricsRow row = new MetricsRow();
        row.put("opinionVar", analyzer.computeVarianceOpinion(agentSet));
        analyzer.computePostVariance();
        row.put("postOpinionVar", analyzer.getPostOpinionVar());
        // C2: repost-inclusive, reach-weighted exposure metrics (excludes target hubs)
        analyzer.computeExposureMetrics(agentSet);
        row.put("exposureOpinionVar", analyzer.getExposureOpinionVar());
        row.put("exposureOpinionMean", analyzer.getExposureOpinionMean());
        row.put("follow", followActionNum);
        row.put("unfollow", unfollowActionNum);
        row.put("rewire", 0);
        row.put("opinionAvg", analyzer.computeMeanOpinion(agentSet));
        row.put("shannonIndex", analyzer.computeShannonWienerIndex(agentSet));
        row.put("disagreement", analyzer.computeDisagreement(agentSet, admin));
        // 2-D outcome plane: structural separation (x) x affective hostility (y)
        row.put("meanTolerance", analyzer.computeMeanTolerance(agentSet));
        row.put("toleranceVar", analyzer.computeToleranceVar(agentSet));
        row.put("bcExtremityCorrelation", analyzer.computeBcExtremityCorrelation(agentSet));
        row.put("opinionAssortativity", analyzer.computeOpinionAssortativity(agentSet, admin));
        row.put("crossCuttingFraction", analyzer.computeCrossCuttingFraction(agentSet, admin, params.neutralBandHalfWidth()));
        row.put("opinionKurtosis", analyzer.computeOpinionKurtosis(agentSet));
        // Interaction-graph (cumulative repost/relay) variants of the structural axis
        row.put("interactionAssortativity", analyzer.computeInteractionAssortativity(agentSet, repostNetworkCumulative));
        row.put("interactionCrossCuttingFraction", analyzer.computeInteractionCrossCuttingFraction(agentSet, repostNetworkCumulative, params.neutralBandHalfWidth()));
        // R16.3: windowed variants (recent relaying only) — transient vs. whole-run separation.
        row.put("interactionAssortativityW", analyzer.computeInteractionAssortativity(agentSet, repostNetworkWindow));
        row.put("interactionCrossCuttingFractionW", analyzer.computeInteractionCrossCuttingFraction(agentSet, repostNetworkWindow, params.neutralBandHalfWidth()));
        // binned metrics (order: feed mean, feed var, cRate mean, cRate var, highComfort count)
        analyzer.computeFeedMetrics(agentSet);
        double[] feedMean = analyzer.getFeedMeanArray();
        double[] feedVar = analyzer.getFeedVarArray();
        for (int i = 0; i < Const.NUM_OF_BINS_OF_OPINION; i++) row.put("feedPostOpinionMean_" + i, feedMean[i]);
        for (int i = 0; i < Const.NUM_OF_BINS_OF_OPINION; i++) row.put("feedPostOpinionVar_" + i, feedVar[i]);
        analyzer.computeCRateArray(agentSet);
        double[] cRateMean = analyzer.getCRateMeanArray();
        double[] cRateVar = analyzer.getCRateVarArray();
        for (int i = 0; i < Const.NUM_OF_BINS_OF_OPINION; i++) row.put("cRateMean_" + i, cRateMean[i]);
        for (int i = 0; i < Const.NUM_OF_BINS_OF_OPINION; i++) row.put("cRateVar_" + i, cRateVar[i]);
        // 2026-08-25: |opinion|>=0.8 comfort-rate probe, see Analysis.computeCRateBand08Array.
        analyzer.computeCRateBand08Array(agentSet);
        double[] cRateMeanBand08 = analyzer.getCRateMeanBand08Array();
        int[] popCountBand08 = analyzer.getPopCountBand08Array();
        row.put("cRateMean08_ext", cRateMeanBand08[0]);
        row.put("cRateMean08_mod", cRateMeanBand08[1]);
        row.put("cRateMean08_neu", cRateMeanBand08[2]);
        row.put("popCount08_ext", popCountBand08[0]);
        row.put("popCount08_mod", popCountBand08[1]);
        row.put("popCount08_neu", popCountBand08[2]);
        analyzer.computeHighComfortRateNumArray(agentSet);
        double[] highComfort = analyzer.getHighComfortRateNumArray();
        for (int i = 0; i < Const.NUM_OF_BINS_OF_OPINION; i++) row.put("highComfortRateNum_" + i, highComfort[i]);
        // vocal-minority readout: share of this step's original posts authored by each opinion-bin class
        analyzer.computePostShareArray(agentSet);
        double[] postShare = analyzer.getPostShareArray();
        for (int i = 0; i < Const.NUM_OF_BINS_OF_OPINION; i++) row.put("postShare_" + i, postShare[i]);

        // R16.2: bimodality companion to kurtosis (Sarle's coefficient, > ~0.555 => bimodal).
        row.put("bimodalityCoeff", analyzer.computeBimodalityCoefficient(agentSet));

        // R1: behavioral hostility proxies (model-invariant; the primary anti-tautology axis).
        row.put("outGroupBlockPropensity", stepStats.outGroupExposureCount > 0 ? (double) stepStats.outGroupSanctionCount / stepStats.outGroupExposureCount : 0.0);
        row.put("outGroupSanctionRate", stepStats.activeCount > 0 ? (double) stepStats.outGroupSanctionCount / stepStats.activeCount : 0.0);
        row.put("crossRepostRate", stepStats.repostCount > 0 ? (double) stepStats.crossRepostCount / stepStats.repostCount : 0.0);
        row.put("blockCount", stepStats.blockCount);
        row.put("followCount", stepStats.followCount);
        row.put("unfollowCount", stepStats.unfollowCount);
        row.put("evictionCount", stepStats.evictionCount);
        // R6: volume metrics for repost:post-ratio calibration.
        row.put("originalPostCount", stepStats.originalPostCount);
        row.put("repostCount", stepStats.allRepostCount);
        // 2026-07-29: self-reinforcement diagnostics (cumulative to date, like the interaction-graph
        // metrics above) -- see AdminOptim's field comments. postLifespanMean grows with run length
        // by construction (more posts have been evicted); read it as a per-post duration, not a
        // running total. postStillActiveAtEvictionFrac is the more direct self-reinforcement-runaway
        // signal: a rising trend means VELOCITY_WINDOW is increasingly cutting off posts still
        // actively accumulating reposts, not just ones that naturally went quiet.
        row.put("postLifespanMean", admin.getPostLifespanMean());
        row.put("postStillActiveAtEvictionFrac", admin.getPostStillActiveAtEvictionFrac());

        // Feed-composition-by-camp: mean posts-per-agent delivered via each channel/origin,
        // by reader's opinion-bin class. Column names end in _0.._4 so the dashboard's family
        // auto-detection (FAMILY_RE) picks these up automatically, same as feedPostOpinionMean_i.
        for (int i = 0; i < Const.NUM_OF_BINS_OF_OPINION; i++) {
            int cnt = stepStats.feedClassAgentCount[i];
            // 2026-08-06: population count per opinion class, THIS STEP (live -- Agent.opinionClass
            // is refreshed every step in updateMyself(), see that method's end). Was already computed
            // every step as the normalizer above but never itself exposed; a per-capita analysis that
            // divides a trailing-window post count by a SINGLE end-of-run snapshot
            // (agent_snapshot_final.csv) is dividing by a population that may not match the window --
            // this column lets analysis take a trailing-window MEAN instead, time-matched to whatever
            // window the numerator uses.
            row.put("popCountByClass_" + i, cnt);
            row.put("feedForYouCountMean_" + i, cnt > 0 ? stepStats.feedForYouCountSum[i] / cnt : 0.0);
            row.put("feedChronoCountMean_" + i, cnt > 0 ? stepStats.feedChronoCountSum[i] / cnt : 0.0);
            row.put("feedRepostCountMean_" + i, cnt > 0 ? stepStats.feedRepostCountSum[i] / cnt : 0.0);
            row.put("feedOriginalCountMean_" + i, cnt > 0 ? stepStats.feedOriginalCountSum[i] / cnt : 0.0);
            // 2026-08-06: author-hub-tier feed composition (StepStats.feedNeutCountSum/
            // feedHubCountSum javadoc) -- mean posts-per-reader-of-camp-i authored by the Neutral
            // hub tier specifically / by any pinned hub tier.
            row.put("feedNeutCountMean_" + i, cnt > 0 ? stepStats.feedNeutCountSum[i] / cnt : 0.0);
            row.put("feedHubCountMean_" + i, cnt > 0 ? stepStats.feedHubCountSum[i] / cnt : 0.0);
        }
        // 2026-08-06: full author-class feed composition (StepStats.feedAuthorClassCountSum
        // javadoc) -- feedAuthorClass{authorCls}CountMean_{readerCls}, mean posts-per-reader-of-
        // camp-readerCls authored by camp authorCls (hub + organic combined). 25 columns; each
        // "feedAuthorClass{authorCls}CountMean" prefix is its own dashboard family (FAMILY_RE),
        // grouped by reader camp same as the families above.
        for (int r = 0; r < Const.NUM_OF_BINS_OF_OPINION; r++) {
            int cnt = stepStats.feedClassAgentCount[r];
            for (int a = 0; a < Const.NUM_OF_BINS_OF_OPINION; a++) {
                row.put("feedAuthorClass" + a + "CountMean_" + r,
                        cnt > 0 ? stepStats.feedAuthorClassCountSum[r][a] / cnt : 0.0);
                // 2026-08-06: comfort-conditional subset (StepStats.feedClassComfortCountSum
                // javadoc) -- feedComfortClass{a}CountMean_{r} / feedAuthorClass{a}CountMean_{r}
                // (post-hoc, in analysis) = fraction of author-class-a content that fell inside
                // reader-class-r's own vocal_comfort_radius.
                row.put("feedComfortClass" + a + "CountMean_" + r,
                        cnt > 0 ? stepStats.feedClassComfortCountSum[r][a] / cnt : 0.0);
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
