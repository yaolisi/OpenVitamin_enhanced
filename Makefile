.PHONY: help bootstrap bootstrap-prod env-init install install-gpu install-prod install-prod-soft up up-gpu up-prod down down-gpu down-prod status logs healthcheck doctor security-guardrails dependency-policy dependency-scan test-no-fallback test-workflow-control-flow smart-routing-smoke smart-routing-all-checks smart-routing-load-test smart-routing-experiment smart-routing-param-scan reset

help:
	@echo "OpenVitamin Docker helper targets:"
	@echo "  make bootstrap     - First-time setup (env-init + doctor + install)"
	@echo "  make bootstrap-prod"
	@echo "                   - First-time prod setup (env-init + strict doctor + install-prod)"
	@echo "  make env-init      - Initialize .env from .env.example"
	@echo "  make install       - Build and start base profile"
	@echo "  make install-gpu   - Build and start GPU profile"
	@echo "  make install-prod  - Build and start production profile"
	@echo "  make install-prod-soft"
	@echo "                   - Build/start prod profile with relaxed doctor warnings"
	@echo "  make up            - Start base profile"
	@echo "  make up-gpu        - Start GPU profile"
	@echo "  make up-prod       - Start production profile"
	@echo "  make down          - Stop base profile"
	@echo "  make down-gpu      - Stop GPU profile"
	@echo "  make down-prod     - Stop production profile"
	@echo "  make status        - Show status in all profile views"
	@echo "  make logs          - Tail logs"
	@echo "  make healthcheck   - Run health checks"
	@echo "  make doctor        - Run environment diagnostics"
	@echo "  make security-guardrails"
	@echo "                   - Enforce production security config gate"
	@echo "  make dependency-policy"
	@echo "                   - Enforce dependency version lock policy"
	@echo "  make dependency-scan"
	@echo "                   - Run third-party dependency vulnerability scan"
	@echo "  DOCTOR_STRICT_WARNINGS=1 make doctor"
	@echo "                   - Treat warnings as failures"
	@echo "  make test-no-fallback"
	@echo "                   - Run API no-fallback regression tests"
	@echo "  make test-no-fallback TEST_ARGS=\"-k memory -x\""
	@echo "                   - Run subset/extra pytest args for no-fallback suite"
	@echo "  make test-workflow-control-flow"
	@echo "                   - Run workflow control-flow regression suite"
	@echo "  make smart-routing-smoke"
	@echo "                   - Run smart routing script/unit smoke tests"
	@echo "  make smart-routing-all-checks"
	@echo "                   - Run full smart routing regression checks"
	@echo "  make smart-routing-load-test MODEL=... BASE_URL=..."
	@echo "                   - Run smart routing load test script"
	@echo "  make smart-routing-experiment MODEL=... CANDIDATE=..."
	@echo "                   - Run one-click experiment (baseline vs candidate)"
	@echo "  make smart-routing-param-scan MODEL=... CANDIDATE=..."
	@echo "                   - Run parameter scan for candidate policy"
	@echo "  make reset         - Remove containers and volumes"

install:
	@bash scripts/install.sh

bootstrap:
	@$(MAKE) env-init
	@$(MAKE) doctor
	@$(MAKE) install

bootstrap-prod:
	@$(MAKE) env-init
	@DOCTOR_STRICT_WARNINGS=1 $(MAKE) doctor
	@$(MAKE) install-prod

env-init:
	@bash scripts/env-init.sh

install-gpu:
	@bash scripts/install-gpu.sh

install-prod:
	@bash scripts/install-prod.sh

install-prod-soft:
	@DOCTOR_STRICT_WARNINGS=0 bash scripts/install-prod.sh

up:
	@bash scripts/up.sh

up-gpu:
	@bash scripts/up-gpu.sh

up-prod:
	@bash scripts/up-prod.sh

down:
	@bash scripts/down.sh

down-gpu:
	@bash scripts/down-gpu.sh

down-prod:
	@bash scripts/down-prod.sh

status:
	@bash scripts/status.sh

logs:
	@bash scripts/logs.sh

healthcheck:
	@bash scripts/healthcheck.sh

doctor:
	@bash scripts/doctor.sh

security-guardrails:
	@bash scripts/check-security-guardrails.sh

dependency-policy:
	@bash scripts/check-dependency-version-policy.sh

dependency-scan:
	@bash scripts/scan-dependencies.sh

test-no-fallback:
	@bash scripts/test-no-fallback.sh $(TEST_ARGS)

test-workflow-control-flow:
	@bash backend/scripts/test_workflow_control_flow_regression.sh

smart-routing-smoke:
	@PYTHONPATH=backend pytest backend/tests/test_smart_routing_script_utils.py backend/tests/test_model_router_smart_routing.py backend/tests/test_smart_routing_validation.py

smart-routing-all-checks:
	@$(MAKE) smart-routing-smoke

smart-routing-load-test:
	@python backend/scripts/smart_routing_load_test.py \
		--base-url "$(or $(BASE_URL),http://127.0.0.1:8000)" \
		--model "$(or $(MODEL),ollama:deepseek-r1:32b)" \
		--duration-seconds "$(or $(DURATION),30)" \
		--rps "$(or $(RPS),5)" \
		--concurrency "$(or $(CONCURRENCY),10)" \
		--large-ratio "$(or $(LARGE_RATIO),0.6)" \
		--min-success-rate "$(or $(MIN_SUCCESS_RATE),0.95)" \
		--max-avg-latency-ms "$(or $(MAX_AVG_LATENCY_MS),2500)" \
		--min-fallback-ratio "$(or $(MIN_FALLBACK_RATIO),0.0)" \
		--report-file "$(or $(REPORT),./tmp/smart-routing-load-report.json)" \
		$(if $(API_KEY),--api-key "$(API_KEY)",) \
		$(if $(API_KEY_HEADER),--api-key-header "$(API_KEY_HEADER)",)

smart-routing-experiment:
	@python backend/scripts/run_smart_routing_experiment.py \
		--base-url "$(or $(BASE_URL),http://127.0.0.1:8000)" \
		--model "$(or $(MODEL),ollama:deepseek-r1:32b)" \
		--candidate-policy-file "$(or $(CANDIDATE),backend/scripts/candidate_policy.example.json)" \
		--output-dir "$(or $(OUTPUT),./tmp/smart-routing-exp)" \
		--duration-seconds "$(or $(DURATION),30)" \
		--rps "$(or $(RPS),6)" \
		--concurrency "$(or $(CONCURRENCY),12)" \
		--large-ratio "$(or $(LARGE_RATIO),0.6)" \
		--promote-only-if-better \
		--promote-require-pass \
		$(if $(FAIL_ON_NO_PROMOTE),--fail-on-no-promote,) \
		$(if $(PROMOTE_REPORT),--promote-report-file "$(PROMOTE_REPORT)",) \
		$(if $(API_KEY),--api-key "$(API_KEY)",) \
		$(if $(API_KEY_HEADER),--api-key-header "$(API_KEY_HEADER)",)

smart-routing-param-scan:
	@python backend/scripts/smart_routing_param_scan.py \
		--base-url "$(or $(BASE_URL),http://127.0.0.1:8000)" \
		--model "$(or $(MODEL),ollama:deepseek-r1:32b)" \
		--candidate-policy-file "$(or $(CANDIDATE),backend/scripts/candidate_policy.example.json)" \
		--scan-model-alias "$(or $(SCAN_ALIAS),$(or $(MODEL),ollama:deepseek-r1:32b))" \
		--duration-seconds "$(or $(DURATION),20)" \
		--rps "$(or $(RPS),6)" \
		--concurrency "$(or $(CONCURRENCY),12)" \
		--large-ratio "$(or $(LARGE_RATIO),0.6)" \
		--top-k "$(or $(TOP_K),5)" \
		--max-scan-combos "$(or $(MAX_SCAN_COMBOS),100)" \
		--max-estimated-minutes "$(or $(MAX_ESTIMATED_MINUTES),45)" \
		--estimated-warn-ratio "$(or $(ESTIMATED_WARN_RATIO),0.7)" \
		--estimated-fail-ratio "$(or $(ESTIMATED_FAIL_RATIO),1.0)" \
		$(if $(PASS_ONLY),--pass-only,) \
		$(if $(DRY_RUN),--dry-run,) \
		$(if $(APPLY_BEST),--apply-best-policy,) \
		$(if $(EXPORT_BEST),--export-best-policy-file "$(EXPORT_BEST)",) \
		$(if $(API_KEY),--api-key "$(API_KEY)",) \
		$(if $(API_KEY_HEADER),--api-key-header "$(API_KEY_HEADER)",) \
		--output-dir "$(or $(OUTPUT),./tmp/smart-routing-scan)"

reset:
	@bash scripts/reset.sh
