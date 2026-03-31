# Viewer S3 Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the ZorkGPT2 viewer to S3/CloudFront at `zorkgpt.com`, replacing the old ZorkGPT site.

**Architecture:** Single CDK stack (S3 + CloudFront + Route53 + ACM) serves a static HTML viewer. The local orchestrator pushes game state JSON to S3 via a Burr lifecycle hook. No server-side compute.

**Tech Stack:** AWS CDK (Python), S3, CloudFront, Route53, ACM, boto3

---

### Task 1: Hardcode domain in CDK stack

**Files:**
- Modify: `infrastructure/zorkburr_viewer_stack.py:9-10` (docstring)
- Modify: `infrastructure/zorkburr_viewer_stack.py:31` (domain_name assignment)
- Modify: `infrastructure/zorkburr_viewer_stack.py:108-122` (remove conditional)

- [ ] **Step 1: Update the docstring**

Remove the "optional domain" usage notes since the domain is now always `zorkgpt.com`:

```python
"""CDK stack for ZorkGPT viewer: S3 + CloudFront + Route53/ACM.

Deploys the live viewer at zorkgpt.com and www.zorkgpt.com.

Usage:
    cdk deploy
"""
```

- [ ] **Step 2: Replace context lookup with hardcoded domain**

Change line 31 from:
```python
domain_name = self.node.try_get_context("domain_name")
```
To:
```python
domain_name = "zorkgpt.com"
```

- [ ] **Step 3: Remove conditionals around Route53/ACM**

The `if domain_name:` guard on lines 111 and 160 is now always true. Remove the conditionals and dedent the bodies so Route53 hosted zone, ACM certificate, domain_names list, and A records are always created.

Before (lines 108-122):
```python
        # --- Optional Route53 + ACM ---
        certificate = None
        domain_names = None
        if domain_name:
            hosted_zone = route53.HostedZone(
                self, "HostedZone", zone_name=domain_name,
            )
            certificate = acm.Certificate(
                ...
            )
            domain_names = [domain_name, f"www.{domain_name}"]
```

After:
```python
        # --- Route53 + ACM ---
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
```

Similarly for the A records block (lines 160-178) — remove the `if domain_name:` guard and dedent.

- [ ] **Step 4: Remove conditional from ViewerURL output**

Before (lines 185-188):
```python
        CfnOutput(self, "ViewerURL",
                  value=f"https://{domain_name}" if domain_name
                  else f"https://{self.distribution.distribution_domain_name}",
                  description="URL to access the viewer")
```

After:
```python
        CfnOutput(self, "ViewerURL",
                  value=f"https://{domain_name}",
                  description="URL to access the viewer")
```

- [ ] **Step 5: Verify CDK synth succeeds**

Run:
```bash
cd /Users/rparrish/workingfolder/ZorkGPT2/infrastructure
pip install -r requirements.txt
cdk synth --quiet
```
Expected: exits 0 with no errors.

- [ ] **Step 6: Commit**

```bash
git add infrastructure/zorkburr_viewer_stack.py
git commit -m "feat(infra): hardcode zorkgpt.com domain in CDK stack"
```

---

### Task 2: Tear down old ZorkGPT stack

**Files:** None (operational task in old repo)

- [ ] **Step 1: Verify old stack exists**

```bash
cd /Users/rparrish/workingfolder/ZorkGPT/infrastructure
cdk list
```
Expected: `ZorkGPTViewerStack`

- [ ] **Step 2: Destroy old stack**

```bash
cdk destroy ZorkGPTViewerStack --force
```
Expected: Stack deletion completes. EC2, S3, CloudFront, Route53 hosted zone, CloudWatch alarms all removed.

Note: `--force` skips the interactive confirmation prompt. This is a destructive action on the OLD stack only. The old site is idle and we are intentionally replacing it.

---

### Task 3: Deploy new CDK stack

**Files:** None (operational task)

- [ ] **Step 1: Bootstrap CDK (if needed)**

```bash
cd /Users/rparrish/workingfolder/ZorkGPT2/infrastructure
cdk bootstrap
```
Expected: CDKToolkit stack is up to date or newly created in us-east-1.

- [ ] **Step 2: Deploy the stack**

```bash
cdk deploy --require-approval broadening
```
Expected: Stack creates S3 bucket, CloudFront distribution, Route53 hosted zone, ACM certificate. Outputs show `BucketName`, `DistributionId`, `ViewerURL`, `NameServers`.

Note: ACM certificate DNS validation happens automatically via Route53. However, the certificate won't fully validate until Dreamhost nameservers are updated (Task 5). The CloudFront distribution will be in a pending state until then.

- [ ] **Step 3: Record stack outputs**

Save the `BucketName` and `NameServers` values from the deploy output — needed for Tasks 4 and 5.

---

### Task 4: Upload viewer and configure local orchestrator

**Files:**
- Modify: `.env` (add `S3_BUCKET`)

- [ ] **Step 1: Upload viewer HTML**

```bash
cd /Users/rparrish/workingfolder/ZorkGPT2
python scripts/deploy_viewer.py <BUCKET_NAME>
```
Expected: `Uploading viewer/index.html -> s3://<BUCKET_NAME>/index.html` then `Done.`

- [ ] **Step 2: Add S3 bucket to .env**

Add to `.env`:
```
S3_BUCKET=<BUCKET_NAME>
```

The Pydantic config field is `s3_bucket` which maps to env var `S3_BUCKET`. The S3 hook in `zorkburr/app.py:73` activates when this is non-empty.

- [ ] **Step 3: Verify viewer loads via CloudFront URL**

Open the CloudFront URL (`https://d*.cloudfront.net`) in a browser. The viewer should load and show "No data" or similar (no episodes pushed yet).

---

### Task 5: Update Dreamhost nameservers

**Files:** None (external DNS task)

- [ ] **Step 1: Get nameservers from stack output**

The `NameServers` output is a comma-separated list of 4 NS records, e.g.:
```
ns-123.awsdns-45.com,ns-678.awsdns-90.net,ns-111.awsdns-22.org,ns-333.awsdns-44.co.uk
```

- [ ] **Step 2: Update nameservers in Dreamhost**

Log into Dreamhost panel, navigate to domain `zorkgpt.com`, and replace the existing nameservers with the 4 AWS NS records.

- [ ] **Step 3: Verify DNS propagation**

```bash
dig zorkgpt.com NS +short
```
Expected (after propagation): Shows the 4 AWS nameservers. This may take minutes to hours.

- [ ] **Step 4: Verify site loads at zorkgpt.com**

Open `https://zorkgpt.com` in a browser. The viewer should load. Also verify `https://www.zorkgpt.com` redirects or loads correctly.

---

### Task 6: End-to-end smoke test

**Files:** None (validation task)

- [ ] **Step 1: Run a short episode**

```bash
cd /Users/rparrish/workingfolder/ZorkGPT2
uv run python run_episode.py --max-turns 5 --episode-id smoke-test
```
Expected: Episode runs 5 turns, S3 hook uploads state each turn (check for `Failed to upload` in logs — there should be none).

- [ ] **Step 2: Verify live state in viewer**

Open `https://zorkgpt.com` (or CloudFront URL if DNS hasn't propagated). The viewer should show the `smoke-test` episode with live turn data, map, knowledge base, and score.

- [ ] **Step 3: Verify historical playback**

Select the `smoke-test` episode from the episode dropdown. Use the turn slider to browse turns 1-5. Each turn should load its snapshot correctly.

- [ ] **Step 4: Commit .env changes (do NOT commit .env itself)**

Verify `.env` is in `.gitignore`. If not already, ensure it is. The bucket name is not a secret but `.env` contains the API key.

```bash
grep "^\.env$" .gitignore
```
Expected: `.env` is listed in `.gitignore`.
