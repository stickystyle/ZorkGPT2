#!/usr/bin/env python3
"""CDK stack for ZorkBurr viewer: S3 + CloudFront + optional Route53/ACM.

Usage:
    # Without custom domain (uses d*.cloudfront.net URL):
    cdk deploy

    # With custom domain:
    cdk deploy -c domain_name=zorkburr.com
"""
import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_route53 as route53,
    aws_route53_targets as targets,
    aws_certificatemanager as acm,
    Duration,
    RemovalPolicy,
    CfnOutput,
)
from constructs import Construct


class ZorkBurrViewerStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        domain_name = self.node.try_get_context("domain_name")

        # --- S3 Bucket ---
        self.bucket = s3.Bucket(
            self,
            "ViewerBucket",
            public_read_access=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            cors=[
                s3.CorsRule(
                    allowed_methods=[s3.HttpMethods.GET, s3.HttpMethods.HEAD],
                    allowed_origins=["*"],
                    allowed_headers=["*"],
                    max_age=3600,
                )
            ],
        )

        # --- Origin Access Identity ---
        oai = cloudfront.OriginAccessIdentity(
            self, "ViewerOAI", comment="OAI for ZorkBurr Viewer",
        )
        self.bucket.grant_read(oai)

        s3_origin = origins.S3BucketOrigin.with_origin_access_identity(
            bucket=self.bucket, origin_access_identity=oai,
        )

        # --- Cache Policies ---

        # Live state: 5-second cache for near-real-time
        live_cache = cloudfront.CachePolicy(
            self,
            "LiveCachePolicy",
            cache_policy_name=f"ZorkBurr-Live-{self.stack_name}",
            default_ttl=Duration.seconds(5),
            max_ttl=Duration.seconds(10),
            min_ttl=Duration.seconds(0),
            cookie_behavior=cloudfront.CacheCookieBehavior.none(),
            header_behavior=cloudfront.CacheHeaderBehavior.none(),
            query_string_behavior=cloudfront.CacheQueryStringBehavior.none(),
            enable_accept_encoding_gzip=True,
            enable_accept_encoding_brotli=True,
        )

        # Turn snapshots: immutable, cache for 1 year
        immutable_cache = cloudfront.CachePolicy(
            self,
            "ImmutableCachePolicy",
            cache_policy_name=f"ZorkBurr-Immutable-{self.stack_name}",
            default_ttl=Duration.days(365),
            max_ttl=Duration.days(365),
            min_ttl=Duration.days(365),
            cookie_behavior=cloudfront.CacheCookieBehavior.none(),
            header_behavior=cloudfront.CacheHeaderBehavior.none(),
            query_string_behavior=cloudfront.CacheQueryStringBehavior.none(),
            enable_accept_encoding_gzip=True,
            enable_accept_encoding_brotli=True,
        )

        # Default: 5-minute cache for HTML, index.json, meta.json
        default_cache = cloudfront.CachePolicy(
            self,
            "DefaultCachePolicy",
            cache_policy_name=f"ZorkBurr-Default-{self.stack_name}",
            default_ttl=Duration.minutes(5),
            max_ttl=Duration.hours(1),
            min_ttl=Duration.seconds(0),
            cookie_behavior=cloudfront.CacheCookieBehavior.none(),
            header_behavior=cloudfront.CacheHeaderBehavior.none(),
            query_string_behavior=cloudfront.CacheQueryStringBehavior.all(),
            enable_accept_encoding_gzip=True,
            enable_accept_encoding_brotli=True,
        )

        # --- Optional Route53 + ACM ---
        certificate = None
        domain_names = None
        if domain_name:
            hosted_zone = route53.HostedZone(
                self, "HostedZone", zone_name=domain_name,
            )
            certificate = acm.Certificate(
                self,
                "Certificate",
                domain_name=domain_name,
                subject_alternative_names=[f"www.{domain_name}"],
                validation=acm.CertificateValidation.from_dns(hosted_zone),
            )
            domain_names = [domain_name, f"www.{domain_name}"]

        # --- CloudFront Distribution ---
        self.distribution = cloudfront.Distribution(
            self,
            "ViewerDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=s3_origin,
                cache_policy=default_cache,
                origin_request_policy=cloudfront.OriginRequestPolicy.CORS_S3_ORIGIN,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD,
            ),
            additional_behaviors={
                "/live/current_state.json": cloudfront.BehaviorOptions(
                    origin=s3_origin,
                    cache_policy=live_cache,
                    origin_request_policy=cloudfront.OriginRequestPolicy.CORS_S3_ORIGIN,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD,
                ),
                "/episodes/*/turns/*": cloudfront.BehaviorOptions(
                    origin=s3_origin,
                    cache_policy=immutable_cache,
                    origin_request_policy=cloudfront.OriginRequestPolicy.CORS_S3_ORIGIN,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD,
                ),
            },
            default_root_object="index.html",
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,
            comment="ZorkBurr Live Viewer",
            enabled=True,
            domain_names=domain_names,
            certificate=certificate,
        )

        # --- Route53 A Records ---
        if domain_name:
            route53.ARecord(
                self,
                "ARecord",
                zone=hosted_zone,
                record_name=domain_name,
                target=route53.RecordTarget.from_alias(
                    targets.CloudFrontTarget(self.distribution)
                ),
            )
            route53.ARecord(
                self,
                "WWWARecord",
                zone=hosted_zone,
                record_name=f"www.{domain_name}",
                target=route53.RecordTarget.from_alias(
                    targets.CloudFrontTarget(self.distribution)
                ),
            )

        # --- Outputs ---
        CfnOutput(self, "BucketName", value=self.bucket.bucket_name,
                  description="S3 bucket for state uploads")
        CfnOutput(self, "DistributionId", value=self.distribution.distribution_id,
                  description="CloudFront distribution ID")
        CfnOutput(self, "ViewerURL",
                  value=f"https://{domain_name}" if domain_name
                  else f"https://{self.distribution.distribution_domain_name}",
                  description="URL to access the viewer")

        if domain_name:
            CfnOutput(self, "NameServers",
                      value=cdk.Fn.join(",", hosted_zone.hosted_zone_name_servers),
                      description="Configure these with your domain registrar")
