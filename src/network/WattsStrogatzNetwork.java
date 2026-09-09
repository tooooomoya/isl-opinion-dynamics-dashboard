package network;

import agent.Agent;
import rand.randomGenerator;

public class WattsStrogatzNetwork extends Network {
    private int K; // 各ノードの出次数（偶数である必要があります）
    private double beta; // 配線換え確率 (0 <= beta <= 1)

    /**
     * @param size ネットワークのノード数
     * @param K 各ノードの出次数。例えば4なら右隣の4ノードへの有向辺を持ちます。
     * @param beta 配線換え確率。0なら正規格子、1ならランダムグラフに近づきます。
     */
    public WattsStrogatzNetwork(int size, int K, double beta) {
        super(size);
        this.K = K;
        this.beta = beta;
    }

    @Override
    public void makeNetwork(Agent[] agentSet) {
        System.out.println("start making Watts-Strogatz network");

        int n = getSize();
        int halfK = this.K / 2;

        // Step 1: 有向リング格子の作成
        // 各ノード i から右隣の halfK 個のノードへの有向辺のみ設定する
        for (int i = 0; i < n; i++) {
            for (int j = 1; j <= halfK; j++) {
                int neighbor = (i + j) % n;
                setEdge(i, neighbor, 1.0);
            }
        }

        // Step 2: 有向辺の配線換え（Rewiring）
        // 各有向辺 (i → originalNeighbor) について、確率 beta で先端を付け替える
        for (int i = 0; i < n; i++) {
            for (int j = 1; j <= halfK; j++) {
                if (randomGenerator.network().nextDouble() < this.beta) {
                    int originalNeighbor = (i + j) % n;

                    // 有向辺 (i → originalNeighbor) のみ削除
                    removeEdge(i, originalNeighbor);

                    // 新しい接続先を探す（自己ループ・多重辺を回避）
                    int newNeighbor = -1;
                    boolean found = false;
                    int attempts = 0;
                    while (attempts < n) {
                        int candidate = randomGenerator.network().nextInt(n);
                        if (candidate != i && adjacencyMatrix[i][candidate] == 0) {
                            newNeighbor = candidate;
                            found = true;
                            break;
                        }
                        attempts++;
                    }

                    if (found) {
                        setEdge(i, newNeighbor, 1.0);
                    } else {
                        // 接続先が見つからなかった場合は元の辺を戻す
                        setEdge(i, originalNeighbor, 1.0);
                    }
                }
            }
        }
    }
}