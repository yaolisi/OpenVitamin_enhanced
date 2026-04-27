.PHONY: help bootstrap bootstrap-prod env-init install install-gpu install-prod install-prod-soft up up-gpu up-prod down down-gpu down-prod status logs healthcheck doctor security-guardrails dependency-policy dependency-scan test-no-fallback test-workflow-control-flow smart-routing-smoke smart-routing-all-checks smart-routing-load-test smart-routing-experiment smart-routing-param-scan cb-doctor cb-benchmark cb-grid cb-recommend cb-snapshot cb-rollback cb-tier cb-gate cb-triage cb-tests cb-fast cb-latest-report cb-pipeline cb-all cb-release-check reset

CB_BASE_URL ?= http://127.0.0.1:8000
CB_MODEL ?= ollama:deepseek-r1:32b
CB_REQUESTS ?= 120
CB_TIMEOUT ?= 120
CB_CONCURRENCY ?= 10
CB_BATCH_WAIT_MS ?= 12
CB_BATCH_MAX_SIZE ?= 8
CB_CONCURRENCY_LIST ?= 10,20,30
CB_WAIT_MS_LIST ?= 4,8,12,16
CB_MAX_SIZE_LIST ?= 4,8,12
CB_TOP_K ?= 5
CB_MIN_THROUGHPUT_RATIO ?= 1.5
CB_MAX_FIRST_RESPONSE_RATIO ?= 0.3333
CB_MIN_SUCCESS_RATE ?= 0.99
CB_LAST_N ?= 10

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
	@echo "  make cb-benchmark MODEL=... BASE_URL=..."
	@echo "                   - Run sync/batch/async benchmark for continuous batching"
	@echo "  make cb-doctor [CHECK_API=1]"
	@echo "                   - Validate continuous batch tooling prerequisites"
	@echo "  make cb-grid MODEL=... BASE_URL=..."
	@echo "                   - Run continuous batch parameter grid search"
	@echo "  make cb-recommend"
	@echo "                   - Build recommended continuous batch config from grid summary"
	@echo "  make cb-snapshot / make cb-rollback SNAPSHOT=..."
	@echo "                   - Snapshot/rollback continuous batch config"
	@echo "  make cb-tier"
	@echo "                   - Auto-advice strict/balanced/lenient gate tier"
	@echo "  make cb-gate"
	@echo "                   - Run acceptance gate from latest grid summary"
	@echo "  make cb-triage RUN_DIR=..."
	@echo "                   - Diagnose gate failures and output action suggestions"
	@echo "  make cb-tests"
	@echo "                   - Run continuous batch tooling unit tests"
	@echo "  make cb-fast"
	@echo "                   - Fast verification: cb-tests + cb-doctor"
	@echo "  make cb-latest-report"
	@echo "                   - Show latest pipeline run summary quickly"
	@echo "  make cb-pipeline MODEL=... BASE_URL=... [APPLY=1] [AUTO_TIER=1]"
	@echo "                   - One-shot pipeline: snapshot -> grid -> recommend -> optional apply -> gate"
	@echo "  make cb-pipeline ... SKIP_DOCTOR=1"
	@echo "                   - Skip preflight doctor when already checked upstream"
	@echo "  make cb-all MODEL=... BASE_URL=... [CHECK_API=1] [AUTO_TIER=1] [AUTO_TRIAGE=1]"
	@echo "                   - Unified entry: cb-tests -> cb-doctor -> cb-pipeline"
	@echo "  make cb-release-check MODEL=... BASE_URL=..."
	@echo "                   - Release gate: cb-fast + cb-all"
	@echo "  make cb-pipeline ... AUTO_TRIAGE=1"
	@echo "                   - Auto-run triage suggestions when gate fails"
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

cb-doctor:
	@python backend/scripts/continuous_batch_doctor.py \
		--repo-root "." \
		--output-root "$(or $(PIPELINE_ROOT),backend/data/benchmarks/pipeline)" \
		$(if $(CHECK_API),--check-api,) \
		--base-url "$(or $(BASE_URL),$(CB_BASE_URL))" \
		--timeout-seconds "$(or $(TIMEOUT),10)" \
		$(if $(API_KEY),--api-key "$(API_KEY)",) \
		$(if $(API_KEY_HEADER),--api-key-header "$(API_KEY_HEADER)",)

cb-benchmark:
	@python backend/scripts/continuous_batch_benchmark.py \
		--base-url "$(or $(BASE_URL),$(CB_BASE_URL))" \
		--model "$(or $(MODEL),$(CB_MODEL))" \
		--requests "$(or $(REQUESTS),60)" \
		--concurrency "$(or $(CONCURRENCY),$(CB_CONCURRENCY))" \
		--batch-wait-ms "$(or $(BATCH_WAIT_MS),$(CB_BATCH_WAIT_MS))" \
		--batch-max-size "$(or $(BATCH_MAX_SIZE),$(CB_BATCH_MAX_SIZE))" \
		--timeout-seconds "$(or $(TIMEOUT),$(CB_TIMEOUT))" \
		--report-file "$(or $(REPORT),backend/data/benchmarks/continuous-batch.json)" \
		$(if $(API_KEY),--api-key "$(API_KEY)",) \
		$(if $(API_KEY_HEADER),--api-key-header "$(API_KEY_HEADER)",)

cb-grid:
	@python backend/scripts/continuous_batch_grid_search.py \
		--base-url "$(or $(BASE_URL),$(CB_BASE_URL))" \
		--model "$(or $(MODEL),$(CB_MODEL))" \
		--requests "$(or $(REQUESTS),$(CB_REQUESTS))" \
		--concurrency-list "$(or $(CONCURRENCY_LIST),$(CB_CONCURRENCY_LIST))" \
		--wait-ms-list "$(or $(WAIT_MS_LIST),$(CB_WAIT_MS_LIST))" \
		--max-size-list "$(or $(MAX_SIZE_LIST),$(CB_MAX_SIZE_LIST))" \
		--top-k "$(or $(TOP_K),$(CB_TOP_K))" \
		--timeout-seconds "$(or $(TIMEOUT),$(CB_TIMEOUT))" \
		--output-dir "$(or $(OUTPUT_DIR),backend/data/benchmarks/grid)" \
		--summary-file "$(or $(SUMMARY),backend/data/benchmarks/grid/summary.json)" \
		$(if $(API_KEY),--api-key "$(API_KEY)",) \
		$(if $(API_KEY_HEADER),--api-key-header "$(API_KEY_HEADER)",)

cb-recommend:
	@python backend/scripts/continuous_batch_recommend.py \
		--summary-file "$(or $(SUMMARY),backend/data/benchmarks/grid/summary.json)" \
		--base-url "$(or $(BASE_URL),$(CB_BASE_URL))" \
		--min-throughput-ratio "$(or $(MIN_THROUGHPUT_RATIO),$(CB_MIN_THROUGHPUT_RATIO))" \
		--max-first-response-ratio "$(or $(MAX_FIRST_RESPONSE_RATIO),$(CB_MAX_FIRST_RESPONSE_RATIO))" \
		--output-file "$(or $(RECOMMEND_OUT),backend/data/benchmarks/grid/recommended_config.json)" \
		$(if $(APPLY),--apply,) \
		$(if $(API_KEY),--api-key "$(API_KEY)",) \
		$(if $(API_KEY_HEADER),--api-key-header "$(API_KEY_HEADER)",)

cb-snapshot:
	@python backend/scripts/continuous_batch_rollback.py \
		--base-url "$(or $(BASE_URL),$(CB_BASE_URL))" \
		$(if $(API_KEY),--api-key "$(API_KEY)",) \
		$(if $(API_KEY_HEADER),--api-key-header "$(API_KEY_HEADER)",) \
		snapshot \
		--output-file "$(or $(SNAPSHOT_OUT),backend/data/benchmarks/grid/snapshot.json)"

cb-rollback:
	@python backend/scripts/continuous_batch_rollback.py \
		--base-url "$(or $(BASE_URL),$(CB_BASE_URL))" \
		$(if $(API_KEY),--api-key "$(API_KEY)",) \
		$(if $(API_KEY_HEADER),--api-key-header "$(API_KEY_HEADER)",) \
		rollback \
		--snapshot-file "$(or $(SNAPSHOT),backend/data/benchmarks/grid/snapshot.json)"

cb-tier:
	@python backend/scripts/continuous_batch_tier_advisor.py \
		--input "$(or $(INPUT),backend/data/benchmarks/pipeline)" \
		--last-n "$(or $(LAST_N),$(CB_LAST_N))" \
		--output-file "$(or $(TIER_OUT),backend/data/benchmarks/pipeline/tier-advice.json)"

cb-gate:
	@python backend/scripts/continuous_batch_acceptance_gate.py \
		--summary-file "$(or $(SUMMARY),backend/data/benchmarks/grid/summary.json)" \
		--min-throughput-ratio "$(or $(MIN_THROUGHPUT_RATIO),$(CB_MIN_THROUGHPUT_RATIO))" \
		--max-first-response-ratio "$(or $(MAX_FIRST_RESPONSE_RATIO),$(CB_MAX_FIRST_RESPONSE_RATIO))" \
		--min-success-rate "$(or $(MIN_SUCCESS_RATE),$(CB_MIN_SUCCESS_RATE))" \
		--output-file "$(or $(GATE_OUT),backend/data/benchmarks/grid/gate-result.json)"

cb-triage:
	@python backend/scripts/continuous_batch_triage.py \
		$(if $(RUN_DIR),--run-dir "$(RUN_DIR)",) \
		$(if $(GATE_FILE),--gate-file "$(GATE_FILE)",) \
		$(if $(SUMMARY),--summary-file "$(SUMMARY)",) \
		--output-file "$(or $(TRIAGE_OUT),backend/data/benchmarks/grid/triage.json)"

cb-tests:
	@PYTHONPATH=backend pytest \
		backend/tests/test_continuous_batch_tooling.py \
		backend/tests/test_continuous_batch_run_all.py \
		backend/tests/test_continuous_batch_latest_report.py \
		backend/tests/test_continuous_batch_doctor.py \
		-q

cb-fast:
	@$(MAKE) cb-tests
	@$(MAKE) cb-doctor

cb-latest-report:
	@python backend/scripts/continuous_batch_latest_report.py \
		--pipeline-root "$(or $(PIPELINE_ROOT),backend/data/benchmarks/pipeline)" \
		$(if $(RUN_DIR),--run-dir "$(RUN_DIR)",) \
		$(if $(REPORT_OUT),--output-file "$(REPORT_OUT)",)

cb-pipeline:
	@$(if $(SKIP_DOCTOR),echo [cb-pipeline] SKIP_DOCTOR=1 skipping cb-doctor,$(MAKE) cb-doctor $(if $(CHECK_API),CHECK_API=1,) \
		BASE_URL="$(or $(BASE_URL),$(CB_BASE_URL))" \
		PIPELINE_ROOT="$(or $(PIPELINE_ROOT),backend/data/benchmarks/pipeline)" \
		$(if $(API_KEY),API_KEY="$(API_KEY)",) \
		$(if $(API_KEY_HEADER),API_KEY_HEADER="$(API_KEY_HEADER)",))
	@python backend/scripts/continuous_batch_run_all.py \
		--base-url "$(or $(BASE_URL),$(CB_BASE_URL))" \
		--model "$(or $(MODEL),$(CB_MODEL))" \
		--requests "$(or $(REQUESTS),$(CB_REQUESTS))" \
		--concurrency-list "$(or $(CONCURRENCY_LIST),$(CB_CONCURRENCY_LIST))" \
		--wait-ms-list "$(or $(WAIT_MS_LIST),$(CB_WAIT_MS_LIST))" \
		--max-size-list "$(or $(MAX_SIZE_LIST),$(CB_MAX_SIZE_LIST))" \
		--timeout-seconds "$(or $(TIMEOUT),$(CB_TIMEOUT))" \
		--gate \
		--gate-min-throughput-ratio "$(or $(MIN_THROUGHPUT_RATIO),$(CB_MIN_THROUGHPUT_RATIO))" \
		--gate-max-first-response-ratio "$(or $(MAX_FIRST_RESPONSE_RATIO),$(CB_MAX_FIRST_RESPONSE_RATIO))" \
		--gate-min-success-rate "$(or $(MIN_SUCCESS_RATE),$(CB_MIN_SUCCESS_RATE))" \
		$(if $(SKIP_DOCTOR),--skip-doctor,) \
		$(if $(AUTO_TIER),--auto-tier,) \
		$(if $(AUTO_TRIAGE),--auto-triage,) \
		$(if $(APPLY),--apply,) \
		$(if $(API_KEY),--api-key "$(API_KEY)",) \
		$(if $(API_KEY_HEADER),--api-key-header "$(API_KEY_HEADER)",)

cb-all:
	@$(MAKE) cb-tests
	@$(MAKE) cb-doctor \
		$(if $(CHECK_API),CHECK_API=1,) \
		BASE_URL="$(or $(BASE_URL),$(CB_BASE_URL))" \
		PIPELINE_ROOT="$(or $(PIPELINE_ROOT),backend/data/benchmarks/pipeline)" \
		$(if $(API_KEY),API_KEY="$(API_KEY)",) \
		$(if $(API_KEY_HEADER),API_KEY_HEADER="$(API_KEY_HEADER)",)
	@$(MAKE) cb-pipeline \
		BASE_URL="$(or $(BASE_URL),$(CB_BASE_URL))" \
		MODEL="$(or $(MODEL),$(CB_MODEL))" \
		REQUESTS="$(or $(REQUESTS),$(CB_REQUESTS))" \
		CONCURRENCY_LIST="$(or $(CONCURRENCY_LIST),$(CB_CONCURRENCY_LIST))" \
		WAIT_MS_LIST="$(or $(WAIT_MS_LIST),$(CB_WAIT_MS_LIST))" \
		MAX_SIZE_LIST="$(or $(MAX_SIZE_LIST),$(CB_MAX_SIZE_LIST))" \
		TIMEOUT="$(or $(TIMEOUT),$(CB_TIMEOUT))" \
		MIN_THROUGHPUT_RATIO="$(or $(MIN_THROUGHPUT_RATIO),$(CB_MIN_THROUGHPUT_RATIO))" \
		MAX_FIRST_RESPONSE_RATIO="$(or $(MAX_FIRST_RESPONSE_RATIO),$(CB_MAX_FIRST_RESPONSE_RATIO))" \
		MIN_SUCCESS_RATE="$(or $(MIN_SUCCESS_RATE),$(CB_MIN_SUCCESS_RATE))" \
		$(if $(AUTO_TIER),AUTO_TIER=1,) \
		$(if $(AUTO_TRIAGE),AUTO_TRIAGE=1,) \
		$(if $(APPLY),APPLY=1,) \
		$(if $(CHECK_API),CHECK_API=1,) \
		SKIP_DOCTOR=1 \
		$(if $(API_KEY),API_KEY="$(API_KEY)",) \
		$(if $(API_KEY_HEADER),API_KEY_HEADER="$(API_KEY_HEADER)",)

cb-release-check:
	@$(MAKE) cb-fast \
		BASE_URL="$(or $(BASE_URL),$(CB_BASE_URL))" \
		$(if $(API_KEY),API_KEY="$(API_KEY)",) \
		$(if $(API_KEY_HEADER),API_KEY_HEADER="$(API_KEY_HEADER)",)
	@$(MAKE) cb-all \
		BASE_URL="$(or $(BASE_URL),$(CB_BASE_URL))" \
		MODEL="$(or $(MODEL),$(CB_MODEL))" \
		REQUESTS="$(or $(REQUESTS),$(CB_REQUESTS))" \
		CONCURRENCY_LIST="$(or $(CONCURRENCY_LIST),$(CB_CONCURRENCY_LIST))" \
		WAIT_MS_LIST="$(or $(WAIT_MS_LIST),$(CB_WAIT_MS_LIST))" \
		MAX_SIZE_LIST="$(or $(MAX_SIZE_LIST),$(CB_MAX_SIZE_LIST))" \
		TIMEOUT="$(or $(TIMEOUT),$(CB_TIMEOUT))" \
		MIN_THROUGHPUT_RATIO="$(or $(MIN_THROUGHPUT_RATIO),$(CB_MIN_THROUGHPUT_RATIO))" \
		MAX_FIRST_RESPONSE_RATIO="$(or $(MAX_FIRST_RESPONSE_RATIO),$(CB_MAX_FIRST_RESPONSE_RATIO))" \
		MIN_SUCCESS_RATE="$(or $(MIN_SUCCESS_RATE),$(CB_MIN_SUCCESS_RATE))" \
		$(if $(AUTO_TIER),AUTO_TIER=1,) \
		$(if $(AUTO_TRIAGE),AUTO_TRIAGE=1,) \
		$(if $(APPLY),APPLY=1,) \
		$(if $(CHECK_API),CHECK_API=1,) \
		$(if $(API_KEY),API_KEY="$(API_KEY)",) \
		$(if $(API_KEY_HEADER),API_KEY_HEADER="$(API_KEY_HEADER)",)

reset:
	@bash scripts/reset.sh
