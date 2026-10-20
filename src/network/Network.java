package network;

import agent.Agent;

public abstract class Network {
    double[][] adjacencyMatrix;
    private int size;

    // Constructor
    public Network(int size) {
        this.size = size;
        this.adjacencyMatrix = new double[size][size];
    }

    // getter methods

    public double[][] getAdjacencyMatrix() {
        double[][] copy = new double[size][size];
        for (int i = 0; i < size; i++) {
            System.arraycopy(this.adjacencyMatrix[i], 0, copy[i], 0, size);
        }
        return copy;
    }

    public double getEdge(int from, int to) {
        return this.adjacencyMatrix[from][to];
    }

    // protected getter
    protected int getSize() {
        return this.size;
    }

    // setter methods

    /** Set an unweighted follow edge i -> j (weight 1.0). */
    public void setEdge(int i, int j) {
        if (i >= 0 && i < size && j >= 0 && j < size) {
            adjacencyMatrix[i][j] = 1.0;
        }
    }

    // R24: honest weighted setter — previously this ignored `weight` and always wrote 1.0,
    // silently corrupting CustomNetwork's row-normalized weights. Now it writes `weight`.
    // (Unweighted generators call setEdge(i,j) or setEdge(i,j,1.0), both give weight 1.0.)
    public void setEdge(int i, int j, double weight) {
        if (i >= 0 && i < size && j >= 0 && j < size) {
            adjacencyMatrix[i][j] = weight;
        }
    }

    public void setAdjacencyMatrix(double[][] newMatrix) {
        if (newMatrix.length != size || newMatrix[0].length != size) {
            throw new IllegalArgumentException("Adjacency matrix must be of size " + size + "x" + size);
        }
        for (int i = 0; i < size; i++) {
            System.arraycopy(newMatrix[i], 0, this.adjacencyMatrix[i], 0, size);
        }
    }

    // user i unfollow user j (user i temporarily does not see any posts from user
    // j)
    public void removeEdge(int i, int j) {
        if (i >= 0 && i < size && j >= 0 && j < size) {
            adjacencyMatrix[i][j] = 0;
        }
    }

    public double[] getNeighbors(int node) {
        if (node >= 0 && node < size) {
            return adjacencyMatrix[node].clone();
        }
        return new double[0];
    }

    // abstract methods

    /** Number of directed edges (i -> j, i != j). */
    public int countEdges() {
        int m = 0;
        for (int i = 0; i < size; i++) for (int j = 0; j < size; j++) if (i != j && adjacencyMatrix[i][j] != 0.0) m++;
        return m;
    }

    /**
     * Make the number of directed edges exactly {@code target} (mean in-degree = mean out-degree = target / size): surplus edges are
     * removed uniformly at random, missing ones are added between uniformly random non-adjacent pairs. Used to give start networks of
     * different families the same mean degree.
     */
    public void enforceEdgeCount(int target, java.util.Random rng) {
        int m = countEdges();
        while (m > target) {
            int i = rng.nextInt(size), j = rng.nextInt(size);
            if (i != j && adjacencyMatrix[i][j] != 0.0) { adjacencyMatrix[i][j] = 0.0; m--; }
        }
        while (m < target) {
            int i = rng.nextInt(size), j = rng.nextInt(size);
            if (i != j && adjacencyMatrix[i][j] == 0.0) { adjacencyMatrix[i][j] = 1.0; m++; }
        }
    }

    public abstract void makeNetwork(Agent[] agentSet);

}