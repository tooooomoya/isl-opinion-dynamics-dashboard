package analysis;

import admin.AdminOptim;
import agent.*;
import constants.Const;
import java.util.*;

public class Analysis {
    private List<Post> postCash;
    private int n;
    private double postOpinionVar;
    private double exposureOpinionVar;
    private double exposureOpinionMean;
    private List<List<Post>> feedList;
    private double[] feedMeanArray = new double[Const.NUM_OF_BINS_OF_OPINION];
    private double[] feedVarArray = new double[Const.NUM_OF_BINS_OF_OPINION];
    private double[] cRateMeanArray = new double[Const.NUM_OF_BINS_OF_OPINION];
    private double[] cRateVarArray = new double[Const.NUM_OF_BINS_OF_OPINION];
    private double[] highComfortRateNumArray = new double[Const.NUM_OF_BINS_OF_OPINION];
    private double[] postShareArray = new double[Const.NUM_OF_BINS_OF_OPINION];
    private Map<Integer, List<Post>> feedMap = new HashMap<>();

    // 2026-08-25: |opinion|>=0.8 comfort-rate probe (Const.band08Of), parallel to cRateMeanArray
    // above but keyed by continuous opinion rather than Agent.opinionClass -- see Const.band08Of.
    private double[] cRateMeanBand08Array = new double[3];
    private int[] popCountBand08Array = new int[3];

    // constructor
    public Analysis(int n) {
        this.n = n; // R17: agent count is config-driven
        this.postCash = new ArrayList<>();
        this.postOpinionVar = -1;
        this.feedList = new ArrayList<>();
    }

    public double[] getFeedMeanArray() {
        return this.feedMeanArray;
    }

    public double[] getFeedVarArray() {
        return this.feedVarArray;
    }

    public double[] getCRateMeanArray() {
        return this.cRateMeanArray;
    }

    public double[] getCRateVarArray() {
        return this.cRateVarArray;
    }

    public double[] getHighComfortRateNumArray() {
        return this.highComfortRateNumArray;
    }

    public double[] getPostShareArray() {
        return this.postShareArray;
    }

    public double[] getCRateMeanBand08Array() {
        return this.cRateMeanBand08Array;
    }

    public int[] getPopCountBand08Array() {
        return this.popCountBand08Array;
    }

    public void clearPostCash() {
        postCash.clear();
    }

    public void clearFeedList() {
        this.feedList.clear();
    }

    public void setPostCash(Post post) {
        postCash.add(post.copyPost());
    }

    public void setFeedList(List<Post> feed) {
        this.feedList.add(new ArrayList<>(feed));
    }

    public void setFeedMap(Agent agent) {
        this.feedMap.put(agent.getId(), new ArrayList<>(agent.getFeed()));
    }

    public void resetFeedMap() {
        feedMap.clear();
    }

    // compute variance of inner opinions
    public double computeVarianceOpinion(Agent[] agentSet) {
        int num = 0;
        if (n == 0) {
            return -1;
        }

        double sum = 0.0;
        for (Agent agent : agentSet) {
            if (!agent.getTarget()) {
                sum += agent.getOpinion();
                num++;
            }
        }
        double mean = sum / num;

        double squaredDiffSum = 0.0;
        for (Agent agent : agentSet) {
            if (!agent.getTarget()) {
                double diff = agent.getOpinion() - mean;
                squaredDiffSum += diff * diff;
            }
        }
        return squaredDiffSum / num;
    }

    // compute disagreement (metrics representing the degree of echo chamber)
    // R16.1: skip edges touching a target hub, consistent with every other population metric
    // (was the one metric that still counted exogenous hub opinions).
    public double computeDisagreement(Agent[] agentSet, AdminOptim admin) {
        if (agentSet.length == 0) return -1;

        double sum = 0.0;
        int edgeCount = 0;

        for (int i = 0; i < agentSet.length; i++) {
            if (agentSet[i].getTarget()) continue;
            for (int j : admin.getFollowees(i)) {
                if (agentSet[j].getTarget()) continue;
                double diff = agentSet[i].getOpinion() - agentSet[j].getOpinion();
                sum += diff * diff;
                edgeCount++;
            }
        }

        return (edgeCount > 0) ? sum / edgeCount : 0;
    }

    // R16.2: Sarle's bimodality coefficient b = (g1^2 + 1) / (g2 + 3(n-1)^2/((n-2)(n-3))).
    // b > 5/9 (~0.555) suggests bimodality; complements kurtosis. Excludes target hubs.
    public double computeBimodalityCoefficient(Agent[] agentSet) {
        double sum = 0.0; int n = 0;
        for (Agent a : agentSet) if (!a.getTarget()) { sum += a.getOpinion(); n++; }
        if (n < 4) return -1;
        double mean = sum / n;
        double m2 = 0, m3 = 0, m4 = 0;
        for (Agent a : agentSet) {
            if (a.getTarget()) continue;
            double d = a.getOpinion() - mean;
            m2 += d * d; m3 += d * d * d; m4 += d * d * d * d;
        }
        m2 /= n; m3 /= n; m4 /= n;
        if (m2 < 1e-12) return -1;
        double g1 = m3 / Math.pow(m2, 1.5);                 // skewness
        double g2 = m4 / (m2 * m2) - 3.0;                   // excess kurtosis
        double correction = 3.0 * (n - 1.0) * (n - 1.0) / ((n - 2.0) * (n - 3.0));
        return (g1 * g1 + 1.0) / (g2 + correction);
    }

    // ===================================================================
    // 2-D outcome plane (research-direction.md §3.5 / §4 build-order item 1)
    //   x-axis = STRUCTURAL separation:  opinion assortativity + cross-cutting-edge fraction
    //   y-axis = AFFECTIVE hostility:     mean tolerance (ε / bounded confidence), low = hostile
    // Structural polarization (echo-chamber fragmentation) = upper-right (high separation, high hostility);
    // Affective polarization (connected-but-hostile)        = upper-left (LOW separation, high hostility) <- target.
    // All population metrics exclude exogenous (target) hubs, consistent with opinionVar.
    // NB structural axis is computed on the FOLLOW graph here; the 2026-06-23 literature
    // audit (Conover 2011) notes the cross-cutting layer lives in the interaction/quote
    // graph, so an interaction-graph variant is a documented follow-up.
    // ===================================================================

    // y-axis: mean of agents' bounded confidence (ε / tolerance). Lower = more hostile
    // (less willing to accept out-of-tolerance content). This is the affective axis the
    // build order mandates instead of opinion variance.
    public double computeMeanTolerance(Agent[] agentSet) {
        double sum = 0.0;
        int num = 0;
        for (Agent agent : agentSet) {
            if (!agent.getTarget()) {
                sum += agent.getBc();
                num++;
            }
        }
        return (num > 0) ? sum / num : -1;
    }

    public double computeToleranceVar(Agent[] agentSet) {
        double sum = 0.0;
        int num = 0;
        for (Agent agent : agentSet) {
            if (!agent.getTarget()) {
                sum += agent.getBc();
                num++;
            }
        }
        if (num == 0) return -1;
        double mean = sum / num;
        double sq = 0.0;
        for (Agent agent : agentSet) {
            if (!agent.getTarget()) {
                double diff = agent.getBc() - mean;
                sq += diff * diff;
            }
        }
        return sq / num;
    }

    // x-axis (1): Newman scalar assortativity of opinion over directed follow edges (i->j).
    // = Pearson correlation of (O_source, O_target) across edges. High (->1) = homophilous
    // sorting (structural-polarization signature); near 0 / negative = opinions mixed across ties (affective-polarization substrate).
    // Edges touching a target hub are skipped (exogenous opinion would bias the measure).
    public double computeOpinionAssortativity(Agent[] agentSet, AdminOptim admin) {
        double sx = 0.0, sy = 0.0, sxy = 0.0, sx2 = 0.0, sy2 = 0.0;
        long m = 0;
        for (int i = 0; i < agentSet.length; i++) {
            if (agentSet[i].getTarget()) continue;
            double x = agentSet[i].getOpinion();
            for (int j : admin.getFollowees(i)) {
                if (agentSet[j].getTarget()) continue;
                double y = agentSet[j].getOpinion();
                sx += x; sy += y; sxy += x * y; sx2 += x * x; sy2 += y * y;
                m++;
            }
        }
        if (m == 0) return 0.0;
        double cov = sxy / m - (sx / m) * (sy / m);
        double vx = sx2 / m - (sx / m) * (sx / m);
        double vy = sy2 / m - (sy / m) * (sy / m);
        double denom = Math.sqrt(vx * vy);
        return (denom > 1e-12) ? cov / denom : 0.0;
    }

    // x-axis (2): fraction of follow edges that cross the O=0 divide (sign(O_i) != sign(O_j)).
    // High = network stays connected across camps (affective-polarization substrate); low = camps
    // separated (structural polarization). Complements assortativity; insensitive to within-camp spread.
    public double computeCrossCuttingFraction(Agent[] agentSet, AdminOptim admin, double neutralBandHalfWidth) {
        long cross = 0, total = 0;
        for (int i = 0; i < agentSet.length; i++) {
            if (agentSet[i].getTarget() || isNeutral(agentSet[i], neutralBandHalfWidth)) continue;
            double oi = agentSet[i].getOpinion();
            for (int j : admin.getFollowees(i)) {
                if (agentSet[j].getTarget() || isNeutral(agentSet[j], neutralBandHalfWidth)) continue;
                double oj = agentSet[j].getOpinion();
                if (oi * oj < 0) cross++;
                total++;
            }
        }
        return (total > 0) ? (double) cross / total : 0.0;
    }

    // x-axis, interaction-graph variants (2026-06-26): the follow graph is segregated by
    // construction (Conover 2011 - endorsement/retweet = homophily), so measuring separation there
    // is measuring somewhere it's guaranteed to appear. The cross-cutting signal instead lives in
    // who-relays-whom (repost/quote), which we now track cumulatively over the whole run
    // (OpinionDynamics.repostNetworkCumulative). These weight each edge by repost COUNT (not just
    // presence), since a repeatedly-used relay path is a stronger signal than a one-off.
    // R23b: iterate realized (i -> j) repost entries only (was a dense O(N^2) grid scan per step).
    public double computeInteractionAssortativity(Agent[] agentSet, SparseIntMatrix interactionNetwork) {
        double sx = 0.0, sy = 0.0, sxy = 0.0, sx2 = 0.0, sy2 = 0.0;
        long m = 0;
        for (Map.Entry<Integer, Map<Integer, Integer>> row : interactionNetwork.rowEntries()) {
            int i = row.getKey();
            if (agentSet[i].getTarget()) continue;
            double x = agentSet[i].getOpinion();
            for (Map.Entry<Integer, Integer> col : row.getValue().entrySet()) {
                int j = col.getKey();
                int c = col.getValue();
                if (c <= 0 || agentSet[j].getTarget()) continue;
                double y = agentSet[j].getOpinion();
                sx += c * x; sy += c * y; sxy += c * x * y; sx2 += c * x * x; sy2 += c * y * y;
                m += c;
            }
        }
        if (m == 0) return 0.0;
        double cov = sxy / m - (sx / m) * (sy / m);
        double vx = sx2 / m - (sx / m) * (sx / m);
        double vy = sy2 / m - (sy / m) * (sy / m);
        double denom = Math.sqrt(vx * vy);
        return (denom > 1e-12) ? cov / denom : 0.0;
    }

    public double computeInteractionCrossCuttingFraction(Agent[] agentSet, SparseIntMatrix interactionNetwork, double neutralBandHalfWidth) {
        long cross = 0, total = 0;
        for (Map.Entry<Integer, Map<Integer, Integer>> row : interactionNetwork.rowEntries()) {
            int i = row.getKey();
            if (agentSet[i].getTarget() || isNeutral(agentSet[i], neutralBandHalfWidth)) continue;
            double oi = agentSet[i].getOpinion();
            for (Map.Entry<Integer, Integer> col : row.getValue().entrySet()) {
                int j = col.getKey();
                int c = col.getValue();
                if (c <= 0 || agentSet[j].getTarget() || isNeutral(agentSet[j], neutralBandHalfWidth)) continue;
                double oj = agentSet[j].getOpinion();
                if (oi * oj < 0) cross += c;
                total += c;
            }
        }
        return (total > 0) ? (double) cross / total : 0.0;
    }

    // 2026-07-22: bc-vs-extremity relationship (docs/report/2026-07-21-conduit-experiment-
    // design.md) -- Pearson correlation of (|opinion|, bc) across all non-target agents. Negative
    // = extremists hold tighter tolerance than moderates (the asymmetric-bc hypothesis this
    // metric checks for); ~0 or positive = no such relationship / inverted. Same correlation
    // pattern as computeOpinionAssortativity above, just over agent-level (extremity, bc) pairs
    // instead of edge-level (source opinion, target opinion) pairs.
    public double computeBcExtremityCorrelation(Agent[] agentSet) {
        double sx = 0.0, sy = 0.0, sxy = 0.0, sx2 = 0.0, sy2 = 0.0;
        long m = 0;
        for (Agent agent : agentSet) {
            if (agent.getTarget()) continue;
            double x = Math.abs(agent.getOpinion());
            double y = agent.getBc();
            sx += x; sy += y; sxy += x * y; sx2 += x * x; sy2 += y * y;
            m++;
        }
        if (m == 0) return 0.0;
        double cov = sxy / m - (sx / m) * (sy / m);
        double vx = sx2 / m - (sx / m) * (sx / m);
        double vy = sy2 / m - (sy / m) * (sy / m);
        double denom = Math.sqrt(vx * vy);
        return (denom > 1e-12) ? cov / denom : 0.0;
    }

    // affective/bimodality companion: excess kurtosis of all (non-target) inner opinions.
    // Negative (platykurtic) => bimodal / two-camp distribution; positive => peaked/unimodal.
    // Distinguishes "opinions moved apart into two modes" from a single consensus mode in a
    // way variance alone cannot.
    public double computeOpinionKurtosis(Agent[] agentSet) {
        double sum = 0.0;
        int num = 0;
        for (Agent agent : agentSet) {
            if (!agent.getTarget()) { sum += agent.getOpinion(); num++; }
        }
        if (num < 2) return 0.0;
        double mean = sum / num;
        double m2 = 0.0, m4 = 0.0;
        for (Agent agent : agentSet) {
            if (!agent.getTarget()) {
                double d = agent.getOpinion() - mean;
                m2 += d * d;
                m4 += d * d * d * d;
            }
        }
        m2 /= num; m4 /= num;
        return (m2 > 1e-12) ? m4 / (m2 * m2) - 3.0 : 0.0;
    }

    // 2026-07-18: agents with |opinion| < halfWidth are excluded from every sign-based camp metric
    // below (Q_sign, Q_sign_repost, crossCuttingFraction, interactionCrossCuttingFraction) — see
    // ExperimentConfig.neutralBandHalfWidth's comment for the rationale (Conover et al. 2011's
    // "undecidable" exclusion, not a value taken from that paper's methodology, which uses network
    // clustering rather than any opinion threshold).
    private static boolean isNeutral(Agent a, double halfWidth) {
        return Math.abs(a.getOpinion()) < halfWidth;
    }

    // R16.4: directed Newman modularity of the sign(opinion) partition on the current follow graph.
    // Q = (1/m) Σ_ij [A_ij - k_out(i)k_in(j)/m] δ(s_i,s_j). Folding the null term over all same-sign
    // ordered pairs gives Q = (sameSignEdges - (KoutPos·KinPos + KoutNeg·KinNeg)/m) / m. O(edges).
    // High Q = the two opinion camps are structurally separated on the follow graph. Excludes hubs
    // and (2026-07-18) neutral agents (see isNeutral above).
    public double computeSignModularity(Agent[] agentSet, AdminOptim admin, double neutralBandHalfWidth) {
        int[] kOut = new int[agentSet.length];
        int[] kIn = new int[agentSet.length];
        long m = 0;
        for (int i = 0; i < agentSet.length; i++) {
            if (agentSet[i].getTarget() || isNeutral(agentSet[i], neutralBandHalfWidth)) continue;
            for (int j : admin.getFollowees(i)) {
                if (agentSet[j].getTarget() || isNeutral(agentSet[j], neutralBandHalfWidth)) continue;
                kOut[i]++; kIn[j]++; m++;
            }
        }
        if (m == 0) return 0.0;

        long koPos = 0, kiPos = 0, koNeg = 0, kiNeg = 0;
        for (int i = 0; i < agentSet.length; i++) {
            if (agentSet[i].getTarget() || isNeutral(agentSet[i], neutralBandHalfWidth)) continue;
            if (agentSet[i].getOpinion() >= 0) { koPos += kOut[i]; kiPos += kIn[i]; }
            else                                { koNeg += kOut[i]; kiNeg += kIn[i]; }
        }
        double nullTerm = ((double) koPos * kiPos + (double) koNeg * kiNeg) / m;

        long sameSignEdges = 0;
        for (int i = 0; i < agentSet.length; i++) {
            if (agentSet[i].getTarget() || isNeutral(agentSet[i], neutralBandHalfWidth)) continue;
            boolean posi = agentSet[i].getOpinion() >= 0;
            for (int j : admin.getFollowees(i)) {
                if (agentSet[j].getTarget() || isNeutral(agentSet[j], neutralBandHalfWidth)) continue;
                if (posi == (agentSet[j].getOpinion() >= 0)) sameSignEdges++;
            }
        }
        return (sameSignEdges - nullTerm) / m;
    }

    // 2026-07-15: repost-network counterpart to computeSignModularity, for the systematic-A/B
    // calibration plan (docs/research-direction.md) — the repost/retweet graph, not the follow
    // graph, is the correct referent for Conover et al. 2011's ~0.7-0.8 modularity figure (see
    // computeInteractionAssortativity's comment above: follow graphs are segregated by
    // construction, so a follow-graph modularity target is measuring the wrong network). Same Q
    // formula as computeSignModularity, generalized to weighted edges (repost COUNT, not mere
    // presence) via SparseIntMatrix, matching how computeInteractionAssortativity already weights.
    public double computeSignModularityFromMatrix(Agent[] agentSet, SparseIntMatrix net, double neutralBandHalfWidth) {
        long[] kOut = new long[agentSet.length];
        long[] kIn = new long[agentSet.length];
        long w = 0;
        for (Map.Entry<Integer, Map<Integer, Integer>> row : net.rowEntries()) {
            int i = row.getKey();
            if (agentSet[i].getTarget() || isNeutral(agentSet[i], neutralBandHalfWidth)) continue;
            for (Map.Entry<Integer, Integer> col : row.getValue().entrySet()) {
                int j = col.getKey();
                int c = col.getValue();
                if (c <= 0 || agentSet[j].getTarget() || isNeutral(agentSet[j], neutralBandHalfWidth)) continue;
                kOut[i] += c; kIn[j] += c; w += c;
            }
        }
        if (w == 0) return 0.0;

        long koPos = 0, kiPos = 0, koNeg = 0, kiNeg = 0;
        for (int i = 0; i < agentSet.length; i++) {
            if (agentSet[i].getTarget() || isNeutral(agentSet[i], neutralBandHalfWidth)) continue;
            if (agentSet[i].getOpinion() >= 0) { koPos += kOut[i]; kiPos += kIn[i]; }
            else                                { koNeg += kOut[i]; kiNeg += kIn[i]; }
        }
        double nullTerm = ((double) koPos * kiPos + (double) koNeg * kiNeg) / w;

        long sameSignWeight = 0;
        for (Map.Entry<Integer, Map<Integer, Integer>> row : net.rowEntries()) {
            int i = row.getKey();
            if (agentSet[i].getTarget() || isNeutral(agentSet[i], neutralBandHalfWidth)) continue;
            boolean posi = agentSet[i].getOpinion() >= 0;
            for (Map.Entry<Integer, Integer> col : row.getValue().entrySet()) {
                int j = col.getKey();
                int c = col.getValue();
                if (c <= 0 || agentSet[j].getTarget() || isNeutral(agentSet[j], neutralBandHalfWidth)) continue;
                if (posi == (agentSet[j].getOpinion() >= 0)) sameSignWeight += c;
            }
        }
        return (sameSignWeight - nullTerm) / w;
    }

    // compute Shannon-Wiener index to represent diversity of opinions
    public double computeShannonWienerIndex(Agent[] agentSet) {
        int totalAgents = 0;
        int[] counts = new int[Const.NUM_OF_BINS_OF_OPINION];

        // 1. Count agents in each opinion bin
        for (Agent agent : agentSet) {
            if (!agent.getTarget()) { // Assuming we exclude target/media nodes
                int bin = agent.getOpinionClass();
                if (bin >= 0 && bin < counts.length) {
                    counts[bin]++;
                    totalAgents++;
                }
            }
        }

        if (totalAgents == 0) return 0.0;

        // 2. Calculate H' = -sum(pi * ln(pi))
        double shannonIndex = 0.0;
        for (int count : counts) {
            if (count > 0) {
                double p = (double) count / totalAgents;
                shannonIndex -= p * Math.log(p);
            }
        }

        return shannonIndex;
    }

    // compute mean of inner opinions
    public double computeMeanOpinion(Agent[] agentSet) {
        int num = 0;
        if (n == 0 || agentSet == null || agentSet.length == 0) {
            return -1;
        }

        double sum = 0.0;
        for (Agent agent : agentSet) {
            if (!agent.getTarget()) {
                sum += agent.getOpinion();
                num++;
            }
        }
        return sum / num;
    }

    // compute variance of opinions on posts at a step
    public double computeFeedVariance() {
        double temp = 0.0;
        int postNum = 0;

        for (List<Post> feed : this.feedList) {
            for (Post post : feed) {
                temp += post.getPostOpinion();
                postNum++;
            }
        }

        if (postNum == 0) {
            System.out.println("no post was read by users in this step.");
            return -1;
        }

        double avg = temp / postNum;

        double squaredDiffSum = 0.0;
        for (List<Post> feed : this.feedList) {
            for (Post post : feed) {
                double diff = post.getPostOpinion() - avg;
                squaredDiffSum += diff * diff;
            }
        }

        return squaredDiffSum / postNum;
    }

    // compute mean and var of every agent's feed
    public void computeFeedMetrics(Agent[] agentSet) {
        Arrays.fill(this.feedMeanArray, 0.0);
        Arrays.fill(this.feedVarArray, 0.0);

        double[] classVarianceSum = new double[Const.NUM_OF_BINS_OF_OPINION];
        int[] agentCount = new int[Const.NUM_OF_BINS_OF_OPINION];

        for (Map.Entry<Integer, List<Post>> entry : feedMap.entrySet()) {
            Integer userId = entry.getKey();
            List<Post> feed = entry.getValue();
            Agent agent = agentSet[userId];
            int classId = agent.getOpinionClass();

            if (feed.isEmpty())
                continue;

            double sum = 0.0;
            for (Post post : feed) {
                sum += post.getPostOpinion();
            }
            double mean = sum / feed.size();
            this.feedMeanArray[classId] += mean;

            double var = 0.0;
            for (Post post : feed) {
                double diff = post.getPostOpinion() - mean;
                var += diff * diff;
            }
            var /= feed.size(); // or (feed.size() - 1) for unbiased

            classVarianceSum[classId] += var;
            agentCount[classId]++;
        }

        for (int i = 0; i < Const.NUM_OF_BINS_OF_OPINION; i++) {
            if (agentCount[i] != 0) {
                this.feedVarArray[i] = classVarianceSum[i] / agentCount[i];
                this.feedMeanArray[i] = this.feedMeanArray[i] / agentCount[i];
            }
        }

    }

    // compute mean and var of every agent's comfort rate
    public void computeCRateArray(Agent[] agentSet) {
        Arrays.fill(this.cRateMeanArray, 0.0);
        Arrays.fill(this.cRateVarArray, 0.0);

        double[] classVarianceSum = new double[Const.NUM_OF_BINS_OF_OPINION];
        int[] agentCount = new int[Const.NUM_OF_BINS_OF_OPINION];

        for (Map.Entry<Integer, List<Post>> entry : feedMap.entrySet()) {
            Integer userId = entry.getKey();
            Agent agent = agentSet[userId];
            int classId = agent.getOpinionClass();

            double cRate = agent.getAverageComfortRate(); // ★ agent が持っている値を使う

            this.cRateMeanArray[classId] += cRate;
            classVarianceSum[classId] += cRate * cRate; // 後で分散を計算するため平方和を保持
            agentCount[classId]++;
        }

        // クラスごとの平均・分散を計算
        for (int i = 0; i < Const.NUM_OF_BINS_OF_OPINION; i++) {
            if (agentCount[i] != 0) {
                double mean = this.cRateMeanArray[i] / agentCount[i];
                double meanSq = classVarianceSum[i] / agentCount[i];
                double var = meanSq - mean * mean; // 分散 = E[x^2] - (E[x])^2

                this.cRateMeanArray[i] = mean;
                this.cRateVarArray[i] = var;
            }
        }
    }

    // 2026-08-25: same feedMap population as computeCRateArray, reclassified by continuous
    // opinion (Const.band08Of) instead of Agent.opinionClass -- see that method's javadoc.
    public void computeCRateBand08Array(Agent[] agentSet) {
        Arrays.fill(this.cRateMeanBand08Array, 0.0);
        Arrays.fill(this.popCountBand08Array, 0);

        for (Map.Entry<Integer, List<Post>> entry : feedMap.entrySet()) {
            Agent agent = agentSet[entry.getKey()];
            int band = Const.band08Of(agent.getOpinion());
            this.cRateMeanBand08Array[band] += agent.getAverageComfortRate();
            this.popCountBand08Array[band]++;
        }

        for (int i = 0; i < 3; i++) {
            if (popCountBand08Array[i] != 0) {
                this.cRateMeanBand08Array[i] /= popCountBand08Array[i];
            }
        }
    }

    // Vocal-minority readout: what share of this step's ORIGINAL posts (postCash —
    // same population as postOpinionVar: excludes reposts and manipulated-hub posts,
    // see OpinionDynamics buildMetricsRow) was authored by each opinion-bin class.
    // Complements cRateMean_i (comfort/receptiveness) by measuring actual output
    // volume per class instead of receptiveness to it.
    public void computePostShareArray(Agent[] agentSet) {
        Arrays.fill(this.postShareArray, 0.0);
        int total = postCash.size();
        if (total == 0) return;
        for (Post post : postCash) {
            int classId = agentSet[post.getPostUserId()].getOpinionClass();
            this.postShareArray[classId] += 1.0;
        }
        for (int i = 0; i < this.postShareArray.length; i++) this.postShareArray[i] /= total;
    }

    public void computePostVariance() {
        int size = postCash.size();
        if (size == 0) {
            this.postOpinionVar = -1;
            return;
        }

        double sum = 0.0;
        for (Post post : postCash) {
            sum += post.getPostOpinion();
        }
        double mean = sum / size;

        double squaredDiffSum = 0.0;
        for (Post post : postCash) {
            double diff = post.getPostOpinion() - mean;
            squaredDiffSum += diff * diff;
        }
        this.postOpinionVar = squaredDiffSum / size;
    }

    public double getPostOpinionVar() {
        return postOpinionVar;
    }

    public double getExposureOpinionVar() {
        return exposureOpinionVar;
    }

    public double getExposureOpinionMean() {
        return exposureOpinionMean;
    }

    // C2: opinion distribution of content actually delivered to feeds this step.
    // Unlike postOpinionVar (original posts only), this includes reposts and is
    // reach-weighted (a widely reposted post is counted in every feed it reaches),
    // so repost-hub amplification is reflected. Posts authored by manipulated
    // (target) hubs are excluded so the metric measures the population's exposure.
    // The mean doubles as a one-sided "capture" signal for asymmetric backgrounds.
    public void computeExposureMetrics(Agent[] agentSet) {
        double sum = 0.0;
        long count = 0;
        for (List<Post> feed : feedMap.values()) {
            for (Post post : feed) {
                if (agentSet[post.getPostUserId()].getTarget()) continue;
                sum += post.getPostOpinion();
                count++;
            }
        }

        if (count == 0) {
            this.exposureOpinionVar = -1;
            this.exposureOpinionMean = 0.0;
            return;
        }

        double mean = sum / count;
        double squaredDiffSum = 0.0;
        for (List<Post> feed : feedMap.values()) {
            for (Post post : feed) {
                if (agentSet[post.getPostUserId()].getTarget()) continue;
                double diff = post.getPostOpinion() - mean;
                squaredDiffSum += diff * diff;
            }
        }

        this.exposureOpinionMean = mean;
        this.exposureOpinionVar = squaredDiffSum / count;
    }

    public double[] computeClusteringCoefficients(double[][] adj) {
        double[] clustering = new double[n];

        for (int i = 0; i < n; i++) {

            Set<Integer> neighbors = new HashSet<>();
            for (int j = 0; j < n; j++) {
                if (adj[i][j] > 0.0)
                    neighbors.add(j); // out-neighbor
                if (adj[j][i] > 0.0)
                    neighbors.add(j); // in-neighbor
            }
            neighbors.remove(i);

            int k_total = neighbors.size();
            if (k_total < 2) {
                clustering[i] = 0.0;
                continue;
            }

            int linkCount = 0;
            for (int u : neighbors) {
                for (int v : neighbors) {
                    if (u != v && adj[u][v] > 0.0) {
                        linkCount++;
                    }
                }
            }

            clustering[i] = (double) linkCount / (k_total * (k_total - 1));
        }

        return clustering;
    }

    // 2026-08-06: per-opinion-class echo-chamber structural metrics on the follow graph
    // (docs/report/2026-08-02-delayed-moderate-conduit-pilot.md HANDOFF -- feed-composition
    // mechanism investigation). Restricts to (a) the graph's largest connected component (LCC,
    // undirected reachability: adj[i][j]>0 OR adj[j][i]>0) and (b) population agents (excludes
    // pinned hub/target agents, same convention as computeOpinionAssortativity/
    // computeCrossCuttingFraction above), then for each of the NUM_OF_BINS_OF_OPINION classes
    // reports the size, directed-edge density, average undirected local clustering coefficient, and
    // triangle count of the INDUCED subgraph on {population agents in the LCC with that
    // opinionClass}. Deliberately uses the STANDARD undirected clustering formula
    // (2*links/(k*(k-1))) rather than computeClusteringCoefficients' directed-ordered-pair
    // convention above -- this is a fresh echo-chamber-cohesion metric, not a variant of the
    // existing per-agent clustering export, so it isn't bound to that method's legacy convention.
    public EchoChamberStats[] computeEchoChamberByClass(Agent[] agentSet, double[][] adj) {
        int n = adj.length;
        int[] comp = findConnectedComponents(adj);
        int numComp = 0;
        for (int c : comp) numComp = Math.max(numComp, c + 1);
        int[] compSize = new int[numComp];
        for (int c : comp) compSize[c]++;
        int largest = 0;
        for (int i = 1; i < numComp; i++) if (compSize[i] > compSize[largest]) largest = i;

        List<List<Integer>> byClass = new ArrayList<>();
        for (int c = 0; c < Const.NUM_OF_BINS_OF_OPINION; c++) byClass.add(new ArrayList<>());
        for (int i = 0; i < n; i++) {
            if (agentSet[i].getTarget()) continue;      // population only (R1 hub-exclusion convention)
            if (comp[i] != largest) continue;            // LCC only
            byClass.get(agentSet[i].getOpinionClass()).add(i);
        }

        EchoChamberStats[] result = new EchoChamberStats[Const.NUM_OF_BINS_OF_OPINION];
        for (int c = 0; c < Const.NUM_OF_BINS_OF_OPINION; c++) {
            List<Integer> members = byClass.get(c);
            int k = members.size();
            EchoChamberStats s = new EchoChamberStats();
            s.nodeCount = k;
            if (k >= 2) {
                long directedEdges = 0;
                for (int i : members) {
                    for (int j : members) {
                        if (i != j && adj[i][j] > 0.0) directedEdges++;
                    }
                }
                s.density = (double) directedEdges / ((double) k * (k - 1));

                double clusterSum = 0.0;
                long triangleSum = 0;
                for (int i : members) {
                    List<Integer> nb = new ArrayList<>();
                    for (int j : members) {
                        if (j != i && (adj[i][j] > 0.0 || adj[j][i] > 0.0)) nb.add(j);
                    }
                    int kk = nb.size();
                    if (kk >= 2) {
                        int linked = 0;
                        for (int a = 0; a < kk; a++) {
                            for (int b = a + 1; b < kk; b++) {
                                int u = nb.get(a), v = nb.get(b);
                                if (adj[u][v] > 0.0 || adj[v][u] > 0.0) linked++;
                            }
                        }
                        clusterSum += 2.0 * linked / ((double) kk * (kk - 1));
                        triangleSum += linked;
                    }
                }
                s.avgClusteringCoeff = clusterSum / k;
                s.triangleCount = triangleSum / 3; // each triangle counted once per vertex above
            }
            result[c] = s;
        }
        return result;
    }

    // Undirected connected-component labeling (BFS), treating adj[i][j]>0 OR adj[j][i]>0 as an edge
    // -- same symmetrization convention computeClusteringCoefficients uses for neighbor membership.
    private int[] findConnectedComponents(double[][] adj) {
        int n = adj.length;
        int[] comp = new int[n];
        Arrays.fill(comp, -1);
        int next = 0;
        for (int start = 0; start < n; start++) {
            if (comp[start] != -1) continue;
            ArrayDeque<Integer> queue = new ArrayDeque<>();
            queue.add(start);
            comp[start] = next;
            while (!queue.isEmpty()) {
                int u = queue.poll();
                for (int v = 0; v < n; v++) {
                    if (comp[v] == -1 && (adj[u][v] > 0.0 || adj[v][u] > 0.0)) {
                        comp[v] = next;
                        queue.add(v);
                    }
                }
            }
            next++;
        }
        return comp;
    }

    public static class EchoChamberStats {
        public int nodeCount;
        public double density;
        public double avgClusteringCoeff;
        public long triangleCount;
    }

    public void computeHighComfortRateNumArray(Agent[] agentSet) {
        Arrays.fill(this.highComfortRateNumArray, 0.0);

        for (Agent agent : agentSet) {
            int classId = agent.getOpinionClass();
            double cRate = agent.getAverageComfortRate();
            if (cRate >= Const.OPINION_PREVALENCE) {
                this.highComfortRateNumArray[classId] += 1.0;
            }
        }
    }
}
