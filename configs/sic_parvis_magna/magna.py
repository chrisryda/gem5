from sic_parvis import Magna
import argparse

from gem5.isas import ISA
from gem5.simulate.simulator import Simulator
from gem5.resources.resource import BinaryResource

from gem5.components.boards.simple_board import SimpleBoard
from gem5.components.memory import SingleChannelDDR3_1600
from gem5.components.cachehierarchies.classic.no_cache import NoCache
from gem5.components.processors.cpu_types import CPUTypes
from gem5.components.processors.simple_switchable_processor import SimpleSwitchableProcessor

def get_num_ticks(ticks : str) -> int:
    ticks = ticks.strip().upper()
    if ticks.endswith("M"):
        return int(float(ticks[:-1]) * 1_000_000)
    if ticks.endswith("B"):
        return int(float(ticks[:-1]) * 1_000_000_000)
    if ticks.isdigit():
        return int(ticks)
    raise ValueError(f"Unrecognized format: {ticks}")

processor = Magna()
memory = SingleChannelDDR3_1600(size="16GiB")
cache_hierarchy = NoCache()
    
# For fast-forwarding, might need it later  
# processor = SimpleSwitchableProcessor(
#     starting_core_type=CPUTypes.ATOMIC,
#     switch_core_type=CPUTypes.O3,
#     isa=ISA.ARM,
#     num_cores=1,
# )
# simulator.run(x) // processor.switch() // simulator.run(y)


board = SimpleBoard(
    clk_freq="2GHz",
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

match binary:
    case "simple_for":
        binary_path = "/home/crd/nec/gem5/tests/test-progs/simsim/bin/simple_for"
        args = []
    case "whetstone":
        binary_path = "/home/crd/nec/gem5/tests/test-progs/simsim/bin/whetstone"
        args = []
    case "lbm_r":
        binary_path = "/home/crd/nec/gem5/tests/test-progs/519.lbm_r/src/program"
        args = ["64", "reference.dat", "0", "1", "/home/crd/nec/gem5/tests/test-progs/519.lbm_r/data/refrate/input/100_100_130_ldc.of"]
    case "lbm_s": #src copied from 519.lbm_r
        binary_path = "/home/crd/nec/gem5/tests/test-progs/619.lbm_s/src/program"
        args = ["2000", "reference.dat", "0", "0", "/home/crd/nec/gem5/tests/test-progs/619.lbm_s/data/refspeed/input/200_200_260_ldc.of"]
    case "mcf_r":
        binary_path = "/home/crd/nec/gem5/tests/test-progs/505.mcf_r/src/program"
        args = ["/home/crd/nec/gem5/tests/test-progs/505.mcf_r/data/refrate/input/inp.in"]
    case "mcf_s": # src and data folders copied from 505.mcf_r
        binary_path = "/home/crd/nec/gem5/tests/test-progs/605.mcf_s/src/program"
        args = ["/home/crd/nec/gem5/tests/test-progs/605.mcf_s/data/refspeed/input/inp.in"]
    case "gcc_r":
        binary_path = "/home/crd/nec/gem5/tests/test-progs/502.gcc_r/src/cpugcc_r"
        args = ["/home/crd/nec/gem5/tests/test-progs/502.gcc_r/data/refrate/input/gcc-pp.c"]
    case "gcc_s": # src and data folders copied from 602.gcc_r
        binary_path = "/home/crd/nec/gem5/tests/test-progs/602.gcc_s/src/sgcc"
        args = ["/home/crd/nec/gem5/tests/test-progs/602.gcc_s/data/refspeed/input/gcc-pp.c"]

board.set_se_binary_workload(binary=BinaryResource(binary_path), arguments=args)
simulator = Simulator(board=board)
print(f"Running bencmark {binary} for {ticks} ticks\n")

# simulator.schedule_max_insts(1_000_000_000) 
# simulator.run()
simulator.run(get_num_ticks(ticks))

print(f"Ran a total of {simulator.get_current_tick()} simulated ticks")
