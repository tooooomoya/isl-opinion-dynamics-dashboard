package writer;

import java.util.Collection;
import java.util.LinkedHashMap;

/**
 * R21 (docs/report/2026-07-07-model-revision-requirements.md): a single per-step metrics row.
 *
 * Replaces the old five-edit pipeline (Const.RESULT_LIST string + Writer field + setter +
 * appendSingleMetric switch case + exportStepMetrics call). Adding a metric is now one
 * {@code row.put("name", value)}; binned metrics loop {@code row.put("cRateMean_" + i, v)}.
 *
 * Insertion order defines column order. Integer-valued metrics keep integer formatting;
 * everything else is formatted by {@link Writer} as a fixed-precision double. A mismatched key
 * set between rows is a hard error in {@link Writer#write()} (fail fast, not a silent empty cell,
 * which was the legacy failure mode on a typo'd key).
 */
public class MetricsRow {

    private final LinkedHashMap<String, Number> map = new LinkedHashMap<>();

    /** Insert or overwrite a metric; returns this for chaining. */
    public MetricsRow put(String key, Number value) {
        map.put(key, value);
        return this;
    }

    public Collection<String> keys() {
        return map.keySet();
    }

    public Collection<Number> values() {
        return map.values();
    }

    /** Comma-joined key list (no leading "step"). */
    public String headerCsv() {
        return String.join(",", map.keySet());
    }
}
