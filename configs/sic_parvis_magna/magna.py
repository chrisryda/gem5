import os
import argparse
from datetime import datetime
from sic_parvis import Magna, MagnaOpus, SuperMagnaOpus, MagnaOpusSwitchableProcessor, SuperMagnaOpusSwitchableProcessor, IceLakeCacheHierarchy

import m5
from gem5.isas import ISA
from gem5.simulate.simulator import Simulator
from gem5.resources.resource import BinaryResource

from gem5.components.boards.simple_board import SimpleBoard
from gem5.components.memory import SingleChannelDDR4_2400
from gem5.components.memory.simple import SingleChannelSimpleMemory

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

parser = argparse.ArgumentParser()
sim_limit = parser.add_mutually_exclusive_group()
sim_limit.add_argument("-t", dest="ticks", type=str, help="The amount of ticks to simulate")
sim_limit.add_argument("-c", dest="cycles", type=str, help="The amount of cycles to simulate")
parser.add_argument("-b", dest="binary", type=str, help="The benchmark to run")
parser.add_argument("--warmup-insts", type=str, default="0", help="Instructions to fast-forward in ATOMIC mode before timing measurement (e.g. 100M, 1B)")
parser.add_argument("--o3-warmup-insts", type=str, default="0", help="Instructions to run on O3 (no stats) before measurement (e.g. 100M). Requires --warmup-insts > 0.")
parser.add_argument("--iq-size", type=int, default=120, help="Regular IQ entries")
parser.add_argument("--diq-size", type=int, default=40, help="Delta IQ entries")
parser.add_argument("--zero-lat", action="store_true", default=False, help="Use 1-cycle cache latencies and near-zero DRAM latency to isolate IQ bottleneck")
parser.add_argument("--super", dest="super_mode", action="store_true", default=False, help="Use over-provisioned processor (wide pipeline, large ROB/LSQ/regfile) to isolate IQ as bottleneck")
args = parser.parse_args()
warmup_insts = parse_count(args.warmup_insts)
o3_warmup_insts = parse_count(args.o3_warmup_insts)
if o3_warmup_insts > 0 and warmup_insts == 0:
    parser.error("--o3-warmup-insts requires --warmup-insts to be set")

if warmup_insts > 0:
    if args.super_mode:
        processor = SuperMagnaOpusSwitchableProcessor(iq_size=args.iq_size, diq_size=args.diq_size)
        proc_name = "Switch Super MO"
    else:
        processor = MagnaOpusSwitchableProcessor(iq_size=args.iq_size, diq_size=args.diq_size)
        proc_name = "Switch MagnaOpus"
else:
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
    case "lbm_s": #src folder copied from 519.lbm_r
        binary_path = f"{test_dir}/619.lbm_s/lbm_s"
        binary_args = ["2000", "reference.dat", "0", "0", f"{test_dir}/619.lbm_s/data/refspeed/input/200_200_260_ldc.of"]
    case "mcf_s": # src and data folders copied from 505.mcf_r
        binary_path = f"{test_dir}/605.mcf_s/mcf_s"
        binary_args = [f"{test_dir}/605.mcf_s/data/refspeed/input/inp.in"]
    case "gcc_s": # src and data folders copied from 502.gcc_r
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
    case "cam4_s": #src and data folders copied from 527.cam4_r
        binary_path = f"{test_dir}/627.cam4_s/cam4_s"
        binary_args = []
        cwd_path = f"{test_dir}/627.cam4_s/data/refspeed/input"
    case "roms_s": #src and data folders copied from 554.roms_r
        binary_path = f"{test_dir}/654.roms_s/sroms"
        binary_args = []
        stdin_path = f"{test_dir}/654.roms_s/data/refspeed/input/ocean_benchmark3.in.x"
        cwd_path = f"{test_dir}/654.roms_s/data/refspeed/input"
    case "pop2_s":
        binary_path = f"{test_dir}/628.pop2_s/speed_pop2"
        binary_args = []
        cwd_path = f"{test_dir}/628.pop2_s/data/refspeed/input"
    case "wrf_s": # src and data folders copied from 521.wrf_r
        binary_path = f"{test_dir}/621.wrf_s/wrf_s"
        binary_args = []
        cwd_path = f"{test_dir}/621.wrf_s/data/refspeed/input"
    case "omnetpp_s": # src and data copied from 520.omnetpp_r, refrate input only
        binary_path = f"{test_dir}/620.omnetpp_s/omnetpp_s"
        binary_args = ["-c", "General", "-r", "0", "omnetpp.ini"]
        cwd_path = f"{test_dir}/620.omnetpp_s/data/refrate/input"
    case "xalancbmk_s": # src and data copied from 523.xalancbmk_r, refrate input only
        binary_path = f"{test_dir}/623.xalancbmk_s/xalancbmk_s"
        binary_args = ["-v", "t5.xml", "xalanc.xsl"]
        cwd_path = f"{test_dir}/623.xalancbmk_s/data/refrate/input"
    case "imagick_s": # src and data folders copied from 538.imagick_r
        binary_path = f"{test_dir}/638.imagick_s/imagick_s"
        binary_args = [
            "-limit", "disk", "0",
            "refspeed_input.tga",
            "-resize", "817%",
            "-rotate", "-2.76",
            "-shave", "540x375",
            "-alpha", "remove",
            "-auto-level",
            "-contrast-stretch", "1x1%",
            "-colorspace", "Lab",
            "-channel", "R",
            "-equalize",
            "+channel",
            "-colorspace", "sRGB",
            "-define", "histogram:unique-colors=false",
            "-adaptive-blur", "0x5",
            "-despeckle",
            "-auto-gamma",
            "-adaptive-sharpen", "55",
            "-enhance",
            "-brightness-contrast", "10x10",
            "-resize", "30%",
            "refspeed_output.tga",
        ]
        cwd_path = f"{test_dir}/638.imagick_s/data/refspeed/input"
    case "xz_s": # src and data folders copied from 557.xz_r
        binary_path = f"{test_dir}/657.xz_s/xz_s"
        binary_args = [
            "cpu2006docs.tar.xz",
            "6643",
            "055ce243071129412e9dd0b3b69a21654033a9b723d874b2015c774fac1553d9713be561ca86f74e4f16f22e664fc17a79f30caa5ad2c04fbc447549c2810fae",
            "1036078272",
            "1111795472",
            "4",
        ]
        cwd_path = f"{test_dir}/657.xz_s/data/refspeed/input"
    case "cactuBSSN_s": # src and data folders copied from 507.cactuBSSN_r
        binary_path = f"{test_dir}/607.cactuBSSN_s/cactuBSSN_s"
        binary_args = ["spec_ref.par"]
        cwd_path = f"{test_dir}/607.cactuBSSN_s/data/refspeed/input"

board.set_se_binary_workload(
    binary=BinaryResource(binary_path),
    arguments=binary_args,
    stdin_file=BinaryResource(stdin_path) if stdin_path else None,
)
proc = board.get_processor()
if cwd_path:
    cores = proc._all_cores() if hasattr(proc, "_all_cores") else proc.get_cores()
    for core in cores:
        core.get_simobject().workload[0].cwd = cwd_path
simulator = Simulator(board=board)
print(f"Running benchmark {binary} for {sim_desc} with {proc_name}, IQ = {args.iq_size} and DIQ = {args.diq_size}\n")

if warmup_insts > 0:
    print(f"\n[{datetime.now():%b %d %H:%M:%S}] [Phase 1] Fast-forwarding {warmup_insts:,} instructions in ATOMIC mode...\n")
    simulator.schedule_max_insts(warmup_insts)
    simulator.run()
    simulator.switch_processor()
    print(f"[{datetime.now():%b %d %H:%M:%S}] [Phase 1] Done at {simulator.get_current_tick():,} ticks. Switched to O3.\n")

    if o3_warmup_insts > 0:
        print(f"[{datetime.now():%b %d %H:%M:%S}] [Phase 2] Running {o3_warmup_insts:,} instructions on O3 (no stats)...\n")
        simulator.schedule_max_insts(o3_warmup_insts)
        simulator.run()
        print(f"[{datetime.now():%b %d %H:%M:%S}] [Phase 2] Done at {simulator.get_current_tick():,} ticks.\n")
    else:
        print(f"[{datetime.now():%b %d %H:%M:%S}] [Phase 2] Skipped, no O3 warmup specified, skipping to measurement phase.\n")

    m5.stats.reset()
    print(f"[{datetime.now():%b %d %H:%M:%S}] [Phase 3] Starting measurement for {sim_desc}...\n")
    simulator.run(num_ticks)
else:
    simulator.run(num_ticks)

print(f"[{datetime.now():%b %d %H:%M:%S}] {binary} ran a total of {simulator.get_current_tick():,} simulated ticks on {proc_name} with IQ = {args.iq_size} and DIQ = {args.diq_size}")
