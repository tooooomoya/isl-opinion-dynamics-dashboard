package network;

import agent.Agent;
import java.util.*;
import rand.randomGenerator;

/**
 * Degree-matched control for HolmeKimNetwork: build the Holme-Kim graph, then randomize it with
 * double edge swaps (a->b, c->d  =>  a->d, c->b), which keeps every node's in- AND out-degree exactly
 * while destroying the age ordering (new nodes follow only older ones), the near-acyclicity and the
 * clustering. Hubs and the in-degree tail are unchanged; wiring is uniformly random given the degrees.
 * With the same seed the underlying HK graph is the one `network=hk` builds, so degree sequences match run-for-run.
 */
public class HolmeKimShuffledNetwork extends Network {
    private final HolmeKimNetwork hk;
    private static final int SWAPS_PER_EDGE = 20;

    public HolmeKimShuffledNetwork(int size, int m, int A, double pt) {
        super(size);
        this.hk = new HolmeKimNetwork(size, m, A, pt);
    }

    @Override
    public void makeNetwork(Agent[] agentSet) {
        hk.makeNetwork(agentSet);
        int n = getSize();
        double[][] adj = hk.getAdjacencyMatrix();
        List<int[]> edges = new ArrayList<>();
        for (int i = 0; i < n; i++) for (int j = 0; j < n; j++) if (i != j && adj[i][j] > 0) edges.add(new int[]{i, j});
        int e = edges.size(), done = 0;
        for (long t = 0; t < (long) SWAPS_PER_EDGE * e; t++) {
            int[] p = edges.get(randomGenerator.network().nextInt(e)), q = edges.get(randomGenerator.network().nextInt(e));
            int a = p[0], b = p[1], c = q[0], d = q[1];
            if (a == c || b == d || a == d || c == b || adj[a][d] > 0 || adj[c][b] > 0) continue;
            adj[a][b] = 0; adj[c][d] = 0; adj[a][d] = 1.0; adj[c][b] = 1.0;
            p[1] = d; q[1] = b; done++;
        }
        System.out.println("HK degree-matched shuffle: " + done + " swaps on " + e + " edges");
        setAdjacencyMatrix(adj);
    }
}
