# Airlines Data Product — Declarative Automation Bundle

Packages the **Airlines-Data-Product** SDP pipeline (Bronze → Silver → Gold
medallion) as a Databricks Asset Bundle with three environments.

## Layout

```
airlines-data-product-bundle/
├── databricks.yml                         # bundle config + dev/staging/prod targets + prod job
├── resources/
│   └── airlines_pipeline.pipeline.yml     # the SDP pipeline resource
├── src/
│   └── transformations/
│       └── 04_sdp_pipeline.sql            # pipeline source (Databricks notebook format)
├── tests/
│   └── test_bundle.py                     # structural guardrail tests (run in CI)
├── requirements-dev.txt
├── pytest.ini
└── .github/workflows/cicd.yml             # validate + test + deploy pipeline
```

## Targets

| Target  | Mode          | Catalog          | Scheduled job |
|---------|---------------|------------------|---------------|
| `dev`   | development   | `kat_savchyn`    | —             |
| staging | production    | `staging_catalog`| —             |
| `prod`  | production    | `prod_catalog`   | Daily 06:00 America/New_York |

All three deploy to **e2-demo-field-eng** (profile `e2-demo`); only the catalog
and mode differ. `dev` is the default target.

The pipeline reads its raw `raw_airlines.*` source from **the same catalog it
writes to** (via the `${catalog}` config passed to the SQL). Each environment is
self-contained — `raw_airlines` must exist in `staging_catalog` / `prod_catalog`
before deploying there.

The output schema is `airlines_pipeline` in every environment; the pipeline is
serverless + Photon, triggered (not continuous). Bundle target mode controls the
pipeline `development` flag automatically (true for dev, false for staging/prod).

## Scheduled refresh (prod only)

The `airlines_daily_refresh` job is defined only inside the `prod` target, so it
never deploys to dev or staging. It runs the pipeline daily at **06:00 US
Eastern** (`quartz_cron_expression: "0 0 6 * * ?"`, `timezone_id:
America/New_York` — DST-aware). `full_refresh: false` (incremental refresh).

## Commands

```bash
# Validate
databricks bundle validate -t dev     -p e2-demo
databricks bundle validate -t staging -p e2-demo
databricks bundle validate -t prod    -p e2-demo

# Deploy
databricks bundle deploy -t dev     -p e2-demo
databricks bundle deploy -t staging -p e2-demo
databricks bundle deploy -t prod    -p e2-demo

# Run the pipeline on demand
databricks bundle run airlines_data_product -t dev -p e2-demo

# Run the prod refresh job on demand
databricks bundle run airlines_daily_refresh -t prod -p e2-demo

# Run the tests
pip install -r requirements-dev.txt && pytest
```

## CI/CD (GitHub Actions)

`.github/workflows/cicd.yml`:

| Trigger | Jobs |
|---------|------|
| **Pull request → main** | `validate-and-test` (bundle validate all targets + pytest) |
| **Push / merge → main** | `validate-and-test` → `deploy-staging` (auto) → `deploy-prod` (**manual approval**) |

Auth uses a **Databricks personal access token**. The CLI is installed via
`databricks/setup-cli` and authenticates from `DATABRICKS_HOST` +
`DATABRICKS_TOKEN` in the environment — no profile or extra config.

### One-time setup required

1. **Generate a Databricks PAT.** In the workspace: Settings → Developer →
   Access tokens → Generate. The owning identity needs `CAN_MANAGE` on the
   bundle resources / target catalogs. (A service principal token is
   recommended for prod over a personal one.)

2. **GitHub repository secret** (Settings → Secrets and variables → Actions →
   *Secrets*):
   - `DATABRICKS_TOKEN` = the PAT.

3. **GitHub repository variable** (same page → *Variables*):
   - `DATABRICKS_HOST` = `https://e2-demo-field-eng.cloud.databricks.com`

   If staging and prod use *different* tokens or hosts, define
   `DATABRICKS_TOKEN` / `DATABRICKS_HOST` as *environment*-scoped secret/variable
   on the `staging` / `production` environments instead of repo-wide; they
   override the workflow-level values.

4. **Manual approval gate for production.** Settings → Environments → create
   `production` → enable **Required reviewers** and add the approver(s). The
   `deploy-prod` job references `environment: production`, so the run pauses for
   approval before it deploys. (Optionally create a `staging` environment too;
   it needs no protection rule.)
