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

prepro_simr: check
	./build/ARM/gem5.opt configs/sic_parvis_magna/magna.py -b whetstone -t 100B
	mv dist_dependencies_xx100B.csv dist_dependencies_whet100B.csv
	./build/ARM/gem5.opt configs/sic_parvis_magna/magna.py -b lbm_r -t 100B
	mv dist_dependencies_xx100B.csv dist_dependencies_lbm_r100B.csv
	./build/ARM/gem5.opt configs/sic_parvis_magna/magna.py -b mcf_r -t 100B
	mv dist_dependencies_xx100B.csv dist_dependencies_mcf_r100B.csv
	./build/ARM/gem5.opt configs/sic_parvis_magna/magna.py -b gcc_r -t 100B
	mv dist_dependencies_xx100B.csv dist_dependencies_lbm_r100B.csv
	mv dist_dependencies* plot_dependencies/stats

prepro_sims: check
	./build/ARM/gem5.opt configs/sic_parvis_magna/magna.py -b whetstone -t 100B
	mv dist_dependencies_xx100B.csv dist_dependencies_whet100B.csv
	./build/ARM/gem5.opt configs/sic_parvis_magna/magna.py -b lbm_s -t 100B
	mv dist_dependencies_xx100B.csv dist_dependencies_lbm_s100B.csv
	./build/ARM/gem5.opt configs/sic_parvis_magna/magna.py -b mcf_s -t 100B
	mv dist_dependencies_xx100B.csv dist_dependencies_mcf_s100B.csv
	./build/ARM/gem5.opt configs/sic_parvis_magna/magna.py -b gcc_s -t 100B
	mv dist_dependencies_xx100B.csv dist_dependencies_gcc_s100B.csv
	mv dist_dependencies* plot_dependencies/stats

BENCHMARKS := whetstone lbm_s mcf_s gcc_s perlbench_s bwaves_s cactuBSSN_s omnetpp_s

first: check
	@> first.txt
	@for bench in $(BENCHMARKS); do \
		./build/ARM/gem5.opt configs/sic_parvis_magna/magna.py --outdir=m5out-$$bench -b $$bench -t 100B; \
		echo "---------- Begin Simulation Statistics ----------" >> first.txt; \
		echo "$$bench 100B" >> first.txt; \
		grep -e "simSeconds" -e "simInsts" -e "core.cpi" -e "instsAdded" -e "deltaInstsAdded" -e "iqFullEvents" m5out-$$bench/stats.txt >> first.txt; \
		echo -e "---------- End Simulation Statistics ----------\n" >> first.txt; \
	done
	@cat first.txt

# Individual targets for parallel execution: make check && make -j4 first-par
GEM5 := ./build/ARM/gem5.opt
MAGNA := configs/sic_parvis_magna/magna.py
STATS_GREP := grep -e "simSeconds" -e "simInsts" -e "core.cpi" -e "instsAdded" -e "deltaInstsAdded" -e "iqFullEvents"

define run_first
	@$(GEM5) --outdir=m5out-$(1) $(MAGNA) -b $(1) -t 1B
	@{ echo "---------- Begin Simulation Statistics ----------"; \
	   echo "$(1) 100B"; \
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

first-perlbench:
	$(call run_first,perlbench_s)

first-bwaves:
	$(call run_first,bwaves_s)

first-cactuBSSN:
	$(call run_first,cactuBSSN_s)

first-omnetpp:
	$(call run_first,omnetpp_s)

first-par: first-whetstone first-lbm first-mcf first-gcc \
           first-perlbench first-bwaves first-cactuBSSN first-omnetpp
	@cat first-whetstone.txt first-lbm_s.txt first-mcf_s.txt first-gcc_s.txt \
	     first-perlbench_s.txt first-bwaves_s.txt first-cactuBSSN_s.txt first-omnetpp_s.txt \
	     > first.txt
	@cat first.txt

# Benchmarks with rebuild: clean all in their Makefiles
BENCH_SRCDIRS := \
    tests/test-progs/600.perlbench_s/src \
    tests/test-progs/603.bwaves_s/src \
    tests/test-progs/605.mcf_s/src \
    tests/test-progs/607.cactuBSSN_s/src \
    tests/test-progs/619.lbm_s/src \
    tests/test-progs/620.omnetpp_s/src

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

