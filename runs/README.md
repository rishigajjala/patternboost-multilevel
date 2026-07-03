# runs/

This directory is intentionally ignored by git except for this README.

Use it for local and HPC outputs:

```bash
scripts/make_main_matrix.sh
PYTHONPATH=src python -m multilevel.cli smoke --out runs/smoke
```

Do not commit raw run directories. Preserve important final certificates or
figures by copying them into a documented location under `docs/`.

