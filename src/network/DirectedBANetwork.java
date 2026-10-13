package network;

import agent.Agent;
import rand.randomGenerator;

/**
 * Directed scale-free start (Price / Barabasi-Albert style growth). Agents arrive one at a time; each new
 * agent follows exactly {@code outDegree} distinct earlier agents, drawn without replacement with probability
 * proportional to (current in-degree + attractiveness). Out-degree is therefore the same for everyone
 * (the follow list length is conserved by rewire), while in-degree (followers) becomes heavy-tailed.
 *
 * {@code attractiveness} sets how strong the initial inequality is: 0 is the strongest rich-get-richer; a large
 * value approaches uniform attachment (no hubs). Values near outDegree give moderate hubs. The first
 * outDegree+1 agents follow each other completely so that everyone has outDegree followees.
 * Arrival order is the agent id, which is independent of X (X is drawn i.i.d.), so no initial homophily.
 */
public class DirectedBANetwork extends Network {
    private final int outDegree;
    private final double attractiveness;

    public DirectedBANetwork(int size, int outDegree, double attractiveness) {
        super(size);
        this.outDegree = outDegree;
        this.attractiveness = attractiveness;
    }

    @Override
    public void makeNetwork(Agent[] agentSet) {
        int n = getSize();
        int m = Math.min(outDegree, n - 1);
        int seedSize = Math.min(m + 1, n);
        int[] inDeg = new int[n];
        for (int i = 0; i < seedSize; i++) {
            for (int j = 0; j < seedSize; j++) {
                if (i != j) { setEdge(i, j, 1.0); inDeg[j]++; }
            }
        }
        double[] w = new double[n];
        for (int v = seedSize; v < n; v++) {
            for (int j = 0; j < v; j++) w[j] = inDeg[j] + attractiveness;
            for (int pick = 0; pick < m; pick++) {
                double total = 0;
                for (int j = 0; j < v; j++) total += w[j];
                double r = randomGenerator.network().nextDouble() * total;
                int chosen = v - 1;
                double acc = 0;
                for (int j = 0; j < v; j++) {
                    acc += w[j];
                    if (r < acc && w[j] > 0) { chosen = j; break; }
                }
                setEdge(v, chosen, 1.0);
                inDeg[chosen]++;
                w[chosen] = 0; // without replacement within this agent's draw
            }
        }
    }
}
