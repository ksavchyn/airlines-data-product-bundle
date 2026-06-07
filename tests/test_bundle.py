"""Structural guardrail tests for the Airlines Data Product bundle.

These run in CI before any deploy. They assert the contract the bundle is
supposed to uphold (target catalogs/modes, prod-only daily refresh job, the
pipeline source format) so a bad edit fails the PR instead of prod.
"""
import os

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTEBOOK = os.path.join(ROOT, "src", "transformations", "04_sdp_pipeline.sql")


def _load(*parts):
    with open(os.path.join(ROOT, *parts)) as f:
        return yaml.safe_load(f)


# --- databricks.yml ---------------------------------------------------------

def test_bundle_name():
    assert _load("databricks.yml")["bundle"]["name"] == "airlines-data-product"


def test_three_targets():
    assert set(_load("databricks.yml")["targets"]) == {"dev", "staging", "prod"}


def test_target_modes_and_catalogs():
    t = _load("databricks.yml")["targets"]
    assert t["dev"]["mode"] == "development"
    assert t["dev"].get("default") is True
    assert t["dev"]["variables"]["catalog"] == "kat_savchyn"
    assert t["staging"]["mode"] == "production"
    assert t["staging"]["variables"]["catalog"] == "staging_catalog"
    assert t["prod"]["mode"] == "production"
    assert t["prod"]["variables"]["catalog"] == "prod_catalog"


def test_refresh_job_is_prod_only():
    t = _load("databricks.yml")["targets"]
    assert "resources" not in t["dev"]
    assert "resources" not in t["staging"]
    assert "airlines_daily_refresh" in t["prod"]["resources"]["jobs"]


def test_prod_schedule_is_6am_eastern_daily():
    job = _load("databricks.yml")["targets"]["prod"]["resources"]["jobs"][
        "airlines_daily_refresh"
    ]
    sched = job["schedule"]
    assert sched["quartz_cron_expression"] == "0 0 6 * * ?"
    assert sched["timezone_id"] == "America/New_York"
    assert sched["pause_status"] == "UNPAUSED"


# --- pipeline resource ------------------------------------------------------

def test_pipeline_is_serverless_and_parameterized():
    pl = _load("resources", "airlines_pipeline.pipeline.yml")["resources"][
        "pipelines"
    ]["airlines_data_product"]
    assert pl["serverless"] is True
    assert pl["catalog"] == "${var.catalog}"
    assert pl["configuration"]["catalog"] == "${var.catalog}"


# --- pipeline source --------------------------------------------------------

def test_notebook_is_databricks_source_format():
    with open(NOTEBOOK) as f:
        assert f.readline().strip() == "-- Databricks notebook source"


def test_notebook_defines_medallion_tables():
    with open(NOTEBOOK) as f:
        content = f.read()
    for table in ("bronze_flights", "silver_flights", "gold_fact_flights"):
        assert table in content, f"missing {table} in pipeline source"
