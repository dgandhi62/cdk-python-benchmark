# cdk-python-benchmark — app-2

A CDK (Python) benchmark app that synthesizes **100 stacks** with **400 resources
each** (40,000 resources total). Each resource is an SSM `StringParameter`, chosen
because it is self-contained with no cross-resource dependencies, keeping
synthesis fast and predictable.

## Layout

```
.
├── app.py                       # CDK entry point; instantiates the stacks
├── benchmark/
│   └── benchmark_stack.py       # Stack definition with N resources
├── cdk.json                     # CDK app configuration
└── requirements.txt             # Python dependencies
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
# Synthesize all stacks
cdk synth

# List the generated stacks
cdk list
```

## Tuning

The stack and resource counts are configurable via environment variables:

```bash
NUM_STACKS=10 RESOURCES_PER_STACK=50 cdk synth
```

Defaults: `NUM_STACKS=100`, `RESOURCES_PER_STACK=400`.

## Import baseline (isolating import cost)

This app imports many `aws_cdk.aws_*` service modules but only exercises a few
during synth. With lazy submodule loading, unused imports are never actually
loaded, so the import win is a one-time startup cost that does **not** scale with
stack or resource count. To measure it on its own, shrink the workload to near
zero so synthesis time drops out and only import/startup remains:

```bash
# Near-zero workload: isolates import + interpreter startup
hyperfine \
  --warmup 1 \
  --runs 5 \
  --prepare 'rm -rf cdk.out' \
  'NUM_STACKS=1 RESOURCES_PER_STACK=1 python3 app.py'
```

For a direct breakdown of where import time goes (per-module cumulative cost),
use Python's built-in import profiler:

```bash
python3 -X importtime app.py 2> importtime.log
sort -t'|' -k2 -n -r importtime.log | head -30   # slowest imports first
```

Compare the import baseline across jsii runtime versions (e.g. pre-lazy vs.
lazy) to see the startup improvement independently of per-resource synth cost.
