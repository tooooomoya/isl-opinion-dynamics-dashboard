package network;

import agent.Agent;
import rand.randomGenerator;

/**
 * Homophilous start: every agent follows exactly {@code outDegree} distinct others, drawn without
 * replacement with probability proportional to exp(-gamma * |x_i - x_j|), so agents with similar X
 * are probabilistically close in the network. gamma = 0 gives a uniform random graph with fixed
 * out-degree; larger gamma gives stronger initial homophily. Needs the agents' X, so agents must exist
 * before the network is built. (In-degree is not controlled: agents near the middle of the X range
 * are similar to more people and so tend to receive more follows.)
 */
public class HomophilyNetwork extends Network {
    private final int outDegree;
    private final double gamma;

    public HomophilyNetwork(int size, int outDegree, double gamma) {
        super(size);
        this.outDegree = outDegree;
        this.gamma = gamma;
    }

    @Override
    public void makeNetwork(Agent[] agentSet) {
        int n = getSize();
        int k = Math.min(outDegree, n - 1);
        double[] key = new double[n];
        for (int i = 0; i < n; i++) {
            double xi = agentSet[i].getOpinion();
            for (int j = 0; j < n; j++) {
                if (j == i) { key[j] = Double.NEGATIVE_INFINITY; continue; }
                double w = Math.exp(-gamma * Math.abs(xi - agentSet[j].getOpinion()));
                // Efraimidis-Spirakis: the k largest of u^(1/w) are a weighted sample without replacement;
                // log(u)/w has the same ordering.
                key[j] = Math.log(randomGenerator.network().nextDouble()) / Math.max(w, 1e-300);
            }
            for (int pick = 0; pick < k; pick++) {
                int best = -1;
                for (int j = 0; j < n; j++) {
                    if (key[j] > (best < 0 ? Double.NEGATIVE_INFINITY : key[best]) && key[j] != Double.NEGATIVE_INFINITY) best = j;
                }
                if (best < 0) break;
                setEdge(i, best, 1.0);
                key[best] = Double.NEGATIVE_INFINITY;
            }
        }
    }
}
