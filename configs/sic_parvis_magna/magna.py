from sic_parvis import Magna

from gem5.isas import ISA
from gem5.simulate.simulator import Simulator
from gem5.resources.resource import BinaryResource

from gem5.components.boards.simple_board import SimpleBoard
from gem5.components.memory import SingleChannelDDR3_1600
from gem5.components.cachehierarchies.classic.no_cache import NoCache
from gem5.components.processors.cpu_types import CPUTypes
from gem5.components.processors.simple_switchable_processor import SimpleSwitchableProcessor

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

binary = "/home/crd/nec/gem5/tests/test-progs/simsim/bin/simple_for"
# binary = "/home/crd/nec/gem5/tests/test-progs/simsim/bin/whetstone"
# binary = "/home/crd/nec/gem5/tests/test-progs/lbm/program"

args = []
# args = ["64", "reference.dat", "0", "1", "/home/crd/nec/gem5/tests/test-progs/lbm/100_100_130_cf_a.of"]

board.set_se_binary_workload(binary=BinaryResource(binary), arguments=args)

simulator = Simulator(board=board)
simulator.run()

print(f"Ran a total of {simulator.get_current_tick()} simulated ticks")
