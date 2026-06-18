# Profiling harness

Decomposes CDK-python synth time to attribute the lazy-import / `check_type`
savings to specific causes (imports vs `get_type_hints` vs `check_type` vs kernel
IPC), and explains why the percentage savings vary across app-1/2/3.

## Files

- `profile_app.py` — profiles ONE app in a fresh process, writes a JSON result.
- `aggregate.py` — merges per-app JSON results into one comparison table (+ CSV).
- `results/` — drop the per-app JSON files here.

## What it measures

| Phase | What | Scales with |
|-------|------|-------------|
| Build detection | lazy vs eager `aws_cdk`; cached vs per-call `check_type` | — |
| Import cost | `aws_cdk` core + each `aws_*` service module the app imports | one-time (module count) |
| Synth attribution | `get_type_hints`, `check_type`, `register_*`, `proxy_for`, `import_module`, kernel IPC | per-resource |
| Call counts | how often each per-resource hot-spot fires | resource count |

Output is a single JSON object per app so results accumulate cleanly.

> Important: run each app with **its own venv python** so the installed
> `aws_cdk`/`jsii` is the one measured. The script auto-detects whether that
> build is lazy or eager.

## Run all three apps in parallel

The profiler is CPU- and IPC-bound and each app spawns its own jsii kernel, so
running the three concurrently is safe and faster. From the repo root:

```bash
BENCH="$PWD"
PROF="$BENCH/profiling"
mkdir -p "$PROF/results"

for app in app-1 app-2 app-3; do
  "$BENCH/$app/.venv/bin/python" "$PROF/profile_app.py" \
      "$BENCH/$app" \
      --stacks 5 --resources 400 \
      --out "$PROF/results/$app.json" &
done
wait   # block until all three finish
```

Each backgrounded run prints a one-line progress summary to stderr as it
finishes. `wait` blocks until all are done.

### Alternative: GNU parallel

```bash
parallel --jobs 3 \
  '{}/.venv/bin/python profiling/profile_app.py {} --stacks 5 --resources 400 --out profiling/results/$(basename {}).json' \
  ::: app-1 app-2 app-3
```

## Accumulate and compare

```bash
"$BENCH/app-1/.venv/bin/python" "$PROF/aggregate.py" \
    "$PROF/results/*.json" \
    --csv "$PROF/summary.csv"
```

Produces an aligned table plus a per-resource normalization (µs/resource), which
is the number that explains the variance: the savings are roughly linear in
resource count, so apps with more resources show larger absolute savings even
though the per-resource cost is similar.

## Tips

- Keep `--stacks` small (e.g. 5). The per-resource costs are linear, so a small
  workload profiles fast and still attributes the costs correctly. Use larger
  values only to confirm linearity.
- To A/B the lazy vs eager build, install the respective wheel into an app's
  venv, re-run the profiler, and diff the JSON. The `build` / `check_type` fields
  record which version was measured.
- `cProfile` adds overhead, so `synth.wall_ms` here is higher than a clean
  `hyperfine` run. Use it for *attribution* (relative breakdown), and use
  `hyperfine` (see the top-level README) for headline wall-clock numbers.
```
