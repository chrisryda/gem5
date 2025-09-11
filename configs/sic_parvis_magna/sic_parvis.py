from m5.objects import ArmO3CPU
from m5.objects.BranchPredictor import (
    MultiperspectivePerceptronTAGE64KB,
    TournamentBP,
)
from m5.objects.FuncUnitConfig import *

from gem5.components.processors.base_cpu_core import BaseCPUCore
from gem5.components.processors.base_cpu_processor import BaseCPUProcessor
from gem5.isas import ISA

# O3CPUCore extends Arn3CPU. ArmO3CPU is one of gem5's internal models
# the implements an out of order pipeline. Please refer to
# https://www.gem5.org/documentation/general_docs/cpu_models/O3CPU
# to learn more about O3CPU.
class O3CPUCore(ArmO3CPU):
    def __init__(self, width, rob_size, num_int_regs, num_fp_regs):
        """
        :param width: sets the width of fetch, decode, rename, issue, wb, and
        commit stages.
        :param rob_size: determine the number of entries in the reorder buffer.
        :param num_int_regs: determines the size of the integer register file.
        :param num_int_regs: determines the size of the vector/floating point
        register file.
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

        self.LQEntries = 32
        self.SQEntries = 32

# Along with BaseCPUCore, CPUStdCore wraps CPUCore to a core compatible
# with gem5's standard library. Please refer to
# gem5/src/python/gem5/components/processors/base_cpu_core.py
# to learn more about BaseCPUCore.


class O3CPUStdCore(BaseCPUCore):
    def __init__(self, width, rob_size, num_int_regs, num_fp_regs):
        """
        :param width: sets the width of fetch, decode, raname, issue, wb, and
        commit stages.
        :param rob_size: determine the number of entries in the reorder buffer.
        :param num_int_regs: determines the size of the integer register file.
        :param num_int_regs: determines the size of the vector/floating point
        register file.
        """
        core = O3CPUCore(width, rob_size, num_int_regs, num_fp_regs)
        super().__init__(core, ISA.ARM)


# O3CPU along with BaseCPUProcessor wraps CPUCore to a processor
# compatible with gem5's standard library. Please refer to
#  gem5/src/python/gem5/components/processors/base_cpu_processor.py
# to learn more about BaseCPUProcessor.


class O3CPU(BaseCPUProcessor):
    def __init__(self, width, rob_size, num_int_regs, num_fp_regs):
        """
        :param width: sets the width of fetch, decode, raname, issue, wb, and
        commit stages.
        :param rob_size: determine the number of entries in the reorder buffer.
        :param num_int_regs: determines the size of the integer register file.
        :param num_int_regs: determines the size of the vector/floating point
        register file.
        """
        cores = [O3CPUStdCore(width, rob_size, num_int_regs, num_fp_regs)]
        super().__init__(cores)
        self._width = width
        self._rob_size = rob_size
        self._num_int_regs = num_int_regs
        self._num_fp_regs = num_fp_regs

    def get_area_score(self):
        """
        :returns the area score of a pipeline using its parameters width,
        rob_size, num_int_regs, and num_fp_regs.
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
