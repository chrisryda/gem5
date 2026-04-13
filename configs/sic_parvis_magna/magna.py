import os
import argparse
from sic_parvis import Magna, MagnaOpus, IceLakeCacheHierarchy

from gem5.isas import ISA
from gem5.simulate.simulator import Simulator
from gem5.resources.resource import BinaryResource, FileResource

from gem5.components.boards.simple_board import SimpleBoard
# from gem5.components.memory import SingleChannelDDR3_1600
# from gem5.components.cachehierarchies.classic.no_cache import NoCache
from gem5.components.memory import SingleChannelDDR4_2400
# from gem5.components.processors.cpu_types import CPUTypes
# from gem5.components.processors.simple_switchable_processor import SimpleSwitchableProcessor

def get_num_ticks(ticks : str) -> int:
    ticks = ticks.strip().upper()
    if ticks.endswith("M"):
        return int(float(ticks[:-1]) * 1_000_000)
    if ticks.endswith("B"):
        return int(float(ticks[:-1]) * 1_000_000_000)
    if ticks.isdigit():
        return int(ticks)
    raise ValueError(f"Unrecognized format: {ticks}")

processor = MagnaOpus()
memory = SingleChannelDDR4_2400(size="16GiB")
cache_hierarchy = IceLakeCacheHierarchy()
    
# For fast-forwarding, might need it later  
# processor = SimpleSwitchableProcessor(
#     starting_core_type=CPUTypes.ATOMIC,
#     switch_core_type=CPUTypes.O3,
#     isa=ISA.ARM,
#     num_cores=1,
# )
# simulator.run(x) // processor.switch() // simulator.run(y)


board = SimpleBoard(
    clk_freq="3.3GHz",
    processor=processor,
    memory=memory,
    cache_hierarchy=cache_hierarchy,
)

parser = argparse.ArgumentParser()
parser.add_argument("-t", dest="ticks", type=str, help="The amount of ticks to simulate")
parser.add_argument("-b", dest="binary", type=str, help="The benchmark to run")
args = parser.parse_args()
ticks = args.ticks if args.ticks else "1M"
binary = args.binary if args.binary else "simple_for"
stdin_file = None

home = os.path.expanduser("~")
test_dir = f"{home}/nec/gem5/tests/test-progs" if "crd" in home else f"{home}/gem5/tests/test-progs"
match binary:
    case "hello_world":
        binary_path = f"{test_dir}/hello/bin/arm/linux/hello"
        args = []
    case "simple_for":
        binary_path = f"{test_dir}/simsim/bin/simple_for"
        args = []
    case "whetstone":
        binary_path = f"{test_dir}/simsim/bin/whetstone"
        args = []
    case "lbm_r":
        binary_path = f"{test_dir}/519.lbm_r/src/program"
        args = [
            "64", "reference.dat", "0", "1",
            f"{test_dir}/519.lbm_r/data/refrate/input/100_100_130_ldc.of"
        ]
    case "lbm_s": #src copied from 519.lbm_r
        binary_path = f"{test_dir}/619.lbm_s/src/program"
        args = [
            "2000", "reference.dat", "0", "0",
            f"{test_dir}/619.lbm_s/data/refspeed/input/200_200_260_ldc.of"
        ]
    case "mcf_r":
        binary_path = f"{test_dir}/505.mcf_r/src/program"
        args = [f"{test_dir}/505.mcf_r/data/refrate/input/inp.in"]
    case "mcf_s": # src and data folders copied from 505.mcf_r
        binary_path = f"{test_dir}/605.mcf_s/src/program"
        args = [f"{test_dir}/605.mcf_s/data/refspeed/input/inp.in"]
    case "gcc_r":
        binary_path = f"{test_dir}/502.gcc_r/src/cpugcc_r"
        args = [f"{test_dir}/502.gcc_r/data/refrate/input/gcc-pp.c"]
    case "gcc_s": # src and data folders copied from 602.gcc_r
        binary_path = f"{test_dir}/602.gcc_s/src/sgcc"
        args = [f"{test_dir}/602.gcc_s/data/refspeed/input/gcc-pp.c"]
    case "perlbench_s": # src already present, data in 600.perlbench_s
        binary_path = f"{test_dir}/600.perlbench_s/src/program"
        args = [
            f"-I{test_dir}/600.perlbench_s/data/all/input/lib",
            f"{test_dir}/600.perlbench_s/data/all/input/splitmail.pl", 
            "6400", "12", "26", "16", "100", "0"
        ]
    case "bwaves_s": # src already present, data in 603.bwaves_s
        binary_path = f"{test_dir}/603.bwaves_s/src/program"
        args = ["bwaves_1"]
        stdin_file = FileResource(f"{test_dir}/603.bwaves_s/data/refspeed/input/bwaves_1.in")
    case "cactuBSSN_s": # src already present, data in 607.cactuBSSN_s
        binary_path = f"{test_dir}/607.cactuBSSN_s/src/cactuBSSN_s"
        args = [f"{test_dir}/607.cactuBSSN_s/data/refspeed/input/spec_ref.par"]
    case "omnetpp_s": # src from 520.omnetpp_r, data from rate benchmark
        binary_path = f"{test_dir}/620.omnetpp_s/src/program"
        args = ["-c", "General", "-r", "0"]

board.set_se_binary_workload(binary=BinaryResource(binary_path), arguments=args, stdin_file=stdin_file) # type: ignore[arg-type]  
simulator = Simulator(board=board)
print(f"Running bencmark {binary} for {ticks} ticks\n")

# simulator.schedule_max_insts(1_000_000_000) 
# simulator.run()
simulator.run(get_num_ticks(ticks))

print(f"Ran a total of {simulator.get_current_tick()} simulated ticks")
