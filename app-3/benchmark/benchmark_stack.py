from aws_cdk import Stack
from aws_cdk import aws_ssm as ssm
from constructs import Construct


class BenchmarkStack(Stack):
    """A stack containing a configurable number of resources.

    SSM String parameters are used as the benchmark resource because they are
    self-contained (no IAM, VPC, or cross-resource dependencies), which keeps
    synthesis fast and the generated template easy to reason about.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        index: int,
        resource_count: int,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        for n in range(resource_count):
            ssm.StringParameter(
                self,
                f"Param{n:04d}",
                parameter_name=f"/benchmark/stack-{index:03d}/param-{n:04d}",
                string_value=f"stack-{index:03d}-value-{n:04d}",
            )
