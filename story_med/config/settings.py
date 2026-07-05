"""患者故事项目路径常量。"""

from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR / "docs"
PROMPTS_DIR = BASE_DIR / "prompts"
RESULTS_DIR = BASE_DIR / "results"
ASSETS_DIR = RESULTS_DIR / "assets"
TMP_DIR = RESULTS_DIR / "temp"
EDIT_RESULTS_DIR = RESULTS_DIR / "edit"
EDIT_DIALOGUE_RESULTS_DIR = RESULTS_DIR / "edit_dialogue"
CASE_IMAGE_DIR = BASE_DIR / "img"

DEFAULT_CONFIG_FILE = CONFIG_DIR / "config.yaml"
DEFAULT_LLM_CONFIG_FILE = CONFIG_DIR / "llm_config.yaml"
DEFAULT_VISION_CONFIG_FILE = CONFIG_DIR / "vision_config.yaml"
DEFAULT_HARD_RULE_FIELD_FILE = DATA_DIR / "hard_rule_fields.yaml"
DEFAULT_CLINICAL_CASE_FILE = DATA_DIR / "clinical_case.yaml"
DEFAULT_EDIT_CASE_FILE = DATA_DIR / "edit_story.yaml"
DEFAULT_EDIT_DIALOGUE_CASE_FILE = DATA_DIR / "edit_dialogue_cases.yaml"
DEFAULT_RESULT_FILE = RESULTS_DIR / "patient_story_run.json"
