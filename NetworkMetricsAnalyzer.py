import networkx as nx
import pandas as pd
import numpy as np
import os
import powerlaw

class NetworkMetricsAnalyzer:
    """
    指定したGEXFファイルを読み込み、ネットワークの主要な統計量を計算し、
    表示およびCSV出力を行うヘルパークラス。
    """
    def __init__(self, gexf_path, output_csv=None):
        self.gexf_path = gexf_path
        self.output_csv = output_csv
        self.metrics = {}
        
        print(f"Loading GEXF file: {self.gexf_path} ...")
        self.G = nx.read_gexf(gexf_path)
        print("Load complete. Calculating metrics (this may take a while for large graphs)...\n")
        
        self._calculate_metrics()
        self.display_metrics()
        
        if self.output_csv:
            self.save_to_csv()

    def _calculate_metrics(self):
        G = self.G
        is_directed = G.is_directed()
        
        # 1. ノード数・エッジ数
        num_nodes = G.number_of_nodes()
        num_edges = G.number_of_edges()
        
        # 2. 平均次数・平均入次数
        degrees = [d for n, d in G.degree()]
        avg_degree = sum(degrees) / num_nodes if num_nodes > 0 else 0
        
        if is_directed:
            in_degrees = [d for n, d in G.in_degree()]
            avg_in_degree = sum(in_degrees) / num_nodes if num_nodes > 0 else 0
        else:
            avg_in_degree = np.nan # 無向グラフの場合はNaN
            
        # 3. 平均クラスタ係数
        # 有向グラフの場合は無向グラフに変換して計算するのが一般的
        G_undirected = G.to_undirected() if is_directed else G
        avg_clustering = nx.average_clustering(G_undirected)
        
        # 4. 平均経路長・NW直径 (最大連結成分に対して計算)
        if num_nodes > 0:
            if is_directed:
                # 有向グラフの場合は最大弱連結成分を使用
                largest_cc = max(nx.weakly_connected_components(G), key=len)
            else:
                largest_cc = max(nx.connected_components(G), key=len)
            
            G_largest = G.subgraph(largest_cc).copy()
            # 経路長や直径は無向グラフとして計算（有向のままだと到達不能ノード間でエラーになるため）
            G_largest_un = G_largest.to_undirected()
            
            try:
                avg_path_length = nx.average_shortest_path_length(G_largest_un)
                diameter = nx.diameter(G_largest_un)
            except nx.NetworkXError:
                avg_path_length = np.nan
                diameter = np.nan
        else:
            avg_path_length = np.nan
            diameter = np.nan

        # 5. モジュラリティ (Louvain法)
        # ネットワークが大きすぎると時間がかかるため、無向グラフで計算
        try:
            communities = nx.community.louvain_communities(G_undirected)
            modularity = nx.community.modularity(G_undirected, communities)
        except Exception as e:
            print(f"Modularity calculation failed: {e}")
            modularity = np.nan

        # 6. 冪乗指数 (Gamma)
        # powerlaw パッケージを使用して次数分布にフィットさせる
        try:
            # 次数が0のノードは除外（powerlawの計算でエラーになるため）
            valid_degrees = [d for d in degrees if d > 0]
            if len(valid_degrees) > 0:
                fit = powerlaw.Fit(valid_degrees, discrete=True, verbose=False)
                gamma = fit.power_law.alpha
            else:
                gamma = np.nan
        except Exception as e:
            print(f"Power-law calculation failed: {e}")
            gamma = np.nan

        # 結果を辞書に格納
        self.metrics = {
            "File Name": os.path.basename(self.gexf_path),
            "Is Directed": is_directed,
            "Number of Nodes": num_nodes,
            "Number of Edges": num_edges,
            "Average Degree": avg_degree,
            "Average In-Degree": avg_in_degree,
            "Average Clustering Coefficient": avg_clustering,
            "Average Path Length (Largest CC)": avg_path_length,
            "Network Diameter (Largest CC)": diameter,
            "Modularity (Louvain)": modularity,
            "Power-law Exponent (Gamma)": gamma
        }

    def display_metrics(self):
        """計算された統計量をコンソールに整形して表示する"""
        print("="*50)
        print(f"Network Metrics: {self.metrics.get('File Name')}")
        print("="*50)
        for key, value in self.metrics.items():
            if isinstance(value, float):
                print(f"{key:<35}: {value:.4f}")
            else:
                print(f"{key:<35}: {value}")
        print("="*50)

    def save_to_csv(self):
        """計算された統計量をCSVファイルに出力する（追記モード）"""
        df = pd.DataFrame([self.metrics])
        
        # ファイルが存在する場合はヘッダーなしで追記、存在しない場合は新規作成
        file_exists = os.path.isfile(self.output_csv)
        df.to_csv(self.output_csv, mode='a', index=False, header=not file_exists, encoding='utf-8-sig')
        print(f"📊 Metrics successfully saved to: {self.output_csv}")

    def get_metrics_df(self):
        """pandasのDataFrameとして取得したい場合に使用"""
        return pd.DataFrame([self.metrics])

# ==========================================
# 使い方 (実行例)
# ==========================================
if __name__ == "__main__":
    # 分析したいGEXFファイルのパス
    target_gexf = "./results/run_3_dir_0.0/GEXF/lambda_0.0/step_0.gexf" 
    
    # 出力するCSVファイルのパス
    # 複数ファイルをループで回した場合でも、同じCSVにどんどん行が追加(追記)されていきます
    output_csv_path = "./results/network_summary_stats.csv"
    
    # ファイルが存在する場合のみ実行するテストコード
    if os.path.exists(target_gexf):
        # クラスをインスタンス化するだけで、読み込み→計算→表示→CSV保存 まで一気に実行されます
        analyzer = NetworkMetricsAnalyzer(gexf_path=target_gexf, output_csv=output_csv_path)
        
        # 必要であればDataFrameとして受け取ることも可能
        df_stats = analyzer.get_metrics_df()
    else:
        print(f"Please place a '{target_gexf}' file in the current directory to test.")
        
    # ※ フォルダ内のすべての .gexf ファイルを一括で処理したい場合の書き方例:
    # gexf_files = glob.glob("data/*.gexf")
    # for file in gexf_files:
    #     NetworkMetricsAnalyzer(gexf_path=file, output_csv="all_networks_stats.csv")