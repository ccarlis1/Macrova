.PHONY: test openapi openapi-check

test:
	python3 scripts/run_pytest.py

openapi:
	python3 scripts/run_export_openapi.py

openapi-check:
	python3 scripts/run_export_openapi.py --check
