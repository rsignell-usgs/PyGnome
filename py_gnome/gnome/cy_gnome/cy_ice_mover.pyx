import os

cimport numpy as cnp
import numpy as np
from libc.string cimport memcpy

from type_defs cimport *
from utils cimport _GetHandleSize
from movers cimport Mover_c
from current_movers cimport IceMover_c,GridCurrentMover_c,CurrentMover_c

from gnome import basic_types
from gnome.cy_gnome.cy_gridcurrent_mover cimport CyGridCurrentMover
from gnome.cy_gnome.cy_helpers cimport to_bytes


cdef extern from *:
    #IceMover_c* dynamic_cast_ptr "dynamic_cast<IceMover_c *>" (Mover_c *) except NULL
    IceMover_c* dc_mover_to_im "dynamic_cast<IceMover_c *>" (Mover_c *) except NULL
    CurrentMover_c* dc_im_mover_to_cm "dynamic_cast<IceMover_c *>" (Mover_c *) except NULL
    GridCurrentMover_c* dc_im_mover_to_gcm "dynamic_cast<IceMover_c *>" (Mover_c *) except NULL

cdef class CyIceMover(CyGridCurrentMover):

    cdef IceMover_c *grid_ice

    def __cinit__(self):
        self.mover = new IceMover_c()
        #self.grid_ice = dynamic_cast_ptr(self.mover)
        self.grid_ice = dc_mover_to_im(self.mover)
        self.curr_mv = dc_im_mover_to_cm(self.mover)
        self.grid_current = dc_im_mover_to_gcm(self.mover)

    def __dealloc__(self):
        del self.mover
        self.mover = NULL
        self.grid_ice = NULL
        self.curr_mv = NULL
        self.grid_current = NULL

    def text_read(self, time_grid_file, topology_file=None):
        """
        .. function::text_read

        """
        cdef OSErr err
        cdef bytes time_grid, topology

        time_grid_file = os.path.normpath(time_grid_file)
        time_grid = to_bytes(unicode(time_grid_file))

        if topology_file is None:
            err = self.grid_ice.TextRead(time_grid, '')
        else:
            topology_file = os.path.normpath(topology_file)
            topology = to_bytes(unicode(topology_file))
            err = self.grid_ice.TextRead(time_grid, topology)

        if err != 0:
            """
            For now just raise an OSError - until the types of possible errors
            are defined and enumerated
            """
            raise OSError("IceMover_c.TextRead returned an error.")

    def _get_triangle_data(self):
        """
            Invokes the GetToplogyHdl method of TriGridVel_c object
            to get the velocities for the grid
        """
        cdef short tmp_size = sizeof(Topology)
        cdef TopologyHdl top_hdl
        cdef cnp.ndarray[Topology, ndim = 1] top

        # allocate memory and copy it over
        # should check that topology exists
        top_hdl = self.grid_ice.GetTopologyHdl()
        sz = _GetHandleSize(<Handle>top_hdl)

        # will this always work?
        top = np.empty((sz / tmp_size,), dtype=basic_types.triangle_data)

        memcpy(&top[0], top_hdl[0], sz)

        return top

    def get_num_triangles(self):
        """
            Invokes the GetNumTriangles method of TriGridVel_c object
            to get the number of triangles
        """
        num_tri = self.grid_ice.GetNumTriangles()

        return num_tri

    def get_ice_fields(self, Seconds model_time,
                 cnp.ndarray[cnp.npy_double] thickness,
                 cnp.ndarray[cnp.npy_double] fraction):
        """
            Invokes the GetNumTriangles method of TriGridVel_c object
            to get the number of triangles
        """
        cdef OSErr err
        err = self.grid_ice.GetIceFields(model_time,&thickness[0],&fraction[0])

        if err != 0:
            """
            For now just raise an OSError - until the types of possible errors
            are defined and enumerated
            """
            raise OSError("IceMover_c.GetIceFields returned an error.")
