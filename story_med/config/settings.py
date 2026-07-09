"""患者故事项目路径常量。"""

from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = BASE_DIR / "config"
ENVS_DIR = BASE_DIR / "envs"
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR / "docs"
PROMPTS_DIR = BASE_DIR / "prompts"
RESULTS_DIR = BASE_DIR / "results"
BASELINES_DIR = BASE_DIR / "baselines"
ASSETS_DIR = RESULTS_DIR / "assets"
GENERATION_RUNS_DIR = RESULTS_DIR / "generation_runs"
STORY_AUDITS_DIR = RESULTS_DIR / "story_audits"
EDIT_RUNS_DIR = RESULTS_DIR / "edit_runs"
EDIT_AUDITS_DIR = RESULTS_DIR / "edit_audits"
CASE_IMAGE_DIR = BASE_DIR / "img"

DEFAULT_CONFIG_FILE = CONFIG_DIR / "config.yaml"
DEFAULT_HARD_RULE_FIELD_FILE = DATA_DIR / "hard_rule_fields.yaml"
DEFAULT_CLINICAL_CASE_FILE = DATA_DIR / "clinical_case.yaml"
DEFAULT_EDIT_DIALOGUE_CASE_FILE = DATA_DIR / "edit_dialogue_cases.yaml"
DEFAULT_RESULT_FILE = RESULTS_DIR / "patient_story_run.json"
