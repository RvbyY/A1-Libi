.venv/bin/pip install -U pytest
.venv/bin/pip install -U pytest-cov

.venv/bin/pytest src/galerelm/unit_tests
.venv/bin/pytest --cov=src.galerelm.models src/galerelm/unit_tests/