# -*- coding: utf-8 -*-
import ctypes
import os as _os
import sys as _sys

def _preload_libleidenalg():
    """Preload liblibleidenalg so its symbols are in the flat namespace before
    _c_leiden is imported.  On macOS, Python extensions are linked with
    -undefined dynamic_lookup, so libleidenalg is not recorded as an explicit
    LC_LOAD_DYLIB entry; we must load it ourselves with RTLD_GLOBAL."""
    _pkg_dir = _os.path.dirname(_os.path.abspath(__file__))
    if _sys.platform == "darwin":
        _names = ["liblibleidenalg.dylib", "liblibleidenalg.1.dylib", "liblibleidenalg.0.1.0.dylib"]
    else:
        _names = ["liblibleidenalg.so", "liblibleidenalg.so.1", "liblibleidenalg.so.0.1.0"]
    _search = [
        _pkg_dir,
        _os.path.join(_os.path.expanduser("~"), ".local", "lib"),
    ]
    for _d in _search:
        for _n in _names:
            _p = _os.path.join(_d, _n)
            if _os.path.isfile(_p):
                try:
                    ctypes.CDLL(_p, ctypes.RTLD_GLOBAL)
                    return
                except OSError:
                    pass

_preload_libleidenalg()
del _preload_libleidenalg, ctypes, _os, _sys

r""" This package implements the Leiden algorithm in ``C++`` and exposes it to
python.  It relies on ``(python-)igraph`` for it to function. Besides the
relative flexibility of the implementation, it also scales well, and can be run
on graphs of millions of nodes (as long as they can fit in memory). Each method
is represented by a different class, all of whom derive from
:class:`~leidenalg.VertexPartition.MutableVertexPartition`. In addition,
multiplex graphs are supported as layers, which also supports multislice
representations.

Examples
--------

The simplest example just finds a partition using modularity

  >>> G = ig.Graph.Tree(100, 3)
  >>> partition = la.find_partition(G, la.ModularityVertexPartition)

Alternatively, one can access the different optimisation routines individually
and construct partitions oneself. These partitions can then be optimised by
constructing an :class:`Optimiser` object and running
:func:`~Optimiser.optimise_partition`.

  >>> G = ig.Graph.Tree(100, 3)
  >>> partition = la.CPMVertexPartition(G, resolution_parameter = 0.1)
  >>> optimiser = la.Optimiser()
  >>> diff = optimiser.optimise_partition(partition)

The :class:`Optimiser` class contains also the different subroutines that are
used internally by :func:`~Optimiser.optimise_partition`. In addition, through
the Optimiser class there are various options available for changing some of
the optimisation procedure which can affect both speed and quality, which are
not immediately available in :func:`leidenalg.find_partition`.
"""
from .functions import ALL_COMMS
from .functions import ALL_NEIGH_COMMS
from .functions import RAND_COMM
from .functions import RAND_NEIGH_COMM

from .functions import MOVE_NODES
from .functions import MERGE_NODES

from .functions import find_partition
from .functions import find_partition_multiplex
from .functions import find_partition_temporal
from .functions import slices_to_layers
from .functions import time_slices_to_layers

from .Optimiser import Optimiser
from .VertexPartition import ModularityVertexPartition
from .VertexPartition import SurpriseVertexPartition
from .VertexPartition import SignificanceVertexPartition
from .VertexPartition import RBERVertexPartition
from .VertexPartition import RBConfigurationVertexPartition
from .VertexPartition import CPMVertexPartition

from .version import *
