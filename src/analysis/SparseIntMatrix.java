package analysis;

import java.util.HashMap;
import java.util.Map;
import java.util.Set;

/**
 * R23b (docs/report/2026-07-07-model-revision-requirements.md): sparse integer adjacency counts
 * for the repost/relay interaction graph.
 *
 * Replaces the dense {@code int[N][N]} repost matrices, whose per-step full-grid scans in the
 * interaction metrics (Analysis) cost O(N^2) regardless of how few edges actually exist, and
 * whose N=5000 footprint (~100 MB each) blocked R17 scaling. Iteration is over realized
 * (source -> target) entries only. A dense snapshot is materialized on demand via
 * {@link #toDense(int)} solely at the 5000-step gephi export cadence.
 */
public class SparseIntMatrix {

    private final Map<Integer, Map<Integer, Integer>> rows = new HashMap<>();

    /** counts[i][j] += 1 */
    public void increment(int i, int j) {
        rows.computeIfAbsent(i, k -> new HashMap<>()).merge(j, 1, Integer::sum);
    }

    public int get(int i, int j) {
        Map<Integer, Integer> r = rows.get(i);
        return (r == null) ? 0 : r.getOrDefault(j, 0);
    }

    /** Drop all entries (used for the resettable per-window repost matrix). */
    public void clear() {
        rows.clear();
    }

    /** Realized rows: each entry is source i -> {target j : count}. Iterate for O(edges) work. */
    public Set<Map.Entry<Integer, Map<Integer, Integer>>> rowEntries() {
        return rows.entrySet();
    }

    /** Dense snapshot for gephi export only (export cadence, not per step). */
    public int[][] toDense(int n) {
        int[][] dense = new int[n][n];
        for (Map.Entry<Integer, Map<Integer, Integer>> row : rows.entrySet()) {
            int i = row.getKey();
            if (i < 0 || i >= n) continue;
            for (Map.Entry<Integer, Integer> col : row.getValue().entrySet()) {
                int j = col.getKey();
                if (j >= 0 && j < n) dense[i][j] = col.getValue();
            }
        }
        return dense;
    }
}
