from sic_parvis import Magna

from gem5.components.boards.simple_board import SimpleBoard
from gem5.components.cachehierarchies.classic.no_cache import NoCache
from gem5.components.memory import SingleChannelDDR3_1600
from gem5.resources.resource import BinaryResource
from gem5.simulate.simulator import Simulator

processor = Magna()
memory = SingleChannelDDR3_1600(size="32MiB")
cache_hierarchy = NoCache()

board = SimpleBoard(
    clk_freq="2GHz",
    processor=processor,
    memory=memory,
    cache_hierarchy=cache_hierarchy,
)

binary = "/home/crd/nec/gem5/tests/test-progs/simsim/bin/simple_for"
board.set_se_binary_workload(BinaryResource(binary))

simulator = Simulator(board=board)
simulator.run()

print(f"Ran a total of {simulator.get_current_tick()} simulated ticks")
