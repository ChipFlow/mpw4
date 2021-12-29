from .techno import *
from .StdCellLib import setup as StdCellLib_setup
from .IOLib import setup as IOLib_setup

__lib_setups__ = [StdCellLib.setup,IOLib.setup]
