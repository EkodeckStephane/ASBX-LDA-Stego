"""Figure generator for SPE/LDA_Stego_ASBX article.

Produces:
  Figure_1_pipeline.pdf  — Encode/decode pipeline diagram (PGF/TikZ source)
  Figure_2_capacity.pdf  — Capacity gain factor vs ASBX ratio scatter+bar
  Figure_3_density.pdf   — Gain vs Hamming density for synthetic payloads

Requires: matplotlib, numpy (no LaTex renderer needed).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

_HERE = Path(__file__).resolve().parent
_RESULTS = _HERE.parent / "results"
_FIGURES = _HERE.parent / "LDA_Stego_ASBX" / "figures"
_FIGURES.mkdir(parents=True, exist_ok=True)

STYLE = {
    "sparse_matrix": {"color": "#1f77b4", "marker": "o", "label": "Sparse matrix"},
    "image_tensor": {"color": "#ff7f0e", "marker": "s", "label": "Image tensor (KMNIST)"},
    "canterbury": {"color": "#2ca02c", "marker": "^", "label": "Canterbury (text)"},
    "silesia": {"color": "#d62728", "marker": "D", "label": "Silesia (text)"},
    "synthetic": {"color": "#9467bd", "marker": "x", "label": "Synthetic"},
}


# ---------------------------------------------------------------------------
# Load results
# ---------------------------------------------------------------------------

def load_results() -> list[dict]:
    path = _RESULTS / "capacity_results.json"
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Figure 1: TikZ pipeline source (written to figures/)
# ---------------------------------------------------------------------------

PIPELINE_TIKZ = r"""\documentclass{standalone}
\usepackage{tikz}
\usetikzlibrary{arrows.meta, positioning, shapes.geometric, fit, backgrounds}

\begin{document}
\begin{tikzpicture}[
  node distance=0.6cm and 1.2cm,
  box/.style={draw, rounded corners=3pt, minimum height=0.9cm,
              minimum width=2.2cm, align=center, font=\small},
  arrow/.style={-{Stealth[length=4pt]}, thick},
  label/.style={font=\scriptsize, above, text=gray}
]

%% ---- Sender side ----
\node[box, fill=blue!15] (S)   {Secret\\\texttt{bytes}};
\node[box, fill=blue!25, right=of S] (A)  {ASBX\\compress};
\node[box, fill=blue!25, right=of A] (B)  {Bit\\chunking\\(k bits)};
\node[box, fill=blue!25, right=of B] (C)  {Topic\\indices\\$z_1,\ldots,z_N$};
\node[box, fill=blue!35, right=of C] (D)  {LDA word\\selection};
\node[box, fill=green!20, right=of D] (T)  {Stego-text};

\draw[arrow] (S) -- node[label]{$|S|$ B} (A);
\draw[arrow] (A) -- node[label]{$R|S|$ B} (B);
\draw[arrow] (B) -- node[label]{$N$ chunks} (C);
\draw[arrow] (C) -- (D);
\draw[arrow] (D) -- node[label]{$N$ words} (T);

%% ---- Receiver side ----
\node[box, fill=orange!15, below=1.8cm of S]  (RS)  {Recovered\\secret};
\node[box, fill=orange!25, right=of RS] (RA) {ASBX\\decompress};
\node[box, fill=orange!25, right=of RA] (RB) {Bit\\recon.};
\node[box, fill=orange!25, right=of RB] (RC) {Topic\\indices\\$\hat{z}_1,\ldots,\hat{z}_N$};
\node[box, fill=orange!25, right=of RC] (RD) {LDA\\inference\\$\arg\max_t \beta_{t,w}$};
\node[box, fill=green!20, right=of RD] (RT) {Stego-text};

\draw[arrow] (RT) -- (RD);
\draw[arrow] (RD) -- (RC);
\draw[arrow] (RC) -- (RB);
\draw[arrow] (RB) -- (RA);
\draw[arrow] (RA) -- (RS);

%% side-channel annotation
\draw[dashed, gray] (A.south) -- ++(0,-0.4) node[right, font=\tiny, gray]
  {compressed\_length (side-channel)} -- (RA.north);

%% labels
\node[font=\small\bfseries, above=0.1cm of S] {Sender};
\node[font=\small\bfseries, above=0.1cm of RS] {Receiver};

\end{tikzpicture}
\end{document}
"""

def write_pipeline_tikz() -> Path:
    out = _FIGURES / "Figure_1_pipeline.tex"
    out.write_text(PIPELINE_TIKZ, encoding="utf-8")
    print(f"  Written: {out}")
    return out


# ---------------------------------------------------------------------------
# Figure 2: Capacity gain vs ASBX ratio (scatter)
# ---------------------------------------------------------------------------

def fig_capacity_scatter(rows: list[dict]) -> None:
    fig, ax = plt.subplots(figsize=(7, 4.5))

    for row in rows:
        label_raw = row["label"].split("/")[0]
        # collapse synthetic sub-labels
        corpus = "synthetic" if label_raw.startswith("synthetic") else label_raw
        style = STYLE.get(corpus, {"color": "gray", "marker": ".", "label": corpus})
        ax.scatter(
            row["asbx_ratio"],
            row["capacity_gain_factor"],
            color=style["color"],
            marker=style["marker"],
            s=60,
            alpha=0.8,
        )

    # Reference line: gain = 1/ratio
    ratios = np.linspace(0.01, 1.1, 300)
    ax.plot(ratios, 1.0 / ratios, "k--", lw=0.8, label="Theoretical $1/R$")
    ax.axhline(1.0, color="gray", lw=0.6, ls=":")
    ax.axvline(1.0, color="gray", lw=0.6, ls=":")

    # Legend
    handles = [
        mpatches.Patch(color=v["color"], label=v["label"])
        for v in STYLE.values()
    ]
    handles.append(plt.Line2D([0], [0], color="black", ls="--", lw=0.8, label="Theoretical $1/R$"))
    ax.legend(handles=handles, fontsize=8, loc="upper right")

    ax.set_xlabel("ASBX compression ratio $R$ (lower = more compressed)", fontsize=10)
    ax.set_ylabel("Embedding capacity gain factor $1/R$", fontsize=10)
    ax.set_title("Capacity gain as a function of ASBX ratio\n(all round-trips verified exact)", fontsize=10)
    ax.set_xlim(0, 1.15)
    ax.set_ylim(0, max(r["capacity_gain_factor"] for r in rows) * 1.05)
    ax.grid(True, alpha=0.3)

    out = _FIGURES / "fig_stego_capacity.pdf"
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Written: {out}")


# ---------------------------------------------------------------------------
# Figure 3: Gain vs Hamming density for synthetic payloads
# ---------------------------------------------------------------------------

def fig_density_curve(rows: list[dict]) -> None:
    # Parse synthetic rows
    syn_rows = [r for r in rows if r["label"].startswith("synthetic_rho")]
    if not syn_rows:
        return

    # Group by size
    from collections import defaultdict
    by_size: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for r in syn_rows:
        parts = r["label"].split("_")
        rho_str = parts[1].replace("rho", "")
        size_str = parts[2].replace("size", "")
        rho = int(rho_str) / 100.0
        size = int(size_str)
        by_size[size].append((rho, r["capacity_gain_factor"]))

    fig, ax = plt.subplots(figsize=(6.5, 4))
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c"]
    for (size, points), color in zip(sorted(by_size.items()), colors):
        pts = sorted(points)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.plot(xs, ys, "o-", color=color, label=f"{size} bytes", lw=1.5, ms=5)

    ax.axhline(1.0, color="gray", lw=0.6, ls=":")
    ax.set_xlabel("Hamming density $\\rho$ (fraction of set bits)", fontsize=10)
    ax.set_ylabel("Capacity gain factor $1/R$", fontsize=10)
    ax.set_title("Capacity gain vs payload sparsity\n(synthetic payloads, T=64, k=6 bits/word)", fontsize=10)
    ax.legend(title="Payload size", fontsize=9)
    ax.set_xscale("log")
    ax.grid(True, alpha=0.3, which="both")

    out = _FIGURES / "fig_stego_density.pdf"
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Written: {out}")


# ---------------------------------------------------------------------------
# Figure 4: Bar chart — mean gain by corpus type
# ---------------------------------------------------------------------------

def fig_corpus_bars(rows: list[dict]) -> None:
    from collections import defaultdict

    by_corpus: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        corpus = row["label"].split("/")[0]
        if corpus.startswith("synthetic"):
            corpus = "synthetic"
        by_corpus[corpus].append(row["capacity_gain_factor"])

    labels_ordered = ["sparse_matrix", "image_tensor", "canterbury", "silesia", "synthetic"]
    display = {
        "sparse_matrix": "Sparse\nmatrix",
        "image_tensor": "Image\ntensor",
        "canterbury": "Canterbury\n(text)",
        "silesia": "Silesia\n(text)",
        "synthetic": "Synthetic\n(mixed)",
    }
    means = [np.mean(by_corpus.get(c, [1.0])) for c in labels_ordered]
    stds  = [np.std(by_corpus.get(c, [0.0])) for c in labels_ordered]
    colors = [STYLE[c]["color"] for c in labels_ordered]

    fig, ax = plt.subplots(figsize=(6, 4))
    x = np.arange(len(labels_ordered))
    bars = ax.bar(x, means, yerr=stds, capsize=4,
                  color=colors, edgecolor="white", linewidth=0.5, width=0.6)
    ax.axhline(1.0, color="gray", lw=0.8, ls="--", label="No gain (ratio=1)")
    ax.set_xticks(x)
    ax.set_xticklabels([display[c] for c in labels_ordered], fontsize=9)
    ax.set_ylabel("Mean capacity gain factor $1/R$", fontsize=10)
    ax.set_title("Embedding capacity gain by payload domain\n(T=64 topics, k=6 bits/word)", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, axis="y")
    for bar, mean in zip(bars, means):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                f"x{mean:.1f}", ha="center", va="bottom", fontsize=8)

    out = _FIGURES / "fig_stego_bars.pdf"
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Written: {out}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Loading results...")
    rows = load_results()
    print(f"  {len(rows)} rows loaded.")

    print("Writing pipeline TikZ source...")
    write_pipeline_tikz()

    print("Generating Figure 2 (capacity scatter)...")
    fig_capacity_scatter(rows)

    print("Generating Figure 3 (density curve)...")
    fig_density_curve(rows)

    print("Generating Figure 4 (corpus bars)...")
    fig_corpus_bars(rows)

    print("Done. All figures written to:", _FIGURES)
