import os
import argparse

import m5
from gem5.isas import ISA
from gem5.utils.requires import requires
from gem5.utils.override import overrides
from gem5.simulate.simulator import Simulator
from gem5.resources.resource import BinaryResource
from gem5.components.memory import SingleChannelDDR3_1600
from gem5.components.memory.simple import SingleChannelSimpleMemory
from gem5.components.processors.cpu_types import CPUTypes
from gem5.components.processors.simple_core import SimpleCore
from gem5.components.processors.simple_processor import SimpleProcessor
from gem5.components.processors.abstract_processor import AbstractProcessor
from gem5.components.processors.switchable_processor import SwitchableProcessor
from gem5.components.boards.mem_mode import MemMode
from gem5.components.boards.simple_board import SimpleBoard
from gem5.components.cachehierarchies.classic.private_l1_private_l2_cache_hierarchy import PrivateL1PrivateL2CacheHierarchy

CLK_GHZ = 3.3

def parse_count(s: str) -> int:
    s = s.strip().upper()
    if s.endswith("M"):
        return int(float(s[:-1]) * 1_000_000)
    if s.endswith("B"):
        return int(float(s[:-1]) * 1_000_000_000)
    if s.isdigit():
        return int(s)
    raise ValueError(f"Unrecognized format: {s}")

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


def _apply_super_params(cpu):
    cpu.fetchWidth = 10
    cpu.decodeWidth = 10
    cpu.renameWidth = 10
    cpu.dispatchWidth = 10
    cpu.issueWidth = 12
    cpu.wbWidth = 12
    cpu.commitWidth = 12
    cpu.numROBEntries = 1024
    cpu.LQEntries = 1024
    cpu.SQEntries = 1024
    cpu.numPhysIntRegs = 1024
    cpu.numPhysFloatRegs = 1024


class DefaultSwitchableProcessor(SwitchableProcessor):
    """ATOMIC warmup core --> simple O3 timing core."""

    def __init__(self, iq_size, diq_size, super_mode=False):
        self._start_key = "start"
        self._switch_key = "switch"
        self._current_is_start = True

        atomic_core = SimpleCore(cpu_type=CPUTypes.ATOMIC, core_id=0, isa=ISA.ARM)
        o3_core = SimpleCore(cpu_type=CPUTypes.O3, core_id=0, isa=ISA.ARM)
        o3_core.get_simobject().cpu_id = atomic_core.get_simobject().cpu_id
        o3_core.get_simobject().numIQEntries = iq_size
        o3_core.get_simobject().numDeltaIQEntries = diq_size
        if super_mode:
            _apply_super_params(o3_core.get_simobject())

        super().__init__(
            switchable_cores={
                self._start_key: [atomic_core],
                self._switch_key: [o3_core],
            },
            starting_cores=self._start_key,
        )

    @overrides(SwitchableProcessor)
    def incorporate_processor(self, board):
        super().incorporate_processor(board=board)
        board.set_mem_mode(MemMode.ATOMIC)

    @overrides(AbstractProcessor)
    def switch(self):
        if self._current_is_start:
            self._board.set_mem_mode(MemMode.TIMING)
            self.switch_to_processor(self._switch_key)
        else:
            self._board.set_mem_mode(MemMode.ATOMIC)
            self.switch_to_processor(self._start_key)
        self._current_is_start = not self._current_is_start


parser = argparse.ArgumentParser()
sim_limit = parser.add_mutually_exclusive_group()
sim_limit.add_argument("-t", dest="ticks", type=str, help="The amount of ticks to simulate")
sim_limit.add_argument("-c", dest="cycles", type=str, help="The amount of cycles to simulate")
parser.add_argument("-b", dest="binary", type=str, help="The benchmark to run")
parser.add_argument("--warmup-insts", type=str, default="0", help="Instructions to fast-forward in ATOMIC mode before timing measurement (e.g. 100M, 1B)")
parser.add_argument("--iq-size", type=int, default=64, help="Number of IQ entries")
parser.add_argument("--diq-size", type=int, default=0, help="Number of Delta IQ entries")
parser.add_argument("--zero-lat", action="store_true", default=False, help="Use near-zero DRAM latency to isolate IQ bottleneck")
parser.add_argument("--super", dest="super_mode", action="store_true", default=False, help="Use over-provisioned processor (wide pipeline, large ROB/LSQ/regfile) to isolate IQ as bottleneck")
args = parser.parse_args()
warmup_insts = parse_count(args.warmup_insts)

requires(isa_required=ISA.ARM)

cache_hierarchy = PrivateL1PrivateL2CacheHierarchy(
    l1d_size="32KiB",
    l1i_size="32KiB",
    l2_size="256KiB",
)
if args.zero_lat:
    memory = SingleChannelSimpleMemory(latency="1ns", latency_var="0ns", bandwidth="1TiB/s", size="16GiB")
else:
    memory = SingleChannelDDR3_1600(size="16GiB")

if warmup_insts > 0:
    processor = DefaultSwitchableProcessor(iq_size=args.iq_size, diq_size=args.diq_size, super_mode=args.super_mode)
    proc_name = "Switch Super Default O3" if args.super_mode else "Switch Default O3"
else:
    processor = SimpleProcessor(cpu_type=CPUTypes.O3, isa=ISA.ARM, num_cores=1)
    core = processor.get_cores()[0].get_simobject()
    core.numIQEntries = args.iq_size
    core.numDeltaIQEntries = args.diq_size
    if args.super_mode:
        _apply_super_params(core)
    proc_name = "Super O3" if args.super_mode else "Default O3"

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
    num_ticks = parse_count(ticks)
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
    case "lbm_s":
        binary_path = f"{test_dir}/619.lbm_s/lbm_s"
        binary_args = ["2000", "reference.dat", "0", "0", f"{test_dir}/619.lbm_s/data/refspeed/input/200_200_260_ldc.of"]
    case "mcf_s":
        binary_path = f"{test_dir}/605.mcf_s/mcf_s"
        binary_args = [f"{test_dir}/605.mcf_s/data/refspeed/input/inp.in"]
    case "gcc_s":
        binary_path = f"{test_dir}/602.gcc_s/sgcc"
        binary_args = [f"{test_dir}/602.gcc_s/data/refspeed/input/gcc-pp.c"]

board.set_se_binary_workload(binary=BinaryResource(binary_path), arguments=binary_args)
simulator = Simulator(board=board)
print(f"Running benchmark {binary} for {sim_desc} with {proc_name}, IQ = {args.iq_size} and DIQ = {args.diq_size}\n")

if warmup_insts > 0:
    print(f"\nFast-forwarding {warmup_insts:,} instructions in ATOMIC mode...\n\n")
    simulator.schedule_max_insts(warmup_insts)
    simulator.run()
    m5.stats.reset()
    simulator.switch_processor()
    print(f"\nWarmup done after {simulator.get_current_tick()} simulated ticks. Switched CPU, starting measurements...\n\n")

simulator.run(num_ticks)

print(f"{binary} ran a total of {simulator.get_current_tick()} simulated ticks on {proc_name} with IQ = {args.iq_size} and DIQ = {args.diq_size}\n")