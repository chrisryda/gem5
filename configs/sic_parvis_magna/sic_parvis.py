from m5.objects import (
    ArmO3CPU,
    BadAddr,
    Cache,
    L2XBar,
    StridePrefetcher,
    SystemXBar,
)

from m5.objects.BranchPredictor import (
    MultiperspectivePerceptronTAGE64KB,
    TournamentBP,
)

from m5.objects.FuncUnitConfig import *
from m5.objects.FUPool import DefaultFUPool
from gem5.utils.override import overrides

from gem5.components.processors.base_cpu_core import BaseCPUCore
from gem5.components.processors.base_cpu_processor import BaseCPUProcessor
from gem5.components.processors.switchable_processor import SwitchableProcessor
from gem5.components.processors.simple_core import SimpleCore
from gem5.components.processors.cpu_types import CPUTypes
from gem5.components.processors.abstract_processor import AbstractProcessor
from gem5.components.boards.mem_mode import MemMode
from gem5.isas import ISA

from gem5.components.cachehierarchies.classic.caches.l1dcache import L1DCache
from gem5.components.cachehierarchies.classic.caches.l1icache import L1ICache
from gem5.components.cachehierarchies.abstract_cache_hierarchy import AbstractCacheHierarchy
from gem5.components.cachehierarchies.abstract_three_level_cache_hierarchy import AbstractThreeLevelCacheHierarchy
from gem5.components.cachehierarchies.classic.abstract_classic_cache_hierarchy import AbstractClassicCacheHierarchy

# O3CPUCore extends Arm3CPU. ArmO3CPU is one of gem5's internal models
# that implements an out of order pipeline. Please refer to
# https://www.gem5.org/documentation/general_docs/cpu_models/O3CPU
# to learn more about O3CPU.
class O3CPUCore(ArmO3CPU):
    def __init__(self, width, rob_size, num_int_regs, num_fp_regs):
        """
        :param width:        sets the width of fetch, decode, rename, issue, wb, and commit stages.
        :param rob_size:     determine the number of entries in the reorder buffer.
        :param num_int_regs: determines the size of the integer register file.
        :param num_int_regs: determines the size of the vector/floating point register file.
        """
        super().__init__()
        self.fetchWidth = width
        self.decodeWidth = width
        self.renameWidth = width
        self.issueWidth = width
        self.wbWidth = width
        self.commitWidth = width

        self.numROBEntries = rob_size

        self.numPhysIntRegs = num_int_regs
        self.numPhysFloatRegs = num_fp_regs

        self.branchPred = TournamentBP()

        self.numIQEntries = 64
        self.numDeltaIQEntries = 14
        self.LQEntries = 32
        self.SQEntries = 32

# Along with BaseCPUCore, O3CPUStdCore wraps O3CPUCore to a core
# compatible with gem5's standard library. Please refer to
# gem5/src/python/gem5/components/processors/base_cpu_core.py
# to learn more about BaseCPUCore.
class O3CPUStdCore(BaseCPUCore):
    def __init__(self, width, rob_size, num_int_regs, num_fp_regs):
        """
        :param width:        sets the width of fetch, decode, raname, issue, wb, and commit stages.
        :param rob_size:     determine the number of entries in the reorder buffer.
        :param num_int_regs: determines the size of the integer register file.
        :param num_int_regs: determines the size of the vector/floating point register file.
        """
        core = O3CPUCore(width, rob_size, num_int_regs, num_fp_regs)
        super().__init__(core, ISA.ARM)


# O3CPU along with BaseCPUProcessor wraps O3CPUCore to a processor
# compatible with gem5's standard library. Please refer to
#  gem5/src/python/gem5/components/processors/base_cpu_processor.py
# to learn more about BaseCPUProcessor.
class O3CPU(BaseCPUProcessor):
    def __init__(self, width, rob_size, num_int_regs, num_fp_regs):
        """
        :param width:        sets the width of fetch, decode, raname, issue, wb, and commit stages.
        :param rob_size:     determine the number of entries in the reorder buffer.
        :param num_int_regs: determines the size of the integer register file.
        :param num_int_regs: determines the size of the vector/floating point register file.
        """
        cores = [O3CPUStdCore(width, rob_size, num_int_regs, num_fp_regs)]
        super().__init__(cores)
        self._width = width
        self._rob_size = rob_size
        self._num_int_regs = num_int_regs
        self._num_fp_regs = num_fp_regs

    def get_area_score(self):
        """
        :returns the area score of a pipeline using its parameters
        width, rob_size, num_int_regs, and num_fp_regs.
        """
        score = (
            self._width
            * (2 * self._rob_size + self._num_int_regs + self._num_fp_regs)
            + 4 * self._width
            + 2 * self._rob_size
            + self._num_int_regs
            + self._num_fp_regs
        )
        return score


class Magna(O3CPU):
    def __init__(self):
        super().__init__(
            width=2,
            rob_size=50,
            num_int_regs=64,
            num_fp_regs=64,
        )

# Ice Lake-like processor (Table 1 from Doppelganger).
class MagnaOpusInternalCore(ArmO3CPU):
    def __init__(self, iq_size=120, diq_size=40):
        super().__init__()
        self.fetchWidth = 6   # unspecified in paper -- ??**but likely wider than 5 (decode width) to allow for fetch bubbles**?? --Claude
        self.decodeWidth = 5
        self.renameWidth = 5  # unspecified in paper
        self.issueWidth = 8
        self.wbWidth = 8      # unspecified in paper
        self.commitWidth = 8

        self.numROBEntries = 352
        self.numIQEntries = iq_size # Doppelganger has 160
        self.numDeltaIQEntries = diq_size
        self.LQEntries = 128
        self.SQEntries = 72

        # Physical register file sizes unspecified in paper. BaseO3CPU has 256/256
        self.numPhysIntRegs = 280
        self.numPhysFloatRegs = 224

        self.branchPred = MultiperspectivePerceptronTAGE64KB() # unspecified in paper, but ShadowBinding lists it


class MagnaOpusStdCore(BaseCPUCore):
    def __init__(self, iq_size=120, diq_size=40):
        core = MagnaOpusInternalCore(iq_size=iq_size, diq_size=diq_size)
        super().__init__(core, ISA.ARM)


class MagnaOpus(BaseCPUProcessor):
    """Single-core Ice Lake-like processor."""

    def __init__(self, iq_size=120, diq_size=40):
        super().__init__([MagnaOpusStdCore(iq_size=iq_size, diq_size=diq_size)])

# Over-provisioned FU pool to remove FUs as bottleneck.
# DefaultFUPool indices: [0]=IntALU, [1]=IntMultDiv, [2]=FP_ALU, [3]=FP_MultDiv,
# [4]=ReadPort, [5]=SIMD_Unit, [6]=Matrix_Unit, [7]=PredALU, [8]=WritePort,
# [9]=RdWrPort, [10]=IprPort
class SuperMagnaOpusFUPool(DefaultFUPool):
    FUList = [
        IntALU(count=8),
        IntMultDiv(count=2),
        FP_ALU(count=8),
        FP_MultDiv(count=2),
        ReadPort(count=3),
        SIMD_Unit(count=2),
        Matrix_Unit(),
        PredALU(count=2),
        WritePort(count=0),
        RdWrPort(),
        IprPort(),
    ]
    

# Over-provisioned processor: all structural parameters maxed out to isolate the IQ as the sole bottleneck.
class SuperMagnaOpusInternalCore(ArmO3CPU):
    def __init__(self, iq_size=120, diq_size=40):
        super().__init__()
        self.fetchWidth = 10
        self.decodeWidth = 10
        self.renameWidth = 10
        self.dispatchWidth = 10
        self.issueWidth = 12
        self.wbWidth = 12
        self.commitWidth = 12

        self.numROBEntries = 512   # 1024 triggers gem5's instcount <= 1500 assertion
        self.numIQEntries = iq_size
        self.numDeltaIQEntries = diq_size
        self.LQEntries = 512
        self.SQEntries = 512

        self.numPhysIntRegs = 512
        self.numPhysFloatRegs = 512

        self.fuPool = SuperMagnaOpusFUPool()
        self.branchPred = MultiperspectivePerceptronTAGE64KB()


class SuperMagnaOpusStdCore(BaseCPUCore):
    def __init__(self, iq_size=120, diq_size=40):
        core = SuperMagnaOpusInternalCore(iq_size=iq_size, diq_size=diq_size)
        super().__init__(core, ISA.ARM)


class SuperMagnaOpus(BaseCPUProcessor):
    """Single-core over-provisioned processor; IQ and DIQ remain configurable."""

    def __init__(self, iq_size=120, diq_size=40):
        super().__init__([SuperMagnaOpusStdCore(iq_size=iq_size, diq_size=diq_size)])


class MagnaOpusSwitchableProcessor(SwitchableProcessor):
    """
    Starts in ATOMIC mode for fast cache/TLB warmup, then switches to the
    full MagnaOpus O3 core for timing measurement.
    """

    def __init__(self, iq_size=120, diq_size=40):
        self._start_key = "start"
        self._switch_key = "switch"
        self._current_is_start = True

        atomic_core = SimpleCore(cpu_type=CPUTypes.ATOMIC, core_id=0, isa=ISA.ARM)
        o3_core = MagnaOpusStdCore(
            iq_size=iq_size,
            diq_size=diq_size,
        )
        # cpu_id must match on both sides of the switch or gem5 asserts
        o3_core.get_simobject().cpu_id = atomic_core.get_simobject().cpu_id

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


class SuperMagnaOpusSwitchableProcessor(SwitchableProcessor):
    """
    Starts in ATOMIC mode for fast cache/TLB warmup, then switches to the
    full MagnaOpus O3 core for timing measurement.
    """

    def __init__(self, iq_size=120, diq_size=40):
        self._start_key = "start"
        self._switch_key = "switch"
        self._current_is_start = True

        atomic_core = SimpleCore(cpu_type=CPUTypes.ATOMIC, core_id=0, isa=ISA.ARM)
        o3_core = SuperMagnaOpusStdCore(
            iq_size=iq_size,
            diq_size=diq_size,
        )
        # cpu_id must match on both sides of the switch or gem5 asserts
        o3_core.get_simobject().cpu_id = atomic_core.get_simobject().cpu_id

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


# StridePrefetcher with 1024 entries, 8-way (matching Doppelganger(?))
class IceLakeStridePrefetcher(StridePrefetcher):
    table_entries = "1024"
    table_assoc = 8


# Ice Lake-like cache hierarchy (Table 1 from Doppelganger)
# L1D: 48 KiB, 12-way,  5-cycle roundtrip, 16 MSHRs + stride prefetcher
# L1I: 32 KiB,  8-way  (Ice Lake front-end)
# L2:   2 MiB,  8-way, 15-cycle roundtrip  (private per core)
# L3:  16 MiB, 16-way, 40-cycle roundtrip  (shared)
class IceLakeCacheHierarchy(AbstractClassicCacheHierarchy, AbstractThreeLevelCacheHierarchy):
    def __init__(self, zero_lat=False):
        AbstractClassicCacheHierarchy.__init__(self)
        AbstractThreeLevelCacheHierarchy.__init__(
            self,
            l1i_size="32KiB",
            l1i_assoc=8,
            l1d_size="48KiB",
            l1d_assoc=12,
            l2_size="2MiB",
            l2_assoc=8,
            l3_size="16MiB",
            l3_assoc=16,
        )
        self._zero_lat = zero_lat
        membus = SystemXBar(width=64) # main memory bus
        membus.badaddr_responder = BadAddr() # responder for unmapped addresses, instead of hanging the simulation
        membus.default = membus.badaddr_responder.pio # set route for unmapped addresses
        self.membus = membus # makes it a child SimObject of the hierarchy, so gem5 includes it in the simulation 

    # The board calls these to connect memory controllers and I/O devices to the hierarchy
    @overrides(AbstractClassicCacheHierarchy)
    def get_mem_side_port(self):
        return self.membus.mem_side_ports
    
    @overrides(AbstractClassicCacheHierarchy)
    def get_cpu_side_port(self):
        return self.membus.cpu_side_ports

    # Called by the board during setup to connect the cache hierarchy to the rest of the system.
    # This is where all the connections between caches, buses, and the processor are made.
    @overrides(AbstractCacheHierarchy)
    def incorporate_cache(self, board):
        board.connect_system_port(self.membus.cpu_side_ports)
        
        # Wire memory bus <--> memory controllers (DRAM)
        for _, port in board.get_mem_ports():
            self.membus.mem_side_ports = port

        # Shared L3 and its bus
        self.l3bus = L2XBar(width=64)
        self.l3cache = Cache(
            size=self._l3_size,
            assoc=self._l3_assoc,
            tag_latency=1 if self._zero_lat else 39,
            data_latency=1,
            response_latency=1,
            mshrs=32,
            tgts_per_mshr=12,
        )
        # Wire L3 bus <--> L3 cache <--> memory bus
        self.l3bus.mem_side_ports = self.l3cache.cpu_side
        self.l3cache.mem_side = self.membus.cpu_side_ports

        # Per-core L1 + L2
        num_cores = board.get_processor().get_num_cores()
        self.l2buses = [L2XBar(width=64) for _ in range(num_cores)]
        self.l2caches = [
            Cache(
                size=self._l2_size,
                assoc=self._l2_assoc,
                tag_latency=1 if self._zero_lat else 14,
                data_latency=1,
                response_latency=1,
                mshrs=20,
                tgts_per_mshr=12,
                prefetcher=IceLakeStridePrefetcher(),
            )
            for _ in range(num_cores)
        ]

        self.l1icaches = [
            L1ICache(
                size=self._l1i_size,
                assoc=self._l1i_assoc,
                tag_latency=1,
                data_latency=1,
                response_latency=1,
                mshrs=16,
                PrefetcherCls=NULL,
            )
            for _ in range(num_cores)
        ]

        self.l1dcaches = [
            L1DCache(
                size=self._l1d_size,
                assoc=self._l1d_assoc,
                tag_latency=1 if self._zero_lat else 4,
                data_latency=1,
                response_latency=1,
                mshrs=16,
                PrefetcherCls=IceLakeStridePrefetcher,
            )
            for _ in range(num_cores)
        ]

        # Wire: CPU <--> L1I/L1D <--> L2 bus <--> L2 <--> L3 bus
        for i, cpu in enumerate(board.get_processor().get_cores()):
            self.l2caches[i].mem_side = self.l3bus.cpu_side_ports
            self.l2buses[i].mem_side_ports = self.l2caches[i].cpu_side
            self.l1icaches[i].mem_side = self.l2buses[i].cpu_side_ports
            self.l1dcaches[i].mem_side = self.l2buses[i].cpu_side_ports

            cpu.connect_icache(self.l1icaches[i].cpu_side)
            cpu.connect_dcache(self.l1dcaches[i].cpu_side)
            
            # Connect the ARM MMU table walker to the L2 bus so page table walks
            # go through L2/L3 before hitting DRAM, matching real hardware behavior.
            cpu.connect_walker_ports(self.l2buses[i].cpu_side_ports, self.l2buses[i].cpu_side_ports)
            
            # Connects the CPU's interrupt controller ports. On ARM in SE mode this is essentially a 
            # no-op placeholder, but the standard library requires it to be called.
            cpu.connect_interrupt()

        
        #  Some boards (primarily FS mode) have I/O devices that participate in cache coherence. 
        # This tiny 1 KiB cache acts as a coherence adapter between those devices and the memory bus. 
        # In SE mode has_coherent_io() returns false and this block is never reached.
        if board.has_coherent_io():
            self.iocache = Cache(
                assoc=8,
                tag_latency=50,
                data_latency=50,
                response_latency=50,
                mshrs=20,
                size="1KiB",
                tgts_per_mshr=12,
                addr_ranges=board.mem_ranges,
            )
            self.iocache.mem_side = self.membus.cpu_side_ports
            self.iocache.cpu_side = board.get_mem_side_coherent_io_port()
