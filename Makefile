.PHONY: test openapi openapi-check map map-check

test:
	python3 scripts/run_pytest.py

openapi:
	python3 scripts/run_export_openapi.py

openapi-check:
	python3 scripts/run_export_openapi.py --check

map:
	python3 scripts/gen_architecture_map.py

map-check:
	python3 scripts/gen_architecture_map.py --check
