# Scripts

The scripts prepare corpora, run codec campaigns, summarize CSV results, and
regenerate manuscript tables and figures.

For code-only reproducibility and native checks:

```powershell
python experiments\scripts\generate_synthetic_corpus.py
python experiments\scripts\generate_large_corpus.py
python experiments\scripts\run_large_native_benchmark.py
```

`generate_large_corpus.py` creates deterministic 1-2 MiB payloads under an
ignored directory. `run_large_native_benchmark.py` measures the native C CLI on
those payloads and writes `experiments/results/native_large_benchmark.csv`.

For the confirmation artifacts:

```powershell
pdflatex -output-directory=paper\figures paper\figures\Figure_1.tex
pdflatex -output-directory=paper\figures paper\figures\Figure_2.tex
python experiments\scripts\evaluate_confirmation_domains.py
python experiments\scripts\generate_manuscript_tables.py
python experiments\scripts\generate_manuscript_figures.py
```

Figures 1 and 2 are editable TikZ sources. Figures 3 and 4 are regenerated
from the confirmation CSV as separate PDF and PNG files.

`add_confirmation_baselines.py` is a shorter incremental command. It preserves
existing ASBX confirmation rows and recomputes only the lossless global
position-gap and PNG baselines, including decode-after-encode verification.
