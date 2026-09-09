package writer;

import agent.*;
import constants.Const;
import java.io.FileWriter;
import java.io.IOException;
import java.io.PrintWriter;

/**
 * Batched CSV writer for the three per-step streams.
 *
 * R21: the metrics stream is a generic {@link MetricsRow} (no per-metric fields/setters/switch).
 * Output layout is one appended file per stream per run — {@code metrics/results.csv},
 * {@code posts/post_result.csv}, {@code opinion/opinion_result.csv} — instead of per-1000-step
 * shards, so downstream analysis no longer has to glob-and-concat. In-memory batching (flush
 * every BATCH_SIZE steps) is retained for I/O efficiency.
 */
public class Writer {

    private int simulationStep;
    private final String folderPath;

    // R21: current per-step metrics row (set by OpinionDynamics before write()).
    private MetricsRow currentMetrics;

    // posts / opinion bin streams
    private final int[] postBins = new int[Const.NUM_OF_BINS_OF_POSTS];
    private final double postBinWidth;
    private final int[] opinionBins = new int[Const.NUM_OF_BINS_OF_OPINION_FOR_WRITER];

    // 2026-08-25: analysis-only |opinion|>=0.8 reclassification of the same posts (Const.band08Of),
    // parallel to postBins/postBinWidth above -- see Const.band08Of javadoc.
    private final int[] band08PostBins = new int[3];

    private static final int BATCH_SIZE = 1000;
    private int batchStartStep = 0;
    private final StringBuilder metricsBuf = new StringBuilder();
    private final StringBuilder postsBuf = new StringBuilder();
    private final StringBuilder opinionBuf = new StringBuilder();

    // Frozen headers; a metrics keyset that later differs from metricsHeader is a hard error.
    private String metricsHeader;
    private final String postsHeader;
    private final String opinionHeader;
    private boolean metricsFileStarted = false;
    private boolean postsFileStarted = false;
    private boolean opinionFileStarted = false;

    // R19: repost-cascade (relay-event) log — buffered, flushed with the batch.
    private final StringBuilder repostCascadeBuf = new StringBuilder();
    private boolean repostCascadeFileStarted = false;
    private static final String REPOST_CASCADE_HEADER =
            "step,rootPostId,parentPostId,postId,author,relayer,depth,conveyedOpinion,relayerOpinion,outOfBcRelay,viaAlgo";

    // 2026-07-29: per-post lifespan/self-reinforcement log — one row per post at the moment it's
    // evicted from AdminOptim's For-You candidate window, dashboard's top-reposted-lifespan ranking
    // (see docs/report/2026-07-29-feed-reach-redesign.md). Only posts that received >=1 repost are
    // logged (AdminOptim.recordLifespan already filters these), so volume is bounded well below
    // repost_cascades.csv (one row per post, not per repost event).
    private final StringBuilder postLifespanBuf = new StringBuilder();
    private boolean postLifespanFileStarted = false;
    private static final String POST_LIFESPAN_HEADER =
            "evictionStep,postId,author,postedStep,lastRepostStep,lifespan,receivedReposts,stillActiveAtEviction";

    public Writer(String folderPath) {
        this.folderPath = folderPath;
        this.postBinWidth = 2.0 / postBins.length;

        StringBuilder ph = new StringBuilder("step");
        for (int i = 0; i < postBins.length; i++) ph.append(",bin_").append(i);
        ph.append(",band08_ext,band08_mod,band08_neu");
        ph.append(",sumOfPosts");
        this.postsHeader = ph.toString();

        StringBuilder oh = new StringBuilder("step");
        for (int i = 0; i < opinionBins.length; i++) oh.append(",bin_").append(i);
        this.opinionHeader = oh.toString();
    }

    // ---- setters (only step, the metrics row, and the two bin streams remain) ----

    public void setSimulationStep(int step) {
        this.simulationStep = step;
    }

    /** R21: hand the fully-built metrics row for this step. */
    public void setMetrics(MetricsRow row) {
        this.currentMetrics = row;
    }

    // R19: append one relay event to the repost-cascade buffer.
    // Validation-gate fix (2026-07-09): relayerOpinion is the relayer's OWN opinion at the moment
    // of this relay event (not looked up later from a final snapshot) — camp/side classification
    // done post-hoc from this file must not depend on how much longer the run continued afterward.
    public void logRepostCascade(int step, Post relayed, double relayerOpinion) {
        repostCascadeBuf.append(step).append(',')
                  .append(relayed.getRootPostId()).append(',')
                  .append(relayed.getParentPostId()).append(',')
                  .append(relayed.getPostId()).append(',')
                  .append(relayed.getPostUserId()).append(',')
                  .append(relayed.getRelayerId()).append(',')
                  .append(relayed.getDepth()).append(',')
                  .append(String.format("%.4f", relayed.getPostOpinion())).append(',')
                  .append(String.format("%.4f", relayerOpinion)).append(',')
                  .append(relayed.isOutOfBcRelay() ? 1 : 0).append(',')
                  .append(relayed.isViaAlgo() ? 1 : 0).append('\n');
    }

    // 2026-07-29: one row per post-eviction event (AdminOptim.drainLifespanEvents), see field
    // comment above. author is the post's attributed author at eviction time (relay attribution
    // may have changed it from the original poster -- same convention as repost_cascades.csv).
    public void logPostLifespan(int evictionStep, Post post, boolean stillActiveAtEviction) {
        postLifespanBuf.append(evictionStep).append(',')
                  .append(post.getPostId()).append(',')
                  .append(post.getPostUserId()).append(',')
                  .append(post.getPostedStep()).append(',')
                  .append(post.getLastRepostStep()).append(',')
                  .append(post.getLastRepostStep() - post.getPostedStep()).append(',')
                  .append(post.getReceivedReposts()).append(',')
                  .append(stillActiveAtEviction ? 1 : 0).append('\n');
    }

    public void clearPostBins() {
        for (int i = 0; i < postBins.length; i++) postBins[i] = 0;
        for (int i = 0; i < band08PostBins.length; i++) band08PostBins[i] = 0;
    }

    public void setPostBins(Post post) {
        double shiftedOpinion = post.getPostOpinion() + 1;
        int binIndex = (int) Math.min(shiftedOpinion / postBinWidth, postBins.length - 1);
        postBins[binIndex] += 1;
        band08PostBins[Const.band08Of(post.getPostOpinion())] += 1;
    }

    public void setOpinionBins(Agent[] agentSet) {
        double binWidth = 2.0 / Const.NUM_OF_BINS_OF_OPINION_FOR_WRITER;
        for (int i = 0; i < opinionBins.length; i++) opinionBins[i] = 0;
        for (Agent agent : agentSet) {
            if (!agent.getTarget()) {
                // Bin straight from the raw opinion value into NUM_OF_BINS_OF_OPINION_FOR_WRITER
                // equal-width bins over [-1,1] (independent of Agent.opinionClass).
                double shiftedOpinion = agent.getOpinion() + 1; // [-1,1] -> [0,2]
                int binIndex = (int) Math.min(shiftedOpinion / binWidth,
                        Const.NUM_OF_BINS_OF_OPINION_FOR_WRITER - 1);
                this.opinionBins[binIndex] += 1;
            }
        }
    }

    // ---- write ----

    public void write() {
        // metrics stream (R21)
        if (currentMetrics != null) {
            String header = "step," + currentMetrics.headerCsv();
            if (metricsHeader == null) {
                metricsHeader = header;
            } else if (!metricsHeader.equals(header)) {
                throw new IllegalStateException(
                        "MetricsRow schema changed mid-run (fail-fast, R21).\n expected: "
                        + metricsHeader + "\n got:      " + header);
            }
            metricsBuf.append(simulationStep);
            for (Number v : currentMetrics.values()) {
                metricsBuf.append(',');
                appendNumber(metricsBuf, v);
            }
            metricsBuf.append('\n');
        }

        // posts stream
        postsBuf.append(simulationStep);
        int sumOfPosts = 0;
        for (int bin : postBins) {
            postsBuf.append(',').append(bin);
            sumOfPosts += bin;
        }
        for (int bin : band08PostBins) postsBuf.append(',').append(bin);
        postsBuf.append(',').append(sumOfPosts).append('\n');

        // opinion stream
        opinionBuf.append(simulationStep);
        for (int bin : opinionBins) opinionBuf.append(',').append(bin);
        opinionBuf.append('\n');

        if (simulationStep > 0 && (simulationStep - batchStartStep + 1) >= BATCH_SIZE) {
            flushBatch();
        }
    }

    public void flush() {
        if (metricsBuf.length() > 0 || postsBuf.length() > 0 || opinionBuf.length() > 0
                || repostCascadeBuf.length() > 0 || postLifespanBuf.length() > 0) {
            flushBatch();
        }
    }

    private void flushBatch() {
        appendToFile(metricsBuf, folderPath + "/metrics/results.csv", metricsHeader, metricsFileStarted);
        metricsFileStarted = true;
        appendToFile(postsBuf, folderPath + "/posts/post_result.csv", postsHeader, postsFileStarted);
        postsFileStarted = true;
        appendToFile(opinionBuf, folderPath + "/opinion/opinion_result.csv", opinionHeader, opinionFileStarted);
        opinionFileStarted = true;
        if (repostCascadeBuf.length() > 0) {
            appendToFile(repostCascadeBuf, folderPath + "/posts/repost_cascades.csv", REPOST_CASCADE_HEADER, repostCascadeFileStarted);
            repostCascadeFileStarted = true;
            repostCascadeBuf.setLength(0);
        }
        if (postLifespanBuf.length() > 0) {
            appendToFile(postLifespanBuf, folderPath + "/posts/post_lifespan.csv", POST_LIFESPAN_HEADER, postLifespanFileStarted);
            postLifespanFileStarted = true;
            postLifespanBuf.setLength(0);
        }

        metricsBuf.setLength(0);
        postsBuf.setLength(0);
        opinionBuf.setLength(0);
        batchStartStep = simulationStep + 1;
    }

    // First write to a stream truncates + emits the header; subsequent writes append rows only.
    private void appendToFile(StringBuilder buf, String filePath, String header, boolean started) {
        if (buf.length() == 0) return;
        try (PrintWriter pw = new PrintWriter(new FileWriter(filePath, started))) {
            if (!started && header != null) pw.println(header);
            pw.print(buf);
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    // Integer-valued metrics stay integers; everything else is a fixed 4-dp double (legacy format).
    private void appendNumber(StringBuilder sb, Number v) {
        if (v instanceof Integer || v instanceof Long || v instanceof Short || v instanceof Byte) {
            sb.append(v.longValue());
        } else {
            sb.append(String.format("%.4f", v.doubleValue()));
        }
    }

    public void writeDegrees(double[][] adjacencyMatrix, String outputDirPath) {
        String filePath = outputDirPath + "/degrees/degree_result_" + simulationStep + ".csv";
        try (PrintWriter pw = new PrintWriter(new FileWriter(filePath, false))) {
            pw.println("agentId,inDegree,outDegree");
            int numAgents = adjacencyMatrix.length;
            for (int i = 0; i < numAgents; i++) {
                int outDegree = 0;
                int inDegree = 0;
                for (int j = 0; j < numAgents; j++) {
                    outDegree += (adjacencyMatrix[i][j] > 0) ? 1 : 0;
                }
                for (int j = 0; j < numAgents; j++) {
                    inDegree += (adjacencyMatrix[j][i] > 0) ? 1 : 0;
                }
                pw.printf("%d,%d,%d%n", i, inDegree, outDegree);
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    // 2026-08-02: dedicated diagnostic for the delayed-conduit-entry mechanism (ExperimentConfig
    // .pinNeutralIds) -- user's question: is the pinNeutralIds class's follower base genuinely a
    // population-representative (opinion-blind, per t0 selection) cross-section, or does it happen
    // to skew toward a particular opinion bin for these seeds? Per-class-member opinion-bin
    // breakdown of CURRENT followers, at the same periodic cadence as writeDegrees. Only called
    // when pinNeutralIds is non-empty (see OpinionDynamics.evolve()), so this has zero cost for
    // every other experiment. 5-bin convention matches Analysis.java/population_counts() scripts:
    // shifted = opinion+1.0, bin = floor(shifted/0.4) clamped to [0,4].
    public void writeClassFollowerComposition(agent.Agent[] agentSet, double[][] adjacencyMatrix,
            java.util.Set<Integer> classIds, String outputDirPath) {
        String filePath = outputDirPath + "/degrees/class_follower_composition_" + simulationStep + ".csv";
        try (PrintWriter pw = new PrintWriter(new FileWriter(filePath, false))) {
            pw.println("classAgentId,nFollowers,bin0,bin1,bin2,bin3,bin4");
            int n = adjacencyMatrix.length;
            for (int id : classIds) {
                int[] binCounts = new int[5];
                int nFollowers = 0;
                for (int j = 0; j < n; j++) {
                    if (adjacencyMatrix[j][id] > 0) {
                        nFollowers++;
                        double shifted = agentSet[j].getOpinion() + 1.0;
                        int bin = Math.min((int) (shifted / 0.4), 4);
                        binCounts[bin]++;
                    }
                }
                pw.printf("%d,%d,%d,%d,%d,%d,%d%n", id, nFollowers,
                        binCounts[0], binCounts[1], binCounts[2], binCounts[3], binCounts[4]);
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    // 2026-08-06: per-opinion-class echo-chamber structural metrics (Analysis.
    // computeEchoChamberByClass javadoc) -- one row per opinion-class bin, one file per periodic
    // checkpoint (same cadence/location convention as writeClassFollowerComposition above).
    public void writeEchoChamberByClass(analysis.Analysis.EchoChamberStats[] stats, String outputDirPath) {
        String filePath = outputDirPath + "/degrees/echo_chamber_by_class_" + simulationStep + ".csv";
        try (PrintWriter pw = new PrintWriter(new FileWriter(filePath, false))) {
            pw.println("class,nodeCount,density,avgClusteringCoeff,triangleCount");
            for (int c = 0; c < stats.length; c++) {
                pw.printf("%d,%d,%.6f,%.6f,%d%n", c, stats[c].nodeCount, stats[c].density,
                        stats[c].avgClusteringCoeff, stats[c].triangleCount);
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    // Validation-gate diagnostic (2026-07-08): per-agent snapshot so hub-attributable
    // cross-camp bridging can be computed post-hoc from repost_cascades.csv (existing
    // crossCuttingFraction/interactionCrossCuttingFraction metrics exclude any edge touching a
    // target/hub agent by design, so they cannot see the hub's own bridging edges — this snapshot
    // is the camp/opinion lookup needed to measure that separately, not a replacement metric).
    public void writeAgentSnapshot(agent.Agent[] agentSet, admin.AdminOptim admin, String outputDirPath, String label) {
        String filePath = outputDirPath + "/degrees/agent_snapshot_" + label + ".csv";
        try (PrintWriter pw = new PrintWriter(new FileWriter(filePath, false))) {
            // 2026-08-04: avgComfortRate (Agent.getAverageComfortRate(), a trailing-100-step average
            // already maintained internally by the agent for its own bc/postProb feedback loop)
            // added for the L/M/P hub-tier pilot's hub-vs-non-hub comfort-rate split (existing
            // cRateMean_i in metrics/results.csv mixes hub-tier and ordinary agents within a bin;
            // this column lets analysis exclude the isTarget==1 hub-tier agents in post-hoc Python).
            // (A parallel numOfPosts column + periodic mid-run snapshot were tried for a similar
            // per-agent post-count split and reverted: Agent.numOfPosts is a static feed-capacity
            // field set once at construction, not a post counter -- it does not vary and cannot
            // answer that question. The non-hub post-rate split is instead computed directly from
            // posts/post_result.csv, whose bin_i counts already exclude every target/hub agent's own
            // posts by construction -- see the `!agent.getTarget()` gate around writer.setPostBins()
            // above -- so only the population denominator needed correcting, in Python, no new
            // per-agent instrumentation required.)
            pw.println("agentId,intrinsicOpinion,opinion,bc,followerCount,followeeCount,isTarget,avgComfortRate");
            for (int i = 0; i < agentSet.length; i++) {
                agent.Agent a = agentSet[i];
                pw.printf("%d,%.4f,%.4f,%.4f,%d,%d,%d,%.4f%n",
                        i, a.getIntrinsicOpinion(), a.getOpinion(), a.getBc(),
                        admin.getFollowers(i).size(), admin.followeeCount(i),
                        a.getTarget() ? 1 : 0, a.getAverageComfortRate());
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    // R16.4: append the sign-partition modularity of the evolved follow graph (side CSV).
    // 2026-07-15: added qSignRepost (repost-graph modularity, Analysis.computeSignModularityFromMatrix)
    // as a second column, for the systematic-A/B calibration plan's "repost NW fit" target
    // (Conover et al. 2011's ~0.7-0.8 modularity figure is a retweet-graph, not follow-graph, statistic).
    private boolean modularityFileStarted = false;
    public void writeModularity(int step, double qSign, double qSignRepost, String outputDirPath) {
        String filePath = outputDirPath + "/metrics/modularity.csv";
        try (PrintWriter pw = new PrintWriter(new FileWriter(filePath, modularityFileStarted))) {
            if (!modularityFileStarted) pw.println("step,Q_sign,Q_sign_repost");
            pw.printf("%d,%.6f,%.6f%n", step, qSign, qSignRepost);
            modularityFileStarted = true;
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    public void writeClusteringCoefficients(double[] clustering, String outputDirPath) {
        String filePath = outputDirPath + "/clusterings/clustering_result_" + simulationStep + ".csv";
        try (PrintWriter pw = new PrintWriter(new FileWriter(filePath, false))) {
            pw.println("agentId,clusteringCoefficient");
            for (int i = 0; i < clustering.length; i++) {
                pw.printf("%d,%.6f%n", i, clustering[i]);
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    // 2026-07-15: repost-graph counterparts to writeDegrees/writeClusteringCoefficients, computed
    // on the same windowed repostNetwork matrix that repostGephi.exportGraph() draws at this same
    // call site (OpinionDynamics.java) — so the "repost NW fit" numbers always describe exactly
    // the graph the dashboard's repost-graph snapshot view is showing, not a different window.
    public void writeRepostDegrees(double[][] adjacencyMatrix, String outputDirPath) {
        String filePath = outputDirPath + "/degrees/repost_degree_result_" + simulationStep + ".csv";
        try (PrintWriter pw = new PrintWriter(new FileWriter(filePath, false))) {
            pw.println("agentId,inDegree,outDegree");
            int numAgents = adjacencyMatrix.length;
            for (int i = 0; i < numAgents; i++) {
                int outDegree = 0;
                int inDegree = 0;
                for (int j = 0; j < numAgents; j++) {
                    outDegree += (adjacencyMatrix[i][j] > 0) ? 1 : 0;
                }
                for (int j = 0; j < numAgents; j++) {
                    inDegree += (adjacencyMatrix[j][i] > 0) ? 1 : 0;
                }
                pw.printf("%d,%d,%d%n", i, inDegree, outDegree);
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    // 2026-07-21: empirical 7-bin calibration fit artifact (Const.EMPIRICAL_OPINION_BIN_COUNTS /
    // EMPIRICAL_POST_BIN_WEIGHTS). postCountByBin is cumulative over the whole run (Agent's
    // intrinsic opinion, not current); popCountByBin is a t=0-equivalent diagnostic (intrinsic
    // opinion never changes), confirming init_dist=empirical actually reproduces the target
    // proportions. Written once, at the end of the run -- not a per-step metric.
    public void writePostBin7(long[] postCountByBin, long[] popCountByBin, String outputDirPath) {
        writePostBin7ToFile(postCountByBin, popCountByBin, outputDirPath + "/metrics/post_bin7.csv");
    }

    // 2026-07-25: step-indexed variant for periodic (step%5000==0) snapshots -- see
    // OpinionDynamics.java's evolve() -- so the 7-bin posting-rate shape's evolution over the run
    // can be inspected, not just the final cumulative fit. postCountByBin is cumulative-since-t=0
    // at every call (same semantics as the final post_bin7.csv, just read at an earlier step).
    public void writePostBin7(long[] postCountByBin, long[] popCountByBin, String outputDirPath, int step) {
        writePostBin7ToFile(postCountByBin, popCountByBin, outputDirPath + "/metrics/post_bin7_" + step + ".csv");
    }

    private void writePostBin7ToFile(long[] postCountByBin, long[] popCountByBin, String filePath) {
        try (PrintWriter pw = new PrintWriter(new FileWriter(filePath, false))) {
            pw.println("bin,popCount,postCount");
            for (int i = 0; i < postCountByBin.length; i++) {
                pw.printf("%d,%d,%d%n", i, popCountByBin[i], postCountByBin[i]);
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    public void writeRepostClusteringCoefficients(double[] clustering, String outputDirPath) {
        String filePath = outputDirPath + "/clusterings/repost_clustering_result_" + simulationStep + ".csv";
        try (PrintWriter pw = new PrintWriter(new FileWriter(filePath, false))) {
            pw.println("agentId,clusteringCoefficient");
            for (int i = 0; i < clustering.length; i++) {
                pw.printf("%d,%.6f%n", i, clustering[i]);
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
    }
}
