#!/usr/bin/env python3
import os

import aws_cdk as cdk

# Service imports typical of a small CDK app. Most are imported but not all are
# exercised during synth -- mirroring real apps, which pull in a dependency tree
# far larger than the slice they actually use. This is the scenario lazy
# submodule loading is designed to benefit.
from aws_cdk import (
    aws_cloudwatch as cloudwatch,
    aws_dynamodb as dynamodb,
    aws_events as events,
    aws_iam as iam,
    aws_kms as kms,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_s3 as s3,
    aws_secretsmanager as secretsmanager,
    aws_sns as sns,
    aws_sqs as sqs,
)

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
