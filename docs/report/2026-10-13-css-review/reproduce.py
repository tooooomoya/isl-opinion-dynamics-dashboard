"""Compile the current source in a temporary directory and run review diagnostics.

This reports current behavior; ReviewProbe deliberately demonstrates bugs rather
than asserting a corrected implementation. Does not run or overwrite simulations.
"""
from pathlib import Path
import os
import subprocess
import tempfile


def main():
    root = Path(__file__).resolve().parents[3]
    artifact = Path(__file__).resolve().parent
    jars = sorted(root.glob("lib/**/*.jar"))
    sources = sorted(root.glob("src/**/*.java"))
    with tempfile.TemporaryDirectory(prefix="css-model-review-") as temp:
        classes = Path(temp) / "bin"
        cp = os.pathsep.join(str(p) for p in jars)
        subprocess.run(
            ["javac", "-cp", cp, "-d", str(classes), *map(str, sources)],
            check=True, cwd=root,
        )
        cp = cp + os.pathsep + str(classes)
        subprocess.run(["java", "-cp", cp, "test.ModelTests"], check=True, cwd=root)
        subprocess.run(
            ["javac", "-cp", cp, "-d", str(classes), str(artifact / "ReviewProbe.java")],
            check=True, cwd=root,
        )
        subprocess.run(["java", "-cp", cp, "ReviewProbe"], check=True, cwd=root)


if __name__ == "__main__":
    main()
