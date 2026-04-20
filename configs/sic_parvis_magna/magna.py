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

CLK_GHZ = 3.3

def get_num_ticks(ticks: str) -> int:
    ticks = ticks.strip().upper()
    if ticks.endswith("M"):
        return int(float(ticks[:-1]) * 1_000_000)
    if ticks.endswith("B"):
        return int(float(ticks[:-1]) * 1_000_000_000)
    if ticks.isdigit():
        return int(ticks)
    raise ValueError(f"Unrecognized format: {ticks}")

def get_num_cycles(cycles: str) -> int:
    cycles = cycles.strip().upper()
    if cycles.endswith("M"):
        num = int(float(cycles[:-1]) * 1_000_000)
    elif cycles.endswith("B"):
        num = int(float(cycles[:-1]) * 1_000_000_000)
    elif cycles.isdigit():
        num = int(cycles)
    else:
        raise ValueError(f"Unrecognized format: {cycles}")
    ticks_per_cycle = round(1e12 / (CLK_GHZ * 1e9))
    return num * ticks_per_cycle

parser = argparse.ArgumentParser()
sim_limit = parser.add_mutually_exclusive_group()
sim_limit.add_argument("-t", dest="ticks", type=str, help="The amount of ticks to simulate")
sim_limit.add_argument("-c", dest="cycles", type=str, help="The amount of cycles to simulate")
parser.add_argument("-b", dest="binary", type=str, help="The benchmark to run")
parser.add_argument("--iq-size", type=int, default=120, help="Regular IQ entries")
parser.add_argument("--diq-size", type=int, default=40, help="Delta IQ entries")
args = parser.parse_args()

processor = MagnaOpus(iq_size=args.iq_size, diq_size=args.diq_size)
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
    clk_freq=f"{CLK_GHZ}GHz",
    processor=processor,
    memory=memory,
    cache_hierarchy=cache_hierarchy,
)

if args.cycles:
    num_ticks = get_num_cycles(args.cycles)
    sim_desc = f"{args.cycles} cycles"
else:
    ticks = args.ticks if args.ticks else "1M"
    num_ticks = get_num_ticks(ticks)
    sim_desc = f"{ticks} ticks"

binary = args.binary if args.binary else "hello_world"
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
        args = ["-c", "10000000000"]
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
        binary_path = f"{test_dir.removesuffix('/test-progs')}/ma-benchs/602.gcc_s/sgcc"
        args = [f"{test_dir.removesuffix('/test-progs')}/ma-benchs/602.gcc_s/data/refspeed/input/gcc-pp.c"]

board.set_se_binary_workload(binary=BinaryResource(binary_path), arguments=args)
simulator = Simulator(board=board)
print(f"Running benchmark {binary} for {sim_desc}\n")

# simulator.schedule_max_insts(1_000_000_000)
# simulator.run()
simulator.run(num_ticks)

print(f"{binary} ran a total of {simulator.get_current_tick()} simulated ticks with IQ = {args.iq_size} and DIQ = {args.diq_size}")
