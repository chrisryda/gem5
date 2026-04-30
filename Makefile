.PHONY: check \
        prepro_sims prepro_sims_whetstone prepro_sims_lbm_s prepro_sims_mcf_s prepro_sims_gcc_s \
        first-whetstone first-lbm first-mcf first-gcc first-par collect-cpi \
        sweep-iq-flat collect-iq-results

check:
	@echo "Running correctness check (hello_world)..."
	@./build/ARM/gem5.opt configs/sic_parvis_magna/magna.py -b hello_world -t 1B > corr-test.txt 2>&1
	@cat corr-test.txt | grep -q "Hello world!" \
		&& echo "Correctness check passed." \
		|| (echo "CORRECTNESS CHECK FAILED" >&2; exit 1)
	@rm corr-test.txt

# ---------------------------------------------------------------------------
# Infrastructure
# ---------------------------------------------------------------------------
GEM5            := ./build/ARM/gem5.opt
MAGNA           := configs/sic_parvis_magna/magna.py
DEFAULT         := configs/sic_parvis_magna/default.py
META_STATS_GREP := grep -e "hostSeconds" -e "simSeconds" -e "simTicks" -e "core.numCycles" -e "simInsts"
STATS_GREP      := grep -e "core.cpi" -e "core.ipc" -e "instsAdded" -e "deltaInstsAdded" -e "iqFullEvents"

# ---------------------------------------------------------------------------
# Run configuration  (override on the command line, e.g.: make first-par SUPER=1 ZERO_LAT=1)
#
#   SLIM         : simulation length, -t TICKS or -c CYCLES  (default: -t 100B)
#   ZLAT         : 1 = near-zero cache/DRAM latency          (magna.py only)
#   SUPER        : 1 = over-provisioned SuperMagnaOpus        (magna.py only)
#   WARMUP       : N > 0 = fast-forward N insts before timing (magna.py only)
#   USE_DEF      : 1 = use default.py instead of magna.py
# ---------------------------------------------------------------------------
SLIM    ?= -t 100B
ZLAT    ?= 0
SUPER   ?= 0
WARMUP  ?= 0
USE_DEF ?= 0

# Script to invoke
CONFIG := $(if $(filter 1,$(USE_DEF)),$(DEFAULT),$(MAGNA))

# Extra flags forwarded to magna.py only (suppressed when using default.py)
_MAGNA_ARGS :=
_MAGNA_ARGS += $(if $(filter     1,$(ZLAT)),--zero-lat)
_MAGNA_ARGS += $(if $(filter     1,$(SUPER)),--super)
_MAGNA_ARGS += $(if $(filter-out 0,$(WARMUP)),--warmup-insts $(WARMUP))
MAGNA_ARGS  := $(if $(filter 1,$(USE_DEF)),,$(_MAGNA_ARGS))

IQ  ?= 120
DIQ ?= 40

# SIM_TAG encodes the full configuration; used in output directory and file names.
# Examples: t100B_iq120_diq40 | t100B_super_iq32_diq0_zl | c5M_def_iq64
_TAG_BASE  := $(shell echo "$(SLIM)" | tr -d ' -')
_TAG_SUPER := $(if $(filter     1,$(SUPER)),_super)
_TAG_WARM  := $(if $(filter-out 0,$(WARMUP)),_warm$(WARMUP))
_TAG_ZL    := $(if $(filter     1,$(ZLAT)),_zl)
_TAG_DEF   := $(if $(filter     1,$(USE_DEF)),_def)
_TAG_IQ    := _iq$(IQ)
_TAG_DIQ   := _diq$(DIQ)
SIM_TAG    := $(strip $(_TAG_BASE)$(_TAG_SUPER)$(_TAG_WARM)$(_TAG_ZL)$(_TAG_DEF)$(_TAG_IQ)$(_TAG_DIQ))
# Context without IQ/DIQ — used to build per-sweep stat filenames
_CTX_TAG   := $(strip $(_TAG_BASE)$(_TAG_SUPER)$(_TAG_WARM)$(_TAG_ZL)$(_TAG_DEF))

IQ_ARGS := --iq-size $(IQ) --diq-size $(DIQ)

# ---------------------------------------------------------------------------
# SIMS benchmark preprocessing
# ---------------------------------------------------------------------------
prepro_sims_whetstone:
	$(GEM5) --outdir=m5out-prepro-sims-$(SIM_TAG)/whetstone $(MAGNA) -b whetstone $(SLIM) && mv m5out-prepro-sims-$(SIM_TAG)/whetstone/dist_dependencies.csv dist_dependencies_prepro_whetstone$(SIM_TAG).csv

prepro_sims_lbm_s:
	$(GEM5) --outdir=m5out-prepro-sims-$(SIM_TAG)/lbm_s $(MAGNA) -b lbm_s $(SLIM) && mv m5out-prepro-sims-$(SIM_TAG)/lbm_s/dist_dependencies.csv dist_dependencies_prepro_lbm_s$(SIM_TAG).csv

prepro_sims_mcf_s:
	$(GEM5) --outdir=m5out-prepro-sims-$(SIM_TAG)/mcf_s $(MAGNA) -b mcf_s $(SLIM) && mv m5out-prepro-sims-$(SIM_TAG)/mcf_s/dist_dependencies.csv dist_dependencies_prepro_mcf_s$(SIM_TAG).csv

prepro_sims_gcc_s:
	$(GEM5) --outdir=m5out-prepro-sims-$(SIM_TAG)/gcc_s $(MAGNA) -b gcc_s $(SLIM) && mv m5out-prepro-sims-$(SIM_TAG)/gcc_s/dist_dependencies.csv dist_dependencies_prepro_gcc_s$(SIM_TAG).csv

# Parallel parent: make check && make -j4 prepro_sims
prepro_sims: prepro_sims_whetstone prepro_sims_lbm_s prepro_sims_mcf_s prepro_sims_gcc_s
	mv dist_dependencies* plot_dependencies/stats

# ---------------------------------------------------------------------------
# Single-run targets  (make first-par [-jN] [options])
# ---------------------------------------------------------------------------
define run_first
	@$(GEM5) --outdir=m5out-$(SIM_TAG)/$(1)-$(SIM_TAG) $(CONFIG) -b $(1) $(SLIM) $(IQ_ARGS) $(MAGNA_ARGS)
	@{ echo "---------- Begin Simulation Statistics ----------"; \
	   echo "$(1) IQ=$(IQ) DIQ=$(DIQ) SIM_TAG=$(IQ)/$(DIQ) RUNTAG=$(SIM_TAG)"; \
	   echo "----------"; \
	   $(META_STATS_GREP) m5out-$(SIM_TAG)/$(1)-$(SIM_TAG)/stats.txt; \
	   echo; \
	   $(STATS_GREP) m5out-$(SIM_TAG)/$(1)-$(SIM_TAG)/stats.txt; \
	   echo "---------- End Simulation Statistics ----------"; \
	   echo; \
	} > m5out-$(SIM_TAG)/stat-$(1)-$(SIM_TAG).txt
endef

first-whetstone:
	$(call run_first,whetstone)

first-lbm:
	$(call run_first,lbm_s)

first-mcf:
	$(call run_first,mcf_s)

first-gcc:
	$(call run_first,gcc_s)

first-par: first-whetstone first-lbm first-mcf first-gcc
	@cat m5out-$(SIM_TAG)/stat-whetstone-$(SIM_TAG).txt \
	     m5out-$(SIM_TAG)/stat-lbm_s-$(SIM_TAG).txt \
	     m5out-$(SIM_TAG)/stat-mcf_s-$(SIM_TAG).txt \
	     m5out-$(SIM_TAG)/stat-gcc_s-$(SIM_TAG).txt

collect-cpi:
	@bash scripts/collect-cpi.sh

# ---------------------------------------------------------------------------
# IQ/DIQ sweep  (make sweep-iq-flat [-jN] [options])
#
# Each (benchmark × IQ/DIQ config) pair is an independent PHONY target so
# make -jN can schedule them in parallel.
#
# ---------------------------------------------------------------------------

# Configs to sweep: space-separated IQ-DIQ pairs
IQ_DIQ_CONFIGS := 8-0 128-0 
IQ_FLAT_BENCHMARKS := whetstone lbm_s mcf_s gcc_s

define iq_flat_rule
iq-flat-$(1)-$(2): _TAG := $(_CTX_TAG)_iq$(word 1,$(subst -, ,$(2)))_diq$(word 2,$(subst -, ,$(2)))
iq-flat-$(1)-$(2):
	@mkdir -p m5out-$$(_TAG)/$(1)-$(2)
	@$(GEM5) --outdir=m5out-$$(_TAG)/$(1)-$(2) $(CONFIG) -b $(1) $(SLIM) \
	    --iq-size $(word 1,$(subst -, ,$(2))) \
	    --diq-size $(word 2,$(subst -, ,$(2))) \
	    $(MAGNA_ARGS)
	@{ echo "---------- Begin Simulation Statistics ----------"; \
	   echo "$(1) IQ=$(word 1,$(subst -, ,$(2))) DIQ=$(word 2,$(subst -, ,$(2))) SIM_TAG=$(word 1,$(subst -, ,$(2)))/$(word 2,$(subst -, ,$(2))) RUNTAG=$$(_TAG)"; \
	   echo "----------"; \
	   $(META_STATS_GREP) m5out-$$(_TAG)/$(1)-$(2)/stats.txt; \
	   echo; \
	   $(STATS_GREP) m5out-$$(_TAG)/$(1)-$(2)/stats.txt; \
	   echo "---------- End Simulation Statistics ----------"; \
	   echo; \
	} > m5out-$$(_TAG)/stat-$(1)-$$(_TAG).txt
endef

$(foreach cfg,$(IQ_DIQ_CONFIGS),\
    $(foreach bench,$(IQ_FLAT_BENCHMARKS),\
        $(eval $(call iq_flat_rule,$(bench),$(cfg)))))

IQ_FLAT_TARGETS := $(foreach cfg,$(IQ_DIQ_CONFIGS),\
    $(foreach bench,$(IQ_FLAT_BENCHMARKS),iq-flat-$(bench)-$(cfg)))

.PHONY: $(IQ_FLAT_TARGETS)

sweep-iq-flat: $(IQ_FLAT_TARGETS)
	@$(MAKE) collect-iq-results

collect-iq-results:
	@rm -f iq-sweep-all.txt
	@find . -maxdepth 2 -path './m5out-*' -name "stat-*.txt" | sort | xargs cat >> iq-sweep-all.txt
	@echo "Results written to iq-sweep-all.txt"
