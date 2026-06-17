# cdk-python-benchmark

A benchmark harness for measuring AWS CDK (Python) synthesis performance at scale.
The repo holds several independent CDK apps that each synthesize a different volume
of infrastructure, letting you compare how synth time scales with the number of
stacks and resources.

Each app builds plain SSM `StringParameter` resources — chosen because they have no
IAM, VPC, or cross-resource dependencies — so measurements isolate CDK's own
synthesis cost rather than resource-specific overhead. Benchmarks are run with
[hyperfine](https://github.com/sharkdp/hyperfine) for statistically meaningful
timings (warmup runs, multiple samples, mean ± stddev).

## Apps

| App   | Stacks | Resources/stack | Total resources |
|-------|--------|-----------------|-----------------|
| app-1 | 20     | 400             | 8,000           |
| app-2 | 100    | 400             | 40,000          |
| app-3 | 400    | 400             | 160,000         |

Counts default to the values above. They can be overridden per run via the
`NUM_STACKS` and `RESOURCES_PER_STACK` environment variables, so any app can be
reconfigured without editing source.

Each app is self-contained with its own `.venv`, `app.py`, `benchmark/` package,
`cdk.json`, and `requirements.txt`.

## Prerequisites

- Python 3.9+
- Node.js (for the CDK CLI)
- A CDK CLI compatible with `aws-cdk-lib` 2.259.0 (**≥ 2.1127.0**). The apps install
  a matching CLI locally so `npx cdk` resolves to the correct version.
- [hyperfine](https://github.com/sharkdp/hyperfine) — `brew install hyperfine`

## Setup (per app)

Each app has its own virtual environment. From inside an app folder (e.g. `app-1`):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If you plan to benchmark `cdk synth` (rather than `python3 app.py`), install a
compatible CDK CLI locally so `npx cdk` does not fall back to an older global CLI:

```bash
npm install aws-cdk@latest
npx cdk --version   # confirm >= 2.1127.0
```

## Benchmarking

Two things can be measured. Pick based on what you care about:

- **`python3 app.py`** — pure CDK synthesis (Python execution, construct tree,
  template generation). Skips the CLI/npx layer and avoids CLI version issues.
  Recommended for isolating CDK's synthesis cost.
- **`npx cdk synth`** — full end-to-end synth including CLI startup and orchestration.
  More realistic of real-world `cdk synth` usage.

### Pure synthesis (recommended)

From inside an app folder, with its venv activated:

```bash
hyperfine \
  --warmup 1 \
  --runs 5 \
  --prepare 'rm -rf cdk.out' \
  'python3 app.py'
```

### Full end-to-end synth

```bash
hyperfine \
  --warmup 1 \
  --runs 5 \
  --prepare 'rm -rf cdk.out' \
  'npx cdk synth > /dev/null'
```

### Flag reference

| Flag | Purpose |
|------|---------|
| `--warmup 1` | Run once before measuring to warm OS/file caches. |
| `--runs 5` | Take 5 measured samples; report mean ± stddev, min, max. |
| `--prepare 'rm -rf cdk.out'` | Clear output before each run so every run does full work. |
| `--show-output` | Print the command's output (use to debug a failing run). |
| `-i` / `--ignore-failure` | Continue even if a run exits non-zero. |

### Varying the workload

Use hyperfine's parameter scan to benchmark across sizes without editing files:

```bash
hyperfine \
  --warmup 1 \
  --runs 3 \
  --parameter-list n 10,50,100 \
  --prepare 'rm -rf cdk.out' \
  'NUM_STACKS={n} python3 app.py'
```

### Import baseline (isolating import cost)

The apps import many `aws_cdk.aws_*` service modules but exercise only a few
during synth — mirroring real apps that pull in a large dependency tree but use a
slice of it. This is the scenario lazy submodule loading is designed to benefit.

Import cost is a **one-time startup cost**: it does not scale with stack or
resource count, so it looks roughly constant across app-1/app-2/app-3. To measure
it on its own, shrink the workload to near zero so synthesis time drops out:

```bash
# Near-zero workload: isolates import + interpreter startup
hyperfine \
  --warmup 1 \
  --runs 5 \
  --prepare 'rm -rf cdk.out' \
  'NUM_STACKS=1 RESOURCES_PER_STACK=1 python3 app.py'
```

For a per-module breakdown of where import time goes:

```bash
python3 -X importtime app.py 2> importtime.log
sort -t'|' -k2 -n -r importtime.log | head -30   # slowest imports first
```

Run the import baseline under different jsii runtime versions (pre-lazy vs. lazy)
to attribute the startup delta to import behavior, separately from the
per-resource synthesis cost measured by the full-workload benchmarks above.

## Comparing apps

### Generate lazy-loading version (source only)
```bash
node ~/jsii/packages/jsii-pacmak/bin/jsii-pacmak \
  ~/aws-cdk/packages/aws-cdk-lib --code-only --no-fingerprint --target python
```

### Install into your project
```bash
cd ~/cdk-python-project
source .venv/bin/activate
# 2. Swap aws-cdk-lib to your local lazy bindings (deps already satisfied)
pip install --no-deps --force-reinstall ~/aws-cdk/packages/aws-cdk-lib/dist/python/

# 3. Swap jsii to your local branch runtime (provides _memoized etc.)
pip install --no-deps --force-reinstall /Users/gandhya/jsii/packages/@jsii/python-runtime
```

Run each app's benchmark from its own folder, then compare the reported means. To
export results for later analysis, add `--export-markdown` or `--export-json`:

```bash
hyperfine --warmup 1 --runs 5 --prepare 'rm -rf cdk.out' \
  --export-markdown results.md \
  'python3 app.py'
```

## Notes

- app-3 synthesizes 160,000 resources; its runs are significantly slower. Drop
  `--runs` to 3 (or fewer) if a full benchmark takes too long.
- Each stack holds exactly 400 resources. CloudFormation caps stacks at 500
  resources, and `app.py` sets `analytics_reporting=False` to drop the
  auto-injected `AWS::CDK::Metadata` resource so counts stay exact.
- These apps only synthesize templates locally into `cdk.out/`. They do not deploy
  or call AWS, so no AWS credentials are required for benchmarking.
