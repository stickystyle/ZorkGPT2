# Viewer

Single-file live viewer (`index.html`) for ZorkBurr episodes, served via S3 + CloudFront.

## Deployment

```bash
# Load creds and bucket name from .env
source .env && export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_DEFAULT_REGION

# Upload to S3
aws s3 cp viewer/index.html s3://$S3_BUCKET/index.html \
  --content-type "text/html" --cache-control "public, max-age=300"

# Invalidate CloudFront cache
aws cloudfront create-invalidation \
  --distribution-id E206ZNKA20ZUPT --paths "/index.html"
```

- Bucket name: `S3_BUCKET` env var from `.env`
- CloudFront distribution ID: `E206ZNKA20ZUPT`
- Domain: `zorkgpt.com` / `www.zorkgpt.com`
- Invalidation takes ~1-2 minutes to propagate

## Architecture

- `index.html` is the entire viewer — no build step, no dependencies
- Polls `live/current_state.json` from S3 for real-time updates
- Historical turns fetched from `episodes/*/turns/*.json`
- Episode index from `episodes/index.json`
- Infrastructure defined in `infrastructure/zorkburr_viewer_stack.py` (CDK)
