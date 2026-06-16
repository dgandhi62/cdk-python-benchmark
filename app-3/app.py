#!/usr/bin/env python3
import os

import aws_cdk as cdk

# Service imports typical of a large, enterprise-scale CDK app: a broad surface
# across compute, networking, data, analytics, security, CI/CD, and ML. Most are
# imported but never touched during synth -- the most pronounced version of the
# real-world pattern where lazy submodule loading avoids paying for code that is
# never exercised.
from aws_cdk import (
    aws_apigateway as apigateway,
    aws_appsync as appsync,
    aws_athena as athena,
    aws_autoscaling as autoscaling,
    aws_backup as backup,
    aws_batch as batch,
    aws_certificatemanager as acm,
    aws_cloudfront as cloudfront,
    aws_cloudtrail as cloudtrail,
    aws_cloudwatch as cloudwatch,
    aws_codebuild as codebuild,
    aws_codedeploy as codedeploy,
    aws_codepipeline as codepipeline,
    aws_cognito as cognito,
    aws_config as config,
    aws_dynamodb as dynamodb,
    aws_ec2 as ec2,
    aws_ecr as ecr,
    aws_ecs as ecs,
    aws_efs as efs,
    aws_eks as eks,
    aws_elasticache as elasticache,
    aws_elasticloadbalancingv2 as elbv2,
    aws_emr as emr,
    aws_events as events,
    aws_glue as glue,
    aws_iam as iam,
    aws_kinesis as kinesis,
    aws_kinesisfirehose as firehose,
    aws_kms as kms,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_opensearchservice as opensearch,
    aws_rds as rds,
    aws_route53 as route53,
    aws_s3 as s3,
    aws_sagemaker as sagemaker,
    aws_secretsmanager as secretsmanager,
    aws_sns as sns,
    aws_sqs as sqs,
    aws_ssm as ssm,
    aws_stepfunctions as stepfunctions,
    aws_wafv2 as wafv2,
)

from benchmark.benchmark_stack import BenchmarkStack

# Tunable benchmark parameters (override via environment variables).
NUM_STACKS = int(os.environ.get("NUM_STACKS", "400"))
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
