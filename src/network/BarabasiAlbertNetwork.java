package network;

import agent.Agent;
import java.util.*;
import rand.randomGenerator;

public class BarabasiAlbertNetwork extends Network {
    private int m; // 各ステップで新規ノードが張るリンクの本数

    /**
     * コンストラクタ
     * @param size 全ノード数
     * @param m 新規ノード追加時に既存ノードと繋ぐ本数（例: 2〜4程度が一般的）
     */
    public BarabasiAlbertNetwork(int size, int m) {
        super(size);
        this.m = m;
    }

    @Override
    public void makeNetwork(Agent[] agentSet) {
        System.out.println("start making Barabasi-Albert network");

        // 優先的選択（Preferential Attachment）を実現するためのリスト
        // ノードIDがその次数分だけ重複して格納される "ルーレット" の役割
        List<Integer> degreePool = new ArrayList<>();

        int n = getSize();
        
        // 初期ネットワークの作成（m個のノードによる完全グラフ）
        // 最初の数個のノードがないと接続先がないため
        int initialNodes = m + 1;
        if (initialNodes > n) initialNodes = n;

        for (int i = 0; i < initialNodes; i++) {
            for (int j = i + 1; j < initialNodes; j++) {
                // 無向グラフとして双方向リンクを設定
                addEdge(i, j); 
                addEdge(j, i);

                // 次数プールに追加（iとjそれぞれの次数が増えたため）
                degreePool.add(i);
                degreePool.add(j);
            }
        }

        // 残りのノードを1つずつ追加し、既存ノードに接続
        for (int newNode = initialNodes; newNode < n; newNode++) {
            Set<Integer> targets = new HashSet<>();

            // m本のリンクを張る相手を探す
            while (targets.size() < this.m) {
                if (degreePool.isEmpty()) break;

                // degreePoolからランダムに引くことで、
                // 次数が高い（pool内にたくさん入っている）ノードが選ばれやすくなる
                int candidate = degreePool.get(randomGenerator.network().nextInt(degreePool.size()));

                // 自己ループと多重辺の回避
                if (candidate != newNode && !targets.contains(candidate)) {
                    targets.add(candidate);
                }
            }

            // 選ばれたターゲットと接続
            for (int target : targets) {
                addEdge(newNode, target);
                //addEdge(target, newNode); // 有向グラフにしたい場合はこの行を削除

                // 次数プールを更新
                degreePool.add(newNode);
                degreePool.add(target);
            }
        }
    }

    /**
     * リンク設定のヘルパーメソッド（親クラスのsetEdgeをラップ）
     */
    private void addEdge(int u, int v) {
        // 親クラスの実装に合わせて重みを1に設定
        setEdge(u, v, 1);
    }
}