.PHONY: check \
        first-whetstone first-lbm first-mcf first-gcc \
        first-exchange2 first-fotonik3d first-nab first-x264 \
        first-perlbench first-leela first-deepsjeng first-bwaves \
        first-cactubssn first-omnetpp first-wrf first-xalancbmk \
        first-cam4 first-pop2 first-imagick first-roms first-xz \
        sweep-iq-flat collect-iq-results collect-deps collect-outstanding \
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
#   OT       : collect-* filter only — 1 = match only overtime (ot-) sweep
#              dirs; 0 (passed explicitly) = exclude them
#   LIM      : collect-* filter only — 1 = match only single-consumer-limited
#              (lim-) sweep dirs; 0 (passed explicitly) = exclude them
# ---------------------------------------------------------------------------
SLIM     ?= -t 100B
ZLAT     ?= 0
SUPER    ?= 0
WARMUP   ?= 0
O3WARMUP ?= 0
USE_DEF  ?= 0
OT       ?= 0
LIM      ?= 0

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

first-cactubssn:
	$(call run_first,cactuBSSN_s)

first-omnetpp:
	$(call run_first,omnetpp_s)

first-wrf:
	$(call run_first,wrf_s)

first-xalancbmk:
	$(call run_first,xalancbmk_s)

first-cam4:
	$(call run_first,cam4_s)

first-pop2:
	$(call run_first,pop2_s)

first-imagick:
	$(call run_first,imagick_s)

first-roms:
	$(call run_first,roms_s)

first-xz:
	$(call run_first,xz_s)

# ---------------------------------------------------------------------------
# IQ/DIQ sweep  (make sweep-iq-flat [-jN] [options])
#
# Each (benchmark × IQ/DIQ config) pair is an independent PHONY target so
# make -jN can schedule them in parallel.
#
# ---------------------------------------------------------------------------

# Configs to sweep: space-separated IQ-DIQ pairs
# IQ_FLAT_BENCHMARKS := whetstone lbm_s mcf_s gcc_s
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
_CFILTER += $(if $(filter     1,$(OT)),ot-)
_CFILTER += $(if $(filter     1,$(LIM)),lim-)
_CFILTER_PIPE = $(foreach f,$(_CFILTER), | grep '$(f)')

_CFILTER_EXCL :=
_CFILTER_EXCL += $(if $(filter command line,$(origin USE_DEF)),$(if $(filter 0,$(USE_DEF)),_def))
_CFILTER_EXCL += $(if $(filter command line,$(origin SUPER)),$(if $(filter 0,$(SUPER)),_super))
_CFILTER_EXCL += $(if $(filter command line,$(origin ZLAT)),$(if $(filter 0,$(ZLAT)),_zl))
_CFILTER_EXCL += $(if $(filter command line,$(origin WARMUP)),$(if $(filter 0,$(WARMUP)),_warm))
_CFILTER_EXCL += $(if $(filter command line,$(origin O3WARMUP)),$(if $(filter 0,$(O3WARMUP)),_o3warm))
_CFILTER_EXCL += $(if $(filter command line,$(origin OT)),$(if $(filter 0,$(OT)),ot-))
_CFILTER_EXCL += $(if $(filter command line,$(origin LIM)),$(if $(filter 0,$(LIM)),lim-))
_CFILTER_EXCL_PIPE = $(foreach f,$(_CFILTER_EXCL), | grep -v '$(f)')

#make collect-iq-results SLIM="" SUPER=1 WARMUP=100M O3WARMUP=100M ZLAT=0 USE_DEF=1
collect-iq-results:
	@rm -f iq-sweep-all.txt
	$(if $(_CFILTER),@echo "Include:$(_CFILTER)")
	$(if $(_CFILTER_EXCL),@echo "Exclude:$(_CFILTER_EXCL)")
	@find $(M5OUT_ROOT) -maxdepth 2 -name "stat-*.txt"$(_CFILTER_PIPE)$(_CFILTER_EXCL_PIPE) | sort | xargs cat >> iq-sweep-all.txt
	@echo "Results written to iq-sweep-all.txt"

# ---------------------------------------------------------------------------
# Dependency-distance collection  (make collect-deps)
#   Gathers every dist_dependencies.csv from the IQ=160 sims into one combined
#   CSV (bench,delta,num) for cross-benchmark plotting.  Filtered like a
#   simplified collect-iq-results: SLIM selects the simulation length and
#   SUPER selects/excludes the over-provisioned runs.  Filters should narrow
#   the match to a single run, otherwise benchmarks get duplicated.
# ---------------------------------------------------------------------------
DEPS_OUT := plot_dependencies/stats/dist_dependencies_all160.csv

# Optional filters for collect-deps
_DFILTER :=
_DFILTER += $(if $(filter command line,$(origin SLIM)),$(_TAG_BASE))
_DFILTER += $(if $(filter     1,$(SUPER)),_super)
_DFILTER += $(if $(filter     1,$(OT)),ot-)
_DFILTER += $(if $(filter     1,$(LIM)),lim-)
_DFILTER_PIPE = $(foreach f,$(_DFILTER), | grep '$(f)')

_DFILTER_EXCL :=
_DFILTER_EXCL += $(if $(filter command line,$(origin SUPER)),$(if $(filter 0,$(SUPER)),_super))
_DFILTER_EXCL += $(if $(filter command line,$(origin OT)),$(if $(filter 0,$(OT)),ot-))
_DFILTER_EXCL += $(if $(filter command line,$(origin LIM)),$(if $(filter 0,$(LIM)),lim-))
_DFILTER_EXCL_PIPE = $(foreach f,$(_DFILTER_EXCL), | grep -v '$(f)')

#make collect-deps SLIM="-c 500M" SUPER=0 OT=1
collect-deps:
	$(if $(_DFILTER),@echo "Include:$(_DFILTER)")
	$(if $(_DFILTER_EXCL),@echo "Exclude:$(_DFILTER_EXCL)")
	@echo "bench,delta,num" > $(DEPS_OUT)
	@files=$$(find $(M5OUT_ROOT) -maxdepth 3 -name "dist_dependencies.csv"$(_DFILTER_PIPE)$(_DFILTER_EXCL_PIPE) | sort); \
	for f in $$files; do \
	    bench=$$(basename $$(dirname $$f) | sed 's/-[0-9]*-[0-9]*$$//'); \
	    tail -n +2 "$$f" | sed "s/^/$$bench,/" >> $(DEPS_OUT); \
	done; \
	echo "Combined $$(echo "$$files" | grep -c .) benchmark CSVs into $(DEPS_OUT)"
	@awk -F, 'NR>1 && ++c[$$1","$$2]==2 {d++} END {if (d) print "WARNING: "d" duplicate (bench,delta) pairs - filters match more than one run, add SLIM=/SUPER="}' $(DEPS_OUT)

# ---------------------------------------------------------------------------
# Outstanding-source collection  (make collect-outstanding)
#   Gathers every dist_outstanding_srcs.csv into one combined CSV
#   (bench,outstanding_srcs,num_insts; counted at RENAME, once per renamed inst)
#   for cross-benchmark plotting, then appends suite-average rows per k as
#   PERCENTAGES (value in the num_insts column is a percent for those rows):
#     pooled_pct / arithmean_pct / geomean_pct          - over ALL renamed insts
#     *_nonready                                         - over non-ready (k>=1) insts only
#   This CSV is emitted ONLY by the IQ=160/DIQ=0 baseline sims (the DIQ
#   characterization gate), so a bare run already matches just those.  Filtered
#   like collect-deps (SLIM selects the simulation length, SUPER selects/excludes
#   the over-provisioned runs) to disambiguate when several 160/0 sweeps coexist.
# ---------------------------------------------------------------------------
SRCS_OUT := plot_dependencies/stats/dist_outstanding_srcs_all160.csv

#make collect-outstanding SLIM="-c 500M" SUPER=0 OT=1
collect-outstanding:
	$(if $(_DFILTER),@echo "Include:$(_DFILTER)")
	$(if $(_DFILTER_EXCL),@echo "Exclude:$(_DFILTER_EXCL)")
	@echo "bench,outstanding_srcs,num_insts" > $(SRCS_OUT)
	@files=$$(find $(M5OUT_ROOT) -maxdepth 3 -name "dist_outstanding_srcs.csv"$(_DFILTER_PIPE)$(_DFILTER_EXCL_PIPE) | sort); \
	for f in $$files; do \
	    bench=$$(basename $$(dirname $$f) | sed 's/-[0-9]*-[0-9]*$$//'); \
	    tail -n +2 "$$f" | sed "s/^/$$bench,/" >> $(SRCS_OUT); \
	done; \
	echo "Combined $$(echo "$$files" | grep -c .) benchmark CSVs into $(SRCS_OUT)"
	@awk -F, 'NR>1 && ++c[$$1","$$2]==2 {d++} END {if (d) print "WARNING: "d" duplicate (bench,k) pairs - filters match more than one run, add SLIM=/SUPER="}' $(SRCS_OUT)
	@# Append suite-average rows per k, as PERCENTAGES (not counts), for two
	@# denominators: *_pct over ALL renamed insts, *_nonready over the non-ready
	@# (k>=1) subset.  pooled = instruction-weighted (sum counts / total);
	@# arithmean = mean of per-bench shares (equal weight, zeros included);
	@# geomean = geomean of per-bench shares (zeros skipped, to match plot_dep.py).
	@awk -F, 'NR>1 && $$1!="pooled_pct" && $$1!="arithmean_pct" && $$1!="geomean_pct" && $$1!="pooled_pct_nonready" && $$1!="arithmean_pct_nonready" && $$1!="geomean_pct_nonready" {b=$$1;k=$$2+0;c=$$3+0;cnt[b","k]=c;tot[b]+=c;pool[k]+=c;grand+=c;if(!(b in B)){B[b]=1;nb++};K[k]=1} END {n=0;for(k in K)kk[n++]=k;for(i=1;i<n;i++){v=kk[i];j=i-1;while(j>=0&&kk[j]>v){kk[j+1]=kk[j];j--}kk[j+1]=v};gnr=grand-pool[0];for(b in B){c0=((b","0) in cnt)?cnt[b","0]:0;ds[b]=tot[b]-c0};for(i=0;i<n;i++){k=kk[i];printf "pooled_pct,%d,%.2f\n",k,100*pool[k]/grand};for(i=0;i<n;i++){k=kk[i];s=0;for(b in B){c=((b","k) in cnt)?cnt[b","k]:0;s+=100*c/tot[b]};printf "arithmean_pct,%d,%.2f\n",k,s/nb};for(i=0;i<n;i++){k=kk[i];gs=0;gn=0;for(b in B){c=((b","k) in cnt)?cnt[b","k]:0;sh=100*c/tot[b];if(sh>0){gs+=log(sh);gn++}};printf "geomean_pct,%d,%.2f\n",k,(gn>0)?exp(gs/gn):0};for(i=0;i<n;i++){k=kk[i];if(k<1)continue;printf "pooled_pct_nonready,%d,%.2f\n",k,100*pool[k]/gnr};for(i=0;i<n;i++){k=kk[i];if(k<1)continue;s=0;for(b in B){c=((b","k) in cnt)?cnt[b","k]:0;s+=(ds[b]>0)?100*c/ds[b]:0};printf "arithmean_pct_nonready,%d,%.2f\n",k,s/nb};for(i=0;i<n;i++){k=kk[i];if(k<1)continue;gs=0;gn=0;for(b in B){c=((b","k) in cnt)?cnt[b","k]:0;if(ds[b]>0){sh=100*c/ds[b];if(sh>0){gs+=log(sh);gn++}}};printf "geomean_pct_nonready,%d,%.2f\n",k,(gn>0)?exp(gs/gn):0}}' $(SRCS_OUT) > $(SRCS_OUT).means
	@cat $(SRCS_OUT).means >> $(SRCS_OUT) && rm -f $(SRCS_OUT).means
	@echo "Appended {pooled,arithmean,geomean}_pct[_nonready] percentage rows to $(SRCS_OUT)"

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
