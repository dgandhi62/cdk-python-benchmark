#!/usr/bin/env python3
import os

import aws_cdk as cdk

from benchmark.benchmark_stack import BenchmarkStack

# Tunable benchmark parameters (override via environment variables).
NUM_STACKS = int(os.environ.get("NUM_STACKS", "20"))
RESOURCES_PER_STACK = int(os.environ.get("RESOURCES_PER_STACK", "400"))

# analytics_reporting=False removes the auto-injected AWS::CDK::Metadata
# resource so each stack contains exactly RESOURCES_PER_STACK resources and
# stays within CloudFormation's 500-resource-per-stack limit.
app = cdk.App(analytics_reporting=False)

for i in range(NUM_STACKS):
    BenchmarkStack(
        app,
        f"BenchmarkStack-{i:03d}",
        index=i,
        resource_count=RESOURCES_PER_STACK,
    )

app.synth()
