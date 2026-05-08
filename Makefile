.PHONY: check \
        prepro_sims prepro_sims_whetstone prepro_sims_lbm_s prepro_sims_mcf_s prepro_sims_gcc_s \
        first-whetstone first-lbm first-mcf first-gcc first-par collect-cpi \
        first-exchange2 first-fotonik3d first-nab first-x264 \
        first-perlbench first-leela first-deepsjeng first-bwaves \
        sweep-iq-flat collect-iq-results \
        plots

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
#   SLIM     : simulation length, -t TICKS or -c CYCLES   (default: -t 100B)
#   ZLAT     : 1 = near-zero cache/DRAM latency
#   SUPER    : 1 = over-provisioned SuperMagnaOpus
#   WARMUP   : N > 0 = fast-forward N insts in ATOMIC before timing
#   O3WARMUP : N > 0 = run N insts on O3 (no stats) before measurement (requires WARMUP > 0)
#   USE_DEF  : 1 = use default.py instead of magna.py
# ---------------------------------------------------------------------------
SLIM     ?= -t 100B
ZLAT     ?= 0
SUPER    ?= 0
WARMUP   ?= 0
O3WARMUP ?= 0
USE_DEF  ?= 0

# Script to invoke
CONFIG := $(if $(filter 1,$(USE_DEF)),$(DEFAULT),$(MAGNA))

# Extra flags forwarded to the config script
CONFIG_ARGS :=
CONFIG_ARGS += $(if $(filter     1,$(ZLAT)),--zero-lat)
CONFIG_ARGS += $(if $(filter     1,$(SUPER)),--super)
CONFIG_ARGS += $(if $(filter-out 0,$(WARMUP)),--warmup-insts $(WARMUP))
CONFIG_ARGS += $(if $(filter-out 0,$(O3WARMUP)),--o3-warmup-insts $(O3WARMUP))

IQ  ?= 120
DIQ ?= 40

# SIM_TAG encodes the full configuration; used in output directory and file names.
_TAG_BASE    := $(shell echo "$(SLIM)" | tr -d ' -')
_TAG_SUPER   := $(if $(filter     1,$(SUPER)),_super)
_TAG_WARM    := $(if $(filter-out 0,$(WARMUP)),_warm$(WARMUP))
_TAG_O3WARM  := $(if $(filter-out 0,$(O3WARMUP)),_o3warm$(O3WARMUP))
_TAG_ZL      := $(if $(filter     1,$(ZLAT)),_zl)
_TAG_DEF     := $(if $(filter     1,$(USE_DEF)),_def)
_TAG_IQ      := _iq$(IQ)
_TAG_DIQ     := _diq$(DIQ)
SIM_TAG      := $(strip $(_TAG_BASE)$(_TAG_SUPER)$(_TAG_WARM)$(_TAG_O3WARM)$(_TAG_ZL)$(_TAG_DEF)$(_TAG_IQ)$(_TAG_DIQ))
# Context without IQ/DIQ — used to build per-sweep stat filenames
_CTX_TAG     := $(strip $(_TAG_BASE)$(_TAG_SUPER)$(_TAG_WARM)$(_TAG_O3WARM)$(_TAG_ZL)$(_TAG_DEF))

IQ_ARGS := --iq-size $(IQ) --diq-size $(DIQ)

M5OUT_ROOT := m5out-sims

# ---------------------------------------------------------------------------
# SIMS benchmark preprocessing
# ---------------------------------------------------------------------------
prepro_sims_whetstone:
	$(GEM5) --outdir=$(M5OUT_ROOT)/m5out-prepro-sims-$(SIM_TAG)/whetstone $(MAGNA) -b whetstone $(SLIM) && mv $(M5OUT_ROOT)/m5out-prepro-sims-$(SIM_TAG)/whetstone/dist_dependencies.csv dist_dependencies_prepro_whetstone$(SIM_TAG).csv

prepro_sims_lbm_s:
	$(GEM5) --outdir=$(M5OUT_ROOT)/m5out-prepro-sims-$(SIM_TAG)/lbm_s $(MAGNA) -b lbm_s $(SLIM) && mv $(M5OUT_ROOT)/m5out-prepro-sims-$(SIM_TAG)/lbm_s/dist_dependencies.csv dist_dependencies_prepro_lbm_s$(SIM_TAG).csv

prepro_sims_mcf_s:
	$(GEM5) --outdir=$(M5OUT_ROOT)/m5out-prepro-sims-$(SIM_TAG)/mcf_s $(MAGNA) -b mcf_s $(SLIM) && mv $(M5OUT_ROOT)/m5out-prepro-sims-$(SIM_TAG)/mcf_s/dist_dependencies.csv dist_dependencies_prepro_mcf_s$(SIM_TAG).csv

prepro_sims_gcc_s:
	$(GEM5) --outdir=$(M5OUT_ROOT)/m5out-prepro-sims-$(SIM_TAG)/gcc_s $(MAGNA) -b gcc_s $(SLIM) && mv $(M5OUT_ROOT)/m5out-prepro-sims-$(SIM_TAG)/gcc_s/dist_dependencies.csv dist_dependencies_prepro_gcc_s$(SIM_TAG).csv

# Parallel parent: make check && make -j4 prepro_sims
prepro_sims: prepro_sims_whetstone prepro_sims_lbm_s prepro_sims_mcf_s prepro_sims_gcc_s
	mv dist_dependencies* plot_dependencies/stats

# ---------------------------------------------------------------------------
# Single-run targets  (make first-par [-jN] [options])
# ---------------------------------------------------------------------------
define run_first
	@$(GEM5) --outdir=$(M5OUT_ROOT)/m5out-$(SIM_TAG)/$(1)-$(SIM_TAG) $(CONFIG) -b $(1) $(SLIM) $(IQ_ARGS) $(CONFIG_ARGS)
	@{ echo "---------- Begin Simulation Statistics ----------"; \
	   echo "$(1) IQ=$(IQ) DIQ=$(DIQ) SIM_TAG=$(IQ)/$(DIQ) RUNTAG=$(SIM_TAG)"; \
	   echo "----------"; \
	   $(META_STATS_GREP) $(M5OUT_ROOT)/m5out-$(SIM_TAG)/$(1)-$(SIM_TAG)/stats.txt; \
	   echo; \
	   $(STATS_GREP) $(M5OUT_ROOT)/m5out-$(SIM_TAG)/$(1)-$(SIM_TAG)/stats.txt; \
	   echo "---------- End Simulation Statistics ----------"; \
	   echo; \
	} > $(M5OUT_ROOT)/m5out-$(SIM_TAG)/stat-$(1)-$(SIM_TAG).txt
endef

first-whetstone:
	$(call run_first,whetstone)

first-lbm:
	$(call run_first,lbm_s)

first-mcf:
	$(call run_first,mcf_s)

first-gcc:
	$(call run_first,gcc_s)

first-exchange2:
	$(call run_first,exchange2_s)

first-fotonik3d:
	$(call run_first,fotonik3d_s)

first-nab:
	$(call run_first,nab_s)

first-x264:
	$(call run_first,x264_s)

first-perlbench:
	$(call run_first,perlbench_s)

first-leela:
	$(call run_first,leela_s)

first-deepsjeng:
	$(call run_first,deepsjeng_s)

first-bwaves:
	$(call run_first,bwaves_s)

first-par: first-whetstone first-lbm first-mcf first-gcc \
           first-exchange2 first-fotonik3d first-nab first-x264 \
           first-perlbench first-leela first-deepsjeng first-bwaves
	@cat $(M5OUT_ROOT)/m5out-$(SIM_TAG)/stat-whetstone-$(SIM_TAG).txt \
	     $(M5OUT_ROOT)/m5out-$(SIM_TAG)/stat-lbm_s-$(SIM_TAG).txt \
	     $(M5OUT_ROOT)/m5out-$(SIM_TAG)/stat-mcf_s-$(SIM_TAG).txt \
	     $(M5OUT_ROOT)/m5out-$(SIM_TAG)/stat-gcc_s-$(SIM_TAG).txt \
	     $(M5OUT_ROOT)/m5out-$(SIM_TAG)/stat-exchange2_s-$(SIM_TAG).txt \
	     $(M5OUT_ROOT)/m5out-$(SIM_TAG)/stat-fotonik3d_s-$(SIM_TAG).txt \
	     $(M5OUT_ROOT)/m5out-$(SIM_TAG)/stat-nab_s-$(SIM_TAG).txt \
	     $(M5OUT_ROOT)/m5out-$(SIM_TAG)/stat-x264_s-$(SIM_TAG).txt \
	     $(M5OUT_ROOT)/m5out-$(SIM_TAG)/stat-perlbench_s-$(SIM_TAG).txt \
	     $(M5OUT_ROOT)/m5out-$(SIM_TAG)/stat-leela_s-$(SIM_TAG).txt \
	     $(M5OUT_ROOT)/m5out-$(SIM_TAG)/stat-deepsjeng_s-$(SIM_TAG).txt \
	     $(M5OUT_ROOT)/m5out-$(SIM_TAG)/stat-bwaves_s-$(SIM_TAG).txt

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
IQ_FLAT_BENCHMARKS := whetstone lbm_s mcf_s gcc_s
# IQ_DIQ_CONFIGS := \
    32-0  32-10  32-20  32-30 \
    64-0  64-10  64-20  64-30 \
    96-0  96-10  96-20  96-30 \
    128-0 128-20 128-40 128-60 128-80 \
    160-0 160-20 160-40 160-60 160-80 \
    192-0 192-20 192-40 192-60 192-80 \
    224-0 224-20 224-40 224-60 224-80 \
    256-0 256-20 256-40 256-60 256-80 \
    280-0 280-20 280-40 280-60 280-80 280-100 280-120
IQ_DIQ_CONFIGS := \
           32-10  32-20  32-30  32-40  32-50  32-60  32-70  32-80  32-90  32-100  32-110  32-120  32-130 \
           64-10  64-20  64-30  64-40  64-50  64-60  64-70  64-80  64-90  64-100 \
     96-0  96-10  96-20  96-30  96-40  96-50  96-60  96-70 \
          128-10 128-20 128-30 128-40

define iq_flat_rule
iq-flat-$(1)-$(2): _TAG := $(_CTX_TAG)_iq$(word 1,$(subst -, ,$(2)))_diq$(word 2,$(subst -, ,$(2)))
iq-flat-$(1)-$(2):
	@mkdir -p $(M5OUT_ROOT)/m5out-$$(_TAG)/$(1)-$(2)
	@$(GEM5) --outdir=$(M5OUT_ROOT)/m5out-$$(_TAG)/$(1)-$(2) $(CONFIG) -b $(1) $(SLIM) \
	    --iq-size $(word 1,$(subst -, ,$(2))) \
	    --diq-size $(word 2,$(subst -, ,$(2))) \
	    $(CONFIG_ARGS)
	@{ echo "---------- Begin Simulation Statistics ----------"; \
	   echo "$(1) IQ=$(word 1,$(subst -, ,$(2))) DIQ=$(word 2,$(subst -, ,$(2))) SIM_TAG=$(word 1,$(subst -, ,$(2)))/$(word 2,$(subst -, ,$(2))) RUNTAG=$$(_TAG)"; \
	   echo "----------"; \
	   $(META_STATS_GREP) $(M5OUT_ROOT)/m5out-$$(_TAG)/$(1)-$(2)/stats.txt; \
	   echo; \
	   $(STATS_GREP) $(M5OUT_ROOT)/m5out-$$(_TAG)/$(1)-$(2)/stats.txt; \
	   echo "---------- End Simulation Statistics ----------"; \
	   echo; \
	} > $(M5OUT_ROOT)/m5out-$$(_TAG)/stat-$(1)-$$(_TAG).txt
endef

$(foreach cfg,$(IQ_DIQ_CONFIGS),\
    $(foreach bench,$(IQ_FLAT_BENCHMARKS),\
        $(eval $(call iq_flat_rule,$(bench),$(cfg)))))

IQ_FLAT_TARGETS := $(foreach cfg,$(IQ_DIQ_CONFIGS),\
    $(foreach bench,$(IQ_FLAT_BENCHMARKS),iq-flat-$(bench)-$(cfg)))

.PHONY: $(IQ_FLAT_TARGETS)

sweep-iq-flat: $(IQ_FLAT_TARGETS)
	@$(MAKE) collect-iq-results

# Optional filters for collect-iq-results
_CFILTER :=
_CFILTER += $(if $(filter command line,$(origin SLIM)),$(_TAG_BASE))
_CFILTER += $(if $(filter     1,$(SUPER)),_super)
_CFILTER += $(if $(filter-out 0,$(WARMUP)),_warm$(WARMUP))
_CFILTER += $(if $(filter-out 0,$(O3WARMUP)),_o3warm$(O3WARMUP))
_CFILTER += $(if $(filter     1,$(ZLAT)),_zl)
_CFILTER += $(if $(filter     1,$(USE_DEF)),_def)
_CFILTER += $(if $(ONLY_DIQ),_diq$(ONLY_DIQ)/)
_CFILTER += $(if $(ONLY_IQ),_iq$(ONLY_IQ)_)
_CFILTER_PIPE = $(foreach f,$(_CFILTER), | grep '$(f)')

_CFILTER_EXCL :=
_CFILTER_EXCL += $(if $(filter command line,$(origin USE_DEF)),$(if $(filter 0,$(USE_DEF)),_def))
_CFILTER_EXCL += $(if $(filter command line,$(origin SUPER)),$(if $(filter 0,$(SUPER)),_super))
_CFILTER_EXCL += $(if $(filter command line,$(origin ZLAT)),$(if $(filter 0,$(ZLAT)),_zl))
_CFILTER_EXCL += $(if $(filter command line,$(origin WARMUP)),$(if $(filter 0,$(WARMUP)),_warm))
_CFILTER_EXCL += $(if $(filter command line,$(origin O3WARMUP)),$(if $(filter 0,$(O3WARMUP)),_o3warm))
_CFILTER_EXCL_PIPE = $(foreach f,$(_CFILTER_EXCL), | grep -v '$(f)')

#make collect-iq-results SLIM="" SUPER=1 WARMUP=100M O3WARMUP=100M ZLAT=0 USE_DEF=1
collect-iq-results:
	@rm -f iq-sweep-all.txt
	$(if $(_CFILTER),@echo "Include:$(_CFILTER)")
	$(if $(_CFILTER_EXCL),@echo "Exclude:$(_CFILTER_EXCL)")
	@find $(M5OUT_ROOT) -maxdepth 2 -name "stat-*.txt"$(_CFILTER_PIPE)$(_CFILTER_EXCL_PIPE) | sort | xargs cat >> iq-sweep-all.txt
	@echo "Results written to iq-sweep-all.txt"

PLOT_SCRIPT := python plot_ipc/plot_ipc.py

plots:
	@echo "Generating all plots..."
	@$(PLOT_SCRIPT) --downgrade  -s
	@$(PLOT_SCRIPT) --split      -s
	@$(PLOT_SCRIPT) --budget     -s
	@$(PLOT_SCRIPT) --iq-groups  -s
	@$(PLOT_SCRIPT) --table      -s
	@$(PLOT_SCRIPT) --bar        -s
	@$(PLOT_SCRIPT)              -s
	@echo "All plots saved to plot_ipc/"
