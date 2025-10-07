from gem5.components.boards.simple_board import SimpleBoard
from gem5.components.cachehierarchies.classic.no_cache import NoCache
from gem5.components.memory import SingleChannelDDR3_1600
from gem5.components.processors.cpu_types import CPUTypes
from gem5.components.processors.simple_processor import SimpleProcessor
from gem5.isas import ISA
from gem5.resources.resource import obtain_resource
from gem5.simulate.simulator import Simulator
from gem5.utils.requires import requires

# This check ensures the gem5 binary is compiled to the ARM ISA target. If not,
# an exception will be thrown.
requires(isa_required=ISA.ARM)

# In this setup we don't have a cache. `NoCache` can be used for such setups.
cache_hierarchy = NoCache()

# We use a single channel DDR3_1600 memory system
memory = SingleChannelDDR3_1600(size="32MiB")

# We use a simple Timing processor with one core.
processor = SimpleProcessor(cpu_type=CPUTypes.O3, isa=ISA.ARM, num_cores=1)


# The gem5 library simple board which can be used to run simple SE-mode
# simulations.
board = SimpleBoard(
    clk_freq="3GHz",
    processor=processor,
    memory=memory,
    cache_hierarchy=cache_hierarchy,
)

# Here we set the workload. In this case we want to run a simple "Hello World!"
# program compiled to the ARM ISA. The `Resource` class will automatically
# download the binary from the gem5 Resources cloud bucket if it's not already
# present.
board.set_se_binary_workload(
    # The `Resource` class reads the `resources.json` file from the gem5
    # resources repository:
    # https://github.com/gem5/gem5-resources.
    # Any resource specified in this file will be automatically retrieved.
    # At the time of writing, this file is a WIP and does not contain all
    # resources. Jira ticket: https://gem5.atlassian.net/browse/GEM5-1096
    obtain_resource("arm-hello64-static", resource_version="1.0.0")
)

# Lastly we run the simulation.
simulator = Simulator(board=board)
simulator.run()

print(
    "Exiting @ tick {} because {}.".format(
        simulator.get_current_tick(), simulator.get_last_exit_event_cause()
    )
)
