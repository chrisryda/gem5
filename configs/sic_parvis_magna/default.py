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
    cpu.numROBEntries = 512   # 1024 triggers gem5's instcount <= 1500 assertion
    cpu.LQEntries = 512
    cpu.SQEntries = 512
    cpu.numPhysIntRegs = 512
    cpu.numPhysFloatRegs = 512


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
parser.add_argument("--o3-warmup-insts", type=str, default="0", help="Instructions to run on O3 (no stats) before measurement (e.g. 100M). Requires --warmup-insts > 0.")
parser.add_argument("--iq-size", type=int, default=64, help="Number of IQ entries")
parser.add_argument("--diq-size", type=int, default=0, help="Number of Delta IQ entries")
parser.add_argument("--zero-lat", action="store_true", default=False, help="Use near-zero DRAM latency to isolate IQ bottleneck")
parser.add_argument("--super", dest="super_mode", action="store_true", default=False, help="Use over-provisioned processor (wide pipeline, large ROB/LSQ/regfile) to isolate IQ as bottleneck")
args = parser.parse_args()
warmup_insts = parse_count(args.warmup_insts)
o3_warmup_insts = parse_count(args.o3_warmup_insts)
if o3_warmup_insts > 0 and warmup_insts == 0:
    parser.error("--o3-warmup-insts requires --warmup-insts to be set")

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
stdin_path = None
cwd_path = None
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
    case "exchange2_s": #src and data folders copied from 548.exchange2_r, no refspeed inputs available
        binary_path = f"{test_dir}/648.exchange2_s/exchange2_s"
        binary_args = []
        stdin_path = f"{test_dir}/648.exchange2_s/input.txt"
    case "fotonik3d_s": # src and data folders copied from 549.fotonik3d_r
        binary_path = f"{test_dir}/649.fotonik3d_s/fotonik3d_s"
        binary_args = []
        cwd_path = f"{test_dir}/649.fotonik3d_s/data/refspeed/input"
    case "nab_s": # src and data folders copied from 544.nab_r
        binary_path = f"{test_dir}/644.nab_s/nab_s"
        binary_args = ["3j1n", "20140317", "220"]
        cwd_path = f"{test_dir}/644.nab_s/data/refspeed/input"
    case "x264_s": # src and data folders copied from 525.x264_r, refrate input only
        binary_path = f"{test_dir}/625.x264_s/src/x264_s"
        binary_args = [
            "--pass", "1",
            "--stats", "BuckBunny.264.stats",
            "--bitrate", "1000",
            "--frames", "500",
            "-o", "BuckBunny_New.264",
            f"{test_dir}/625.x264_s/data/refrate/input/BuckBunny.264",
            "1280x720",
        ]
    case "perlbench_s": # src and data folders copied from 600.perlbench_r
        binary_path = f"{test_dir}/600.perlbench_s/perlbench_s"
        binary_args = [
            "-I./lib",
            "checkspam.pl",
            "2500", "5", "25", "11", "150", "1", "1", "1"
        ]
        cwd_path = f"{test_dir}/600.perlbench_s"
    case "leela_s": #src and data folders copied from 541.leela_r 
        binary_path = f"{test_dir}/641.leela_s/leela_s"
        binary_args = [f"{test_dir}/641.leela_s/ref.sgf"]
    case "deepsjeng_s": #src folder copied from 531.deepsjeng_r 
        binary_path = f"{test_dir}/631.deepsjeng_s/deepsjeng_s"
        binary_args = [f"{test_dir}/631.deepsjeng_s/ref.txt"]
    case "bwaves_s": #src and data folders copied from 503.bwaves_r
        binary_path = f"{test_dir}/603.bwaves_s/speed_bwaves"
        # binary_args = ["bwaves_1"]
        binary_args = []
        stdin_path = f"{test_dir}/603.bwaves_s/bwaves_1.in"

board.set_se_binary_workload(
    binary=BinaryResource(binary_path),
    arguments=binary_args,
    stdin_file=BinaryResource(stdin_path) if stdin_path else None,
)
if cwd_path:
    proc = board.get_processor()
    cores = proc._all_cores() if hasattr(proc, "_all_cores") else proc.get_cores()
    for core in cores:
        core.get_simobject().workload[0].cwd = cwd_path

simulator = Simulator(board=board)
print(f"default.py: Running benchmark {binary} for {sim_desc} with {proc_name}, IQ = {args.iq_size} and DIQ = {args.diq_size}\n")

if warmup_insts > 0:
    print(f"\n[Phase 1] Fast-forwarding {warmup_insts:,} instructions in ATOMIC mode...\n")
    simulator.schedule_max_insts(warmup_insts)
    simulator.run()
    simulator.switch_processor()
    print(f"[Phase 1] Done at {simulator.get_current_tick():,} ticks. Switched to O3.\n")

    if o3_warmup_insts > 0:
        print(f"[Phase 2] Running {o3_warmup_insts:,} instructions on O3 (no stats)...\n")
        simulator.schedule_max_insts(o3_warmup_insts)
        simulator.run()
        print(f"[Phase 2] Done at {simulator.get_current_tick():,} ticks.\n")

    m5.stats.reset()
    phase_label = "[Phase 3]" if o3_warmup_insts > 0 else "[Phase 2]"
    print(f"{phase_label} Starting measurement for {sim_desc}...\n")
    simulator.run(num_ticks)
else:
    simulator.run(num_ticks)

print(f"default.py: {binary} ran a total of {simulator.get_current_tick()} simulated ticks on {proc_name} with IQ = {args.iq_size} and DIQ = {args.diq_size}\n")