import os
import argparse
from sic_parvis import Magna, MagnaOpus, SuperMagnaOpus, IceLakeCacheHierarchy

from gem5.isas import ISA
from gem5.simulate.simulator import Simulator
from gem5.resources.resource import BinaryResource

from gem5.components.boards.simple_board import SimpleBoard
from gem5.components.memory import SingleChannelDDR4_2400
from gem5.components.memory.simple import SingleChannelSimpleMemory

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
parser.add_argument("--zero-lat", action="store_true", default=False, help="Use 1-cycle cache latencies and near-zero DRAM latency to isolate IQ bottleneck")
parser.add_argument("--super", dest="super_mode", action="store_true", default=False, help="Use over-provisioned processor (wide pipeline, large ROB/LSQ/regfile) to isolate IQ as bottleneck")
args = parser.parse_args()

if args.super_mode:
    processor = SuperMagnaOpus(iq_size=args.iq_size, diq_size=args.diq_size)
    proc_name = "Super MO"
else:
    processor = MagnaOpus(iq_size=args.iq_size, diq_size=args.diq_size)
    proc_name = "MagnaOpus"
if args.zero_lat:
    memory = SingleChannelSimpleMemory(latency="1ns", latency_var="0ns", bandwidth="1TiB/s", size="16GiB")
else:
    memory = SingleChannelDDR4_2400(size="16GiB")
cache_hierarchy = IceLakeCacheHierarchy(zero_lat=args.zero_lat)

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
test_dir = f"{home}/nec/gem5/tests/ma-benchs" if "crd" in home else f"{home}/gem5/tests/ma-benchs"
match binary:
    case "hello_world":
        binary_path = f"{test_dir.removesuffix('/ma-benchs')}/test-progs/hello/bin/arm/linux/hello"
        binary_args = []
    case "whetstone":
        binary_path = f"{test_dir}/whetstone/whetstone"
        binary_args = ["-c", "10000000000"]
    case "lbm_s": #src folder copied from 519.lbm_r
        binary_path = f"{test_dir}/619.lbm_s/lbm_s"
        binary_args = ["2000", "reference.dat", "0", "0", f"{test_dir}/619.lbm_s/data/refspeed/input/200_200_260_ldc.of"]
    case "mcf_s": # src and data folders copied from 505.mcf_r
        binary_path = f"{test_dir}/605.mcf_s/mcf_s"
        binary_args = [f"{test_dir}/605.mcf_s/data/refspeed/input/inp.in"]
    case "gcc_s": # src and data folders copied from 502.gcc_r
        binary_path = f"{test_dir}/602.gcc_s/sgcc"
        binary_args = [f"{test_dir}/602.gcc_s/data/refspeed/input/gcc-pp.c"]

board.set_se_binary_workload(binary=BinaryResource(binary_path), arguments=binary_args)
simulator = Simulator(board=board)
print(f"Running benchmark {binary} for {sim_desc} with {proc_name}, IQ = {args.iq_size} and DIQ = {args.diq_size}\n")

# simulator.schedule_max_insts(1_000_000_000)
# simulator.run()
simulator.run(num_ticks)

print(f"{binary} ran a total of {simulator.get_current_tick()} simulated ticks on {proc_name} with IQ = {args.iq_size} and DIQ = {args.diq_size}")
