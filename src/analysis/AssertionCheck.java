package analysis;

import admin.*;
import agent.Agent;
import network.*;

public class AssertionCheck {
    private Agent[] agentSet;
    private Network network;
    private int n;
    private int[] numOfError;
    private int maxStep;
    private int[] initialOutDegree; // snapshot of out-degrees at construction time

    public AssertionCheck(Agent[] agentSet, Network network, int agentNum, int maxStep) {
        this.agentSet = agentSet;
        this.network = network;
        this.n = agentNum;
        this.numOfError = new int[maxStep + 1];
        this.maxStep = maxStep;
    }

    /** Record the t=0 out-degrees that rewire must conserve. */
    public void snapshotOutDegrees(AdminOptim admin) {
        initialOutDegree = new int[n];
        for (int i = 0; i < n; i++) initialOutDegree[i] = admin.followeeCount(i);
    }

    public void assertionChecker(Agent[] agentSet, AdminOptim admin, int agentNum, int step) {
        // R22: the follow graph has a single owner (AdminOptim) now, so the old followList-vs-admin
        // consistency check is obsolete (there is no second copy to desync). Remaining invariants:

        // Out-degree is conserved by rewire: every agent keeps its initial followee count.
        for (int i = 0; i < n; i++) {
            if (initialOutDegree != null && admin.followeeCount(i) != initialOutDegree[i]) {
                System.out.println("AC Error: agent " + i + " out-degree " + admin.followeeCount(i)
                        + " != initial " + initialOutDegree[i]);
                numOfError[step]++;
            }
            if (admin.follows(i, i)) {
                System.out.println("AC Error: agent " + i + " follows itself");
                numOfError[step]++;
            }
        }

        // opinion should be in [-1, 1].
        for (int i = 0; i < n; i++) {
            double o = agentSet[i].getOpinion();
            if (o < -1 || o > 1) {
                System.out.println("AC Error: opinion is out of the range in user " + i);
                numOfError[step]++;
            }
        }

        // R4: fully-pinned hubs (stubbornness=1, e.g. InterventionSetup.pinHub) must keep their
        // assigned opinion. 2026-08-02: getTarget() alone no longer implies full pinning --
        // ExperimentConfig.pinNeutralIds marks target=true (still artificially-assigned intrinsic
        // opinion, still excluded from natural-population metrics elsewhere) but deliberately
        // leaves stubbornness at its normal per-agent draw so opinion CAN drift -- so this
        // invariant must gate on stubbornness==1, not just getTarget().
        for (int i = 0; i < n; i++) {
            if (agentSet[i].getTarget() && agentSet[i].getStubbornness() >= 1.0
                    && Math.abs(agentSet[i].getOpinion() - agentSet[i].getIntrinsicOpinion()) > 1e-9) {
                System.out.println("AC Error: pinned hub " + i + " drifted from its assigned opinion");
                numOfError[step]++;
            }
        }
    }

    public void reportASError(){
        int sumError = 0;
        for(int i = 0; i < maxStep ; i++){
                sumError += numOfError[i];
        }
        System.out.println("the sum of error reported : " + sumError);
    }
}