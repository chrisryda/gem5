# Copyright (c) 2021-2025 The Regents of the University of California
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met: redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer;
# redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution;
# neither the name of the copyright holders nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
This gem5 configuation script creates a simple board to run an ARM
"hello world" binary.

This setup is close to the simplest setup possible using the gem5
library. It does not contain any kind of caching, IO, or any non-essential
components.
"""
import os
import argparse
# from sic_parvis import Magna, MagnaOpus, IceLakeCacheHierarchy

from gem5.isas import ISA
from gem5.utils.requires import requires
from gem5.simulate.simulator import Simulator
from gem5.resources.resource import BinaryResource
from gem5.components.memory import SingleChannelDDR3_1600
from gem5.components.processors.cpu_types import CPUTypes
from gem5.components.boards.simple_board import SimpleBoard
from gem5.components.cachehierarchies.classic.private_l1_private_l2_cache_hierarchy import PrivateL1PrivateL2CacheHierarchy
from gem5.components.processors.simple_processor import SimpleProcessor

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
parser.add_argument("--iq-size", type=int, default=64, help="Number of IQ entries")
args = parser.parse_args()

# This check ensures the gem5 binary contains the ARM ISA target. If not, an
# exception will be thrown.
requires(isa_required=ISA.ARM)

cache_hierarchy = PrivateL1PrivateL2CacheHierarchy(
    l1d_size="32KiB",
    l1i_size="32KiB",
    l2_size="256KiB",
)

# We use a single channel DDR3_1600 memory system
memory = SingleChannelDDR3_1600(size="32MiB")

# We use a simple O3 processor with one core.
processor = SimpleProcessor(cpu_type=CPUTypes.O3, isa=ISA.ARM, num_cores=1)
processor.get_cores()[0].get_simobject().numIQEntries = args.iq_size

# The gem5 library simple board which can be used to run SE-mode simulations.
board = SimpleBoard(
    clk_freq="3.3GHz",
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
print(f"Running benchmark {binary} for {sim_desc}\n")

# simulator.schedule_max_insts(1_000_000_000)
# simulator.run()
simulator.run(num_ticks)

print(f"{binary} ran a total of {simulator.get_current_tick()} simulated ticks\n")
