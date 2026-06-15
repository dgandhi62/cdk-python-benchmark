# cdk-python-benchmark

A CDK (Python) benchmark app that synthesizes **100 stacks** with **500 resources each**
(50,000 resources total). Each resource is an SSM `StringParameter`, chosen because it
is self-contained with no cross-resource dependencies, keeping synthesis fast and
predictable.

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

Defaults: `NUM_STACKS=100`, `RESOURCES_PER_STACK=500`.
