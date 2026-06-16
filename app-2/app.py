#!/usr/bin/env python3
import os

import aws_cdk as cdk

# Service imports typical of a medium CDK app spanning compute, networking,
# data, and integration services. Imported broadly but only partially used
# during synth -- the realistic shape of a growing application, and the case
# where deferring eager submodule imports pays off most.
from aws_cdk import (
    aws_apigateway as apigateway,
    aws_autoscaling as autoscaling,
    aws_certificatemanager as acm,
    aws_cloudwatch as cloudwatch,
    aws_dynamodb as dynamodb,
    aws_ec2 as ec2,
    aws_ecr as ecr,
    aws_ecs as ecs,
    aws_efs as efs,
    aws_elasticloadbalancingv2 as elbv2,
    aws_events as events,
    aws_iam as iam,
    aws_kinesis as kinesis,
    aws_kms as kms,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_rds as rds,
    aws_route53 as route53,
    aws_s3 as s3,
    aws_secretsmanager as secretsmanager,
    aws_sns as sns,
    aws_sqs as sqs,
)

from benchmark.benchmark_stack import BenchmarkStack

# Tunable benchmark parameters (override via environment variables).
NUM_STACKS = int(os.environ.get("NUM_STACKS", "100"))
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
