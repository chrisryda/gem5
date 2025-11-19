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
memory = SingleChannelDDR3_1600(size="32MiB")
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
    case "lbm":
        binary_path = "/home/crd/nec/gem5/tests/test-progs/lbm/program"
        args = ["64", "reference.dat", "0", "1", "/home/crd/nec/gem5/tests/test-progs/lbm/100_100_130_cf_a.of"]
    case "mcf":
        binary_path = "/home/crd/nec/gem5/tests/test-progs/505.mcf_r/src/program"
        args = ["/home/crd/nec/gem5/tests/test-progs/505.mcf_r/data/test/input/inp.in"]

board.set_se_binary_workload(binary=BinaryResource(binary_path), arguments=args)
simulator = Simulator(board=board)
print(f"Running bencmark {binary} for {ticks} ticks\n")

simulator.run(get_num_ticks(ticks))

print(f"Ran a total of {simulator.get_current_tick()} simulated ticks")
