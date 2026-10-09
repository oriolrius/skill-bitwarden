.PHONY: check lint test scan fmt

check: lint test scan

lint:
	shellcheck skill/bitwarden/scripts/* install.sh tests/fixtures/fake-bw/bw
	uv run ruff check .
	uv run ruff format --check .
	uv run python scripts/validate_skill.py skill/bitwarden

test:
	bats tests/bats
	uv run pytest -q

scan:
	gitleaks dir --config .gitleaks.toml --redact --no-banner .
	@if git rev-parse --verify HEAD >/dev/null 2>&1; then gitleaks git --config .gitleaks.toml --redact --no-banner .; fi
	uv run python scripts/check_public_safety.py --all
	uv run python scripts/check_public_safety.py --history

fmt:
	uv run ruff check --fix .
	uv run ruff format .
