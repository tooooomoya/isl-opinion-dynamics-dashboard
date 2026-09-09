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

    public AssertionCheck(Agent[] agentSet, Network network, int agentNum, int maxStep) {
        this.agentSet = agentSet;
        this.network = network;
        this.n = agentNum;
        this.numOfError = new int[maxStep + 1];
        this.maxStep = maxStep;
    }

    public void assertionChecker(Agent[] agentSet, AdminOptim admin, int agentNum, int step) {
        // R22: the follow graph has a single owner (AdminOptim) now, so the old followList-vs-admin
        // consistency check is obsolete (there is no second copy to desync). Remaining invariants:

        // A follow edge must never coexist with a block of the same target (unfollow blocks + drops).
        for (int i = 0; i < n; i++) {
            boolean[] blocked = agentSet[i].getBlockedUserList();
            for (int j : admin.getFollowees(i)) {
                if (blocked[j]) {
                    System.out.println("AC Error: agent " + i + " follows blocked user " + j);
                    numOfError[step]++;
                }
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