# Aurora exercises (ALCF)

The same eight examples as [`../local`](../local/README.md), set up to run on
**Aurora**. Each folder adds a `submit.pbs`; all of them (including 07) source the
shared `env.sh` here (ALCF `frameworks` module, the single `flowcept-academy` conda
env, an **offline** local CPU LLM, and Flowcept's offline settings).

## One-time setup (on a login node)

```bash
bash setup/install.sh                 # builds the `flowcept-academy` conda env
source exercises/aurora/env.sh        # modules + conda env + offline LLM + settings
# pre-cache the local LLM while you still have internet (login nodes have it):
python -c "from flowcept_academy.util import chat; print(chat('hi'))"
```

`env.sh` sets `HF_HOME=$REPO/hf_cache` and `HF_HUB_OFFLINE=1`, so once the model
is cached the compute nodes read it offline — no Argo, no network.

## Run an example

Batch (edit `-A <project>` in `submit.pbs` first):

```bash
cd exercises/aurora/01-actor-client
qsub submit.pbs                       # runs solution.py on a compute node
```

Each run writes to its own `runs/<id>_<date-time>/` in the example folder
(`flowcept_buffer.jsonl`, perf CSV, `<id>_card.md`). Interactive: grab a node
(`qsub -I -A <project> -q debug -l select=1 -l walltime=00:30:00 -l
filesystems=home:flare`), `source ../env.sh`, then work through `python
exercise.py` step by step.

## Then query it

```bash
python ../../../provenance/query.py runs/<id>_* --ask "how many tasks are there?"
```

The examples that call an LLM (06–08) use the offline local model on compute
nodes. Examples 05 and 07 need the `parsl` / `langgraph` extras, already
installed by `setup/install.sh`. See the [exercises overview](../README.md).
