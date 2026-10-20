package agent;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;

/**
 * Window diagnostics of the Q-learning (one simulation per JVM, so static accumulators are fine):
 *  - metrics/td_log.csv: per (state, action) and window: number of credited decisions, mean and variance of
 *    the immediate reward r = fit + recognition observed at the next visit, mean TD error, mean |TD error|, RMS.
 *  - metrics/choice_gap.csv: per window, decisions binned by the Q-gap of an offered action to the best offered
 *    action (gap = Q(s,a) - max Q(s,.) <= 0; bin width 0.01, last bin open): how often offered, how often chosen,
 *    and the sum of the policy's theoretical probability (so chosen/offered can be compared to the model's P).
 */
public final class LearningLog {
    public static final double BIN = 0.01;
    public static final int NB = 60;
    private static final int S = Agent.NUM_STATES, A = Agent.NUM_ACTIONS;
    private static long[][] n = new long[S][A];
    private static double[][] sumR = new double[S][A], sumR2 = new double[S][A];
    private static double[][] sumD = new double[S][A], sumD2 = new double[S][A], sumAbsD = new double[S][A];
    private static long[] offered = new long[NB], chosen = new long[NB];
    private static double[] sumP = new double[NB];

    private LearningLog() {}

    static void recordTd(int s, int a, double r, double delta) {
        n[s][a]++;
        sumR[s][a] += r; sumR2[s][a] += r * r;
        sumD[s][a] += delta; sumD2[s][a] += delta * delta; sumAbsD[s][a] += Math.abs(delta);
    }

    /** Delayed credit g of one POST/RESHARE decision: added to that (s,a)'s reward total (one credit per decision, so meanR = immediate + credited). */
    static void recordCredit(int s, int a, double g) {
        sumR[s][a] += g;
    }

    /** gap[a] = Q(s,a) - max over offered; p[a] = theoretical choice probability; only offered actions are counted. */
    static void recordChoice(boolean[] ok, double[] gap, double[] p, int pick) {
        int k = 0;
        for (int a = 0; a < A; a++) if (ok[a]) k++;
        if (k < 2) return; // a forced move (one available action) says nothing about choosing between actions
        for (int a = 0; a < A; a++) {
            if (!ok[a]) continue;
            int b = Math.min(NB - 1, (int) Math.floor(-gap[a] / BIN + 1e-9));
            offered[b]++;
            sumP[b] += p[a];
            if (a == pick) chosen[b]++;
        }
    }

    public static void flush(int step, Path dir) throws IOException {
        StringBuilder sb = new StringBuilder();
        Path td = dir.resolve("td_log.csv");
        if (!Files.exists(td)) sb.append("step,state,action,n,meanR,varR,meanDelta,meanAbsDelta,rmsDelta\n");
        for (int s = 0; s < S; s++) for (int a = 0; a < A; a++) {
            long c = n[s][a];
            if (c == 0) continue;
            double mr = sumR[s][a] / c;
            sb.append(step).append(',').append(s).append(',').append(Agent.ACTION_NAMES[a]).append(',').append(c)
              .append(',').append(String.format("%.5f,%.6f,%.6f,%.6f,%.6f", mr, Math.max(0.0, sumR2[s][a] / c - mr * mr),
                      sumD[s][a] / c, sumAbsD[s][a] / c, Math.sqrt(sumD2[s][a] / c))).append('\n');
        }
        Files.writeString(td, sb.toString(), StandardOpenOption.CREATE, StandardOpenOption.APPEND);
        StringBuilder cb = new StringBuilder();
        Path cg = dir.resolve("choice_gap.csv");
        if (!Files.exists(cg)) cb.append("step,gap_lo,offered,chosen,sumTheoryP\n");
        for (int b = 0; b < NB; b++) {
            if (offered[b] == 0) continue;
            cb.append(step).append(',').append(String.format("%.2f", -(b + 1) * BIN)).append(',').append(offered[b])
              .append(',').append(chosen[b]).append(',').append(String.format("%.4f", sumP[b])).append('\n');
        }
        Files.writeString(cg, cb.toString(), StandardOpenOption.CREATE, StandardOpenOption.APPEND);
        n = new long[S][A]; sumR = new double[S][A]; sumR2 = new double[S][A];
        sumD = new double[S][A]; sumD2 = new double[S][A]; sumAbsD = new double[S][A];
        offered = new long[NB]; chosen = new long[NB]; sumP = new double[NB];
    }
}
