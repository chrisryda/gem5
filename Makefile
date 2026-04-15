.PHONY: check prepro_simr prepro_sims corr first \
        first-whetstone first-lbm first-mcf first-gcc \
        first-perlbench first-bwaves first-cactuBSSN first-omnetpp \
        first-par rebuild-benchmarks

check:
	@echo "Running correctness check (hello_world)..."
	@./build/ARM/gem5.opt configs/sic_parvis_magna/magna.py -b hello_world -t 1B > corr-test.txt 2>&1
	@cat corr-test.txt | grep -q "Hello world!" \
		&& echo "Correctness check passed." \
		|| (echo "CORRECTNESS CHECK FAILED" >&2; exit 1)
	@rm corr-test.txt

PREPRO_SIMR_BENCHES := whetstone lbm_r mcf_r gcc_r
PREPRO_SIMS_BENCHES := whetstone lbm_s mcf_s gcc_s

prepro_simr: check
	@for bench in $(PREPRO_SIMR_BENCHES); do \
		$(GEM5) $(MAGNA) -b $$bench -t 100B; \
		mv dist_dependencies_xx100B.csv dist_dependencies_$${bench}100B.csv; \
	done
	mv dist_dependencies* plot_dependencies/stats

prepro_sims: check
	@for bench in $(PREPRO_SIMS_BENCHES); do \
		$(GEM5) $(MAGNA) -b $$bench -t 100B; \
		mv dist_dependencies_xx100B.csv dist_dependencies_$${bench}100B.csv; \
	done
	mv dist_dependencies* plot_dependencies/stats

# Individual targets for parallel execution: make check && make -j4 first-par
# Pass SIM_LIMIT to control simulation length, e.g.: make first-par SIM_LIMIT="-c 5M"
GEM5 := ./build/ARM/gem5.opt
MAGNA := configs/sic_parvis_magna/magna.py
META_STATS_GREP := grep -e "hostSeconds" -e "simSeconds" -e "simTicks" -e "core.numCycles" -e "simInsts"
STATS_GREP := grep -e "core.cpi" -e "core.ipc" -e "instsAdded" -e "deltaInstsAdded" -e "iqFullEvents"
SIM_LIMIT ?= -t 100B

define run_first
	@$(GEM5) --outdir=m5out-$(1) $(MAGNA) -b $(1) $(SIM_LIMIT)
	@{ echo "---------- Begin Simulation Statistics ----------"; \
	   echo "$(1) $(SIM_LIMIT)"; \
	   echo "----------"; \
	   $(META_STATS_GREP) m5out-$(1)/stats.txt; \
	   echo; \
	   $(STATS_GREP) m5out-$(1)/stats.txt; \
	   echo "---------- End Simulation Statistics ----------"; \
	   echo; \
	} > first-$(1).txt
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
	@cat first-whetstone.txt first-lbm_s.txt first-mcf_s.txt first-gcc_s.txt > first.txt
	@cat first.txt

# Benchmarks with rebuild: clean all in their Makefiles
BENCH_SRCDIRS := tests/test-progs/605.mcf_s/src tests/test-progs/619.lbm_s/src

# gcc_s uses a raw build script (no proper Makefile), handled separately
GCC_S_DIR := tests/test-progs/602.gcc_s/src

rebuild-benchmarks:
	@echo "Rebuilding simsim (whetstone, simple_for)..."
	@$(MAKE) -C tests/test-progs/simsim clean
	@$(MAKE) -C tests/test-progs/simsim bins
	@for dir in $(BENCH_SRCDIRS); do \
		echo "Rebuilding $$dir..."; \
		$(MAKE) -C $$dir rebuild; \
	done
	@echo "Rebuilding gcc_s (602.gcc_s via simple-build script)..."
	@find $(GCC_S_DIR) -name "*.o" -delete
	@rm -f $(GCC_S_DIR)/sgcc
	@cd $(GCC_S_DIR) && bash simple-build-sgcc-602.sh
	@echo "All benchmarks rebuilt."
