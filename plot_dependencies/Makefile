hists_r:
	python plot_dep.py -f whet100B  -histv -x 100 -y 4000000 -s
	python plot_dep.py -f gcc_r100B -histv -x 100 -y 4000000 -s
	python plot_dep.py -f mcf_r100B -histv -x 100 -y 4000000 -s
	python plot_dep.py -f lbm_r100B -histv -x 100 -y 4000000 -s

cumuls_r:
	python plot_dep.py -f whet100B  -cumul -x 100 -s
	python plot_dep.py -f gcc_r100B -cumul -x 100 -s
	python plot_dep.py -f mcf_r100B -cumul -x 100 -s
	python plot_dep.py -f lbm_r100B -cumul -x 100 -s

hists_s:
	python plot_dep.py -f whet100B  -histv -x 100 -y 4000000 -s
	python plot_dep.py -f gcc_s100B -histv -x 100 -y 4000000 -s
	python plot_dep.py -f mcf_s100B -histv -x 100 -y 4000000 -s
	python plot_dep.py -f lbm_s100B -histv -x 100 -y 4000000 -s

cumuls_s:
	python plot_dep.py -f whet100B  -cumul -x 100 -s
	python plot_dep.py -f gcc_s100B -cumul -x 100 -s
	python plot_dep.py -f mcf_s100B -cumul -x 100 -s
	python plot_dep.py -f lbm_s100B -cumul -x 100 -s

diffhists_r_art: 
	python plot_diff.py -f1 whet100B  -f2 whet_art100B -histv -x 100 -s
	python plot_diff.py -f1 gcc_r100B -f2 gcc_art100B  -histv -x 100 -s
	python plot_diff.py -f1 mcf_r100B -f2 mcf_art100B  -histv -x 100 -s
	python plot_diff.py -f1 lbm_r100B -f2 lbm_art100B  -histv -x 100 -s

diffcumuls_r_art:
	python plot_diff.py -f1 whet100B  -f2 whet_art100B -cumul -x 100 -s
	python plot_diff.py -f1 gcc_r100B -f2 gcc_art100B  -cumul -x 100 -s
	python plot_diff.py -f1 mcf_r100B -f2 mcf_art100B  -cumul -x 100 -s
	python plot_diff.py -f1 lbm_r100B -f2 lbm_art100B  -cumul -x 100 -s

diffhists_r_s: 
	python plot_diff.py -f1 gcc_r100B -f2 gcc_s100B -histv -x 100 -s
	python plot_diff.py -f1 mcf_r100B -f2 mcf_s100B -histv -x 100 -s
	python plot_diff.py -f1 lbm_r100B -f2 lbm_s100B -histv -x 100 -s

diffcumuls_r_s:
	python plot_diff.py -f1 gcc_r100B -f2 gcc_s100B -cumul -x 100 -s
	python plot_diff.py -f1 mcf_r100B -f2 mcf_s100B -cumul -x 100 -s
	python plot_diff.py -f1 lbm_r100B -f2 lbm_s100B -cumul -x 100 -s