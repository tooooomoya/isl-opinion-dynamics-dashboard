package analysis;

import agent.Agent;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.Arrays;

/** Exact non-overlapping windows, independent of sampled display metrics. No RNG calls. */
public final class CalibrationLog {
    private final long[][] counts;
    private final SparseIntMatrix root = new SparseIntMatrix();
    private final SparseIntMatrix immediate = new SparseIntMatrix();
    private int start = 0;

    public CalibrationLog(int n) { counts = new long[n][3]; }
    public void visit(int id) { counts[id][2]++; }
    public void original(int id) { counts[id][0]++; }
    public void reshare(int actor, int source, int rootAuthor) {
        counts[actor][1]++;
        immediate.increment(source, actor);
        root.increment(rootAuthor, actor);
    }

    public void flush(int step, Agent[] agents, Path directory) throws IOException {
        Path f = directory.resolve("calibration_activity.csv");
        StringBuilder b = new StringBuilder();
        if (!Files.exists(f)) b.append("start,step,agentId,intrinsicOpinion,opinion,nPost,nReshare,nVisits\n");
        for (Agent a : agents) {
            int id = a.getId();
            b.append(start).append(',').append(step).append(',').append(id).append(',')
             .append(a.getIntrinsicOpinion()).append(',').append(a.getOpinion());
            for (long c : counts[id]) b.append(',').append(c);
            b.append('\n');
        }
        Files.writeString(f, b.toString(), StandardOpenOption.CREATE, StandardOpenOption.APPEND);
        writeGraph(root, directory.resolve("calibration_root_" + step + ".csv"));
        writeGraph(immediate, directory.resolve("calibration_immediate_" + step + ".csv"));
        for (long[] c : counts) Arrays.fill(c, 0);
        root.clear(); immediate.clear(); start = step;
    }

    private static void writeGraph(SparseIntMatrix net, Path path) throws IOException {
        StringBuilder b = new StringBuilder("source,actor,count\n");
        for (var row : net.rowEntries()) for (var e : row.getValue().entrySet())
            b.append(row.getKey()).append(',').append(e.getKey()).append(',').append(e.getValue()).append('\n');
        Files.writeString(path, b.toString());
    }
}
