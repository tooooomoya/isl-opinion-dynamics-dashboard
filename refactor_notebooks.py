
import json
import os

def update_notebook(file_path, replacements):
    with open(file_path, 'r', encoding='utf-8') as f:
        nb = json.load(f)
    
    modified_cells = []
    for cell in nb['cells']:
        if cell['cell_type'] == 'code':
            source = "".join(cell['source'])
            for target_func, new_source in replacements.items():
                if target_func in source:
                    cell['source'] = [line + "\n" for line in new_source.split("\n")]
                    # Remove the extra newline from the last line if it's empty
                    if cell['source'][-1] == "\n":
                        cell['source'] = cell['source'][:-1]
                    modified_cells.append(target_func)
                    break
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)
    
    return modified_cells

# --- result-summary.ipynb replacements ---
rs_replacements = {
    "def load_post_data_all_steps": """def load_post_data_all_steps(run_dir):
    post_dir = os.path.join(run_dir, "posts")
    if not os.path.exists(post_dir): return pd.DataFrame()
    files = glob.glob(os.path.join(post_dir, "post_result_*.csv"))
    if not files: return pd.DataFrame()
    
    dfs = []
    for f in files:
        try:
            df_temp = pd.read_csv(f)
            if not df_temp.empty:
                dfs.append(df_temp)
        except: pass
    
    if not dfs: return pd.DataFrame()
    
    df_all = pd.concat(dfs, ignore_index=True)
    if "step" in df_all.columns:
        df_all = df_all.sort_values("step")
    
    # Ensure all BINS are present
    for b in BINS:
        if b not in df_all.columns:
            df_all[b] = 0
            
    return df_all""",
    "def load_and_process_seed": """def load_and_process_seed(seed_dir, seed_name):
    \"\"\"
    1つのシード（run_?）フォルダ内の post データを読み込み、平滑化してDataFrameを返す
    \"\"\"
    post_dir = os.path.join(seed_dir, "posts")
    if not os.path.exists(post_dir):
        print(f"Skipping {seed_name}: post folder not found.")
        return None

    # ファイルリストを取得
    files = glob.glob(os.path.join(post_dir, "post_result_*.csv"))
    if not files: return None
    
    dfs = []
    for f in files:
        try:
            dfs.append(pd.read_csv(f))
        except: pass
    if not dfs: return None
    
    df_all = pd.concat(dfs, ignore_index=True).sort_values("step")
    if MAX_INDEX is not None:
        df_all = df_all[df_all["step"] <= MAX_INDEX]

    ratios = {b: [] for b in BINS}
    counts = []
    steps = []

    # 各行を処理
    for _, row in df_all.iterrows():
        # 投稿数を取得（sumOfPostsがあれば優先、なければbinの合計）
        if "sumOfPosts" in row:
            total_posts = int(row["sumOfPosts"])
        else:
            total_posts = sum([int(row.get(b, 0)) for b in BINS])
        
        # 投稿数が0の場合の割合は0とする（またはnan）
        if total_posts > 0:
            for b in BINS:
                ratios[b].append(int(row.get(b, 0)) / total_posts)
        else:
            for b in BINS:
                ratios[b].append(0.0)

        counts.append(total_posts)
        steps.append(int(row["step"]))

    if not steps:
        return None

    # --- 平滑化処理 ---
    # ステップは代表値（区間の開始または中央）をとる
    smoothed_steps = steps[::WINDOW_SIZE]
    
    data = {"step": smoothed_steps}
    
    # 割合の平滑化
    for b in BINS:
        data[b] = smooth_list(ratios[b], WINDOW_SIZE)
        
    # 投稿数の平滑化
    data["sumOfPosts"] = smooth_list(counts, WINDOW_SIZE)
    
    # 長さが合わない場合の調整（念のため）
    min_len = min([len(v) for v in data.values()])
    for k in data.keys():
        data[k] = data[k][:min_len]

    df_seed = pd.DataFrame(data)
    df_seed["seed"] = seed_name
    return df_seed"""
}

# --- polarization-analysis.ipynb replacements ---
pa_replacements = {
    "def load_and_process_seed": rs_replacements["def load_and_process_seed"],
    "def load_single_experiment_metrics": """def load_single_experiment_metrics(data_dir, max_step=None):
    \"\"\"
    指定ディレクトリ内の result_*.csv を全て読み込んで結合・ソートする
    \"\"\"
    # ファイルの検索
    files = sorted(glob.glob(os.path.join(data_dir, "result_*.csv")))
    
    if not files:
        # ファイルがない場合はNoneを返す（エラーで止めない）
        return None

    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f)
            # 最低限必要なカラムがあるかチェック
            if "step" not in df.columns:
                continue
                
            if max_step is not None:
                df = df[df["step"] <= max_step]
            
            dfs.append(df)
        except Exception as e:
            print(f"[Warning] Skip {f}: {e}")

    if not dfs:
        return None

    # 結合してstep順に並べ替え
    out = pd.concat(dfs, ignore_index=True)
    out = out.sort_values("step").reset_index(drop=True)
    return out""",
    "def load_seed_data": """def load_seed_data(run_dir):
    \"\"\"
    1つのシード（runディレクトリ）から metrics を読み込む
    \"\"\"
    metrics_path = os.path.join(run_dir, "metrics")
    # load_single_experiment_metrics を使って全 result_*.csv を読み込む
    df = load_single_experiment_metrics(metrics_path, MAX_STEP)
    
    if df is None or df.empty:
        return None

    # 差分 (Apparent - Overall) を計算
    if "opinionVar" in df.columns and "postOpinionVar" in df.columns:
        df["diffVar"] = df["postOpinionVar"] - df["opinionVar"]
        
    return df"""
}

print("Updating result-summary.ipynb...")
modified_rs = update_notebook('result-summary.ipynb', rs_replacements)
print(f"Modified in result-summary.ipynb: {modified_rs}")

print("\\nUpdating polarization-analysis.ipynb...")
modified_pa = update_notebook('polarization-analysis.ipynb', pa_replacements)
print(f"Modified in polarization-analysis.ipynb: {modified_pa}")
