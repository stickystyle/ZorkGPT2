#!/usr/bin/env python3
"""CDK app for ZorkBurr viewer infrastructure."""
import aws_cdk as cdk

from zorkburr_viewer_stack import ZorkBurrViewerStack

app = cdk.App()

# Stack must be in us-east-1 for CloudFront + ACM certificate
ZorkBurrViewerStack(
    app,
    "ZorkBurrViewerStack",
    env=cdk.Environment(region="us-east-1"),
)

app.synth()
