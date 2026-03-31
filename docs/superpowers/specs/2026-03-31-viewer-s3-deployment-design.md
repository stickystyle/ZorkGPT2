# Viewer S3 Deployment Design

Replace the old ZorkGPT site at `zorkgpt.com` with the ZorkGPT2 viewer, backed by S3 for live game state.

## Context

- Old ZorkGPT has a full CDK stack (S3 + CloudFront + EC2 + Route53 + monitoring) deployed to `zorkgpt.com`
- The old site is idle — no games running
- ZorkGPT2 already has a CDK stack (`infrastructure/zorkburr_viewer_stack.py`), S3 hook (`zorkburr/viewer/s3_hook.py`), state exporter, and deploy script
- The orchestrator runs locally; only the viewer and state pipeline need to be deployed
- Domain `zorkgpt.com` is registered at Dreamhost; nameservers must be updated manually after deploy

## Infrastructure Changes

### CDK Stack (`infrastructure/zorkburr_viewer_stack.py`)

**Single change:** Hardcode `zorkgpt.com` domain instead of the optional `domain_name` context parameter.

Before:
```python
domain_name = self.node.try_get_context("domain_name")
# ... conditional Route53/ACM blocks
```

After:
```python
domain_name = "zorkgpt.com"
# ... Route53/ACM blocks always execute (no conditionals)
```

Everything else stays as-is:
- S3 bucket: private, CORS, auto-delete, `DESTROY` removal policy
- CloudFront: 3 cache behaviors (5s live state, 365d turn snapshots, 5min default)
- Route53 hosted zone for `zorkgpt.com`
- ACM certificate with `zorkgpt.com` + `www.zorkgpt.com` SANs, DNS validation
- `us-east-1` region (required for CloudFront + ACM)
- Price class: `PRICE_CLASS_100` (NA + Europe)

### No Other Code Changes

These components work as-is with no modifications:
- `zorkburr/viewer/s3_hook.py` — Burr post-step hook that uploads live state, turn snapshots, and episode index to S3
- `zorkburr/viewer/state_export.py` — converts Burr state to viewer JSON
- `scripts/deploy_viewer.py` — uploads `viewer/index.html` to S3
- `viewer/index.html` — the viewer itself

## Deployment Workflow

### Step 1: Tear down old stack

```bash
cd /Users/rparrish/workingfolder/ZorkGPT/infrastructure
cdk destroy ZorkGPTViewerStack
```

Removes: old S3 bucket, CloudFront distribution, EC2 instance, Route53 hosted zone, CloudWatch alarms, IAM roles.

### Step 2: Deploy new stack

```bash
cd /Users/rparrish/workingfolder/ZorkGPT2/infrastructure
pip install -r requirements.txt  # aws-cdk-lib, constructs
cdk bootstrap aws://ACCOUNT/us-east-1  # if not already bootstrapped
cdk deploy
```

### Step 3: Upload viewer HTML

```bash
# Bucket name from stack output
python scripts/deploy_viewer.py <bucket-name>
```

### Step 4: Update Dreamhost nameservers

Copy the 4 NS records from the `NameServers` stack output into Dreamhost's DNS settings for `zorkgpt.com`. DNS propagation typically under 1 hour, worst case 48 hours. The CloudFront URL (`d*.cloudfront.net`) works immediately.

### Step 5: Configure local orchestrator

Add to `.env`:
```
S3_BUCKET=<bucket-name>
```

The S3 hook activates automatically when `s3_bucket` is set in config.

## Out of Scope

- CI/CD pipeline — manual deploy is fine for a single HTML file
- EC2 or remote orchestrator — episodes run locally
- CloudWatch monitoring — no server to monitor
- Changes to the viewer HTML or S3 hook
