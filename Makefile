simr:
	./build/ARM/gem5.opt configs/sic_parvis_magna/magna.py -b whetstone -t 100B 
	mv dist_dependencies_xx100B.csv dist_dependencies_whet100B.csv
	./build/ARM/gem5.opt configs/sic_parvis_magna/magna.py -b lbm_r -t 100B
	mv dist_dependencies_xx100B.csv dist_dependencies_lbm_r100B.csv
	./build/ARM/gem5.opt configs/sic_parvis_magna/magna.py -b mcf_r -t 100B
	mv dist_dependencies_xx100B.csv dist_dependencies_mcf_r100B.csv
	./build/ARM/gem5.opt configs/sic_parvis_magna/magna.py -b gcc_r -t 100B
	mv dist_dependencies_xx100B.csv dist_dependencies_lbm_r100B.csv
	mv dist_dependencies* plot_dependencies/stats

sims:
	./build/ARM/gem5.opt configs/sic_parvis_magna/magna.py -b whetstone -t 100B 
	mv dist_dependencies_xx100B.csv dist_dependencies_whet100B.csv
	./build/ARM/gem5.opt configs/sic_parvis_magna/magna.py -b lbm_s -t 100B
	mv dist_dependencies_xx100B.csv dist_dependencies_lbm_s100B.csv
	./build/ARM/gem5.opt configs/sic_parvis_magna/magna.py -b mcf_s -t 100B
	mv dist_dependencies_xx100B.csv dist_dependencies_mcf_s100B.csv
	./build/ARM/gem5.opt configs/sic_parvis_magna/magna.py -b gcc_s -t 100B
	mv dist_dependencies_xx100B.csv dist_dependencies_gcc_s100B.csv
	mv dist_dependencies* plot_dependencies/stats 