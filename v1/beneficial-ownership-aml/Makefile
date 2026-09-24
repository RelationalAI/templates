PY ?= .venv/bin/python

.PHONY: setup data data-ci test-offline test-sf run run-offline bench zip results

setup:
	uv venv --python 3.12 .venv
	uv pip install --python $(PY) -e ".[dev]"

data:
	$(PY) -m data.generator.generate --seed 7 --companies 5000 --persons 3000 --days 180 --density normal --holdout 0.2 --out data/sample

data-ci:
	$(PY) -m data.generator.generate --seed 7 --companies 500 --persons 300 --out data/ci

test-offline:
	$(PY) -m pytest -m offline

test-sf:
	RAI_SF=1 $(PY) -m pytest -m snowflake

run:
	$(PY) beneficial_ownership_local.py

run-offline:
	$(PY) beneficial_ownership_local.py --offline

bench:
	$(PY) benchmarks/run_scaling.py

zip:
	cd .. && zip -r beneficial-ownership-aml.zip beneficial-ownership-aml \
		-x "*/.venv/*" "*/build/*" "*/.pytest_cache/*" "*/__pycache__/*" "*/eval/out/*" "*/benchmarks/out/*" "*/raiconfig.yaml" "*.duckdb"

# Regenerate the sample and every number reported in the README (Snowflake; ~2-3 hours on CPU engines).
results:
	$(PY) -m data.generator.generate --seed 7 --companies 5000 --persons 3000 --days 180 --density normal --holdout 0.2 --out data/sample
	$(PY) -m data.generator.generate --seed 7 --companies 500 --persons 300 --out data/ci
	$(PY) -m data.fixtures.build_fixtures
	$(PY) calibrate.py --with-gnn
	$(PY) -m eval.augmentation_eval --sweep
	$(PY) -m eval.augmentation_eval --gnn-ablation
	$(PY) -m eval.augmentation_eval
	$(PY) -m eval.detection_eval --no-gnn
	$(PY) -m eval.gnn_eval
	$(PY) tune_weights.py
	$(PY) beneficial_ownership_local.py --no-gnn --budgets 100,200,400,800
	$(PY) -m data.generator.stats data/sample
	-$(PY) -m data.generator.snowflake_load data/sample BENEFICIAL_OWNERSHIP.DATA   # for beneficial_ownership.py only
