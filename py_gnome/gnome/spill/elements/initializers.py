#!/usr/bin/env python
'''
Types of elements that a spill can expect
These are properties that are spill specific like:
  'floating' element_types would contain windage_range, windage_persist
  'subsurface_dist' element_types would contain rise velocity distribution info
  'nonweathering' element_types would set use_droplet_size flag to False
  'weathering' element_types would use droplet_size, densities, mass?
'''
import copy
import numpy
np = numpy
from colander import SchemaNode, Int, Float, Range, TupleSchema
from collections import OrderedDict

import gnome    # required by new_from_dict
from gnome.utilities.rand import random_with_persistance
from gnome.utilities.serializable import Serializable
from gnome.utilities.distributions import UniformDistribution

from gnome.cy_gnome.cy_rise_velocity_mover import rise_velocity_from_drop_size

from gnome.persist import base_schema
from gnome import array_types
"""
Initializers for various element types
"""


class InitBaseClass(object):
    """
    All Init* classes will define the _state attribute, so just do so in a
    base class.

    It also documents that all initializers must implement an initialize method

    todo/Note:
    This may change as the persistence code changes. Currently, 'id' and
    'obj_type' are part of base Serializable._state
    """
    _state = copy.deepcopy(Serializable._state)

    def __init__(self):
        # make it an ordered dict so first element in array_types for any
        # initializer will be the primary data_array that is required by a
        # mover or weatherer. All other data_arrays are set by the initializer
        # by may not be directly required by a mover/weather. An example is
        # InitRiseVelFromDropletSizeFromDist() which stores the
        # droplet_diameter in the data_arrays even though it isn't required by
        # the mover
        #
        # NOTE: It is not necessary to make this an OrderedDict since the
        # data_arrays will contain all array_types set by the initializer if
        # the mover sets the primary data_array (ie rise_vel for above example)
        self.array_types = OrderedDict()

    def initialize(self, num_new_particles, spill, data_arrays, substance):
        """
        all classes that derive from Base class must implement initialize
        method
        """
        pass


class WindageSchema(TupleSchema):
    min_windage = SchemaNode(Float(), validator=Range(0, 1.0),
                             default=0.01)
    max_windage = SchemaNode(Float(), validator=Range(0, 1.0),
                             default=0.04)
    name = 'windage_range'


class InitWindagesSchema(base_schema.ObjType):
    """
    windages initializer values
    """
    windage_range = WindageSchema()
    windage_persist = SchemaNode(Int(), default=900,
                                 description='windage persistence in minutes')
    name = 'windages'


class InitWindages(InitBaseClass, Serializable):
    _update = ['windage_range', 'windage_persist']
    _create = []
    _create.extend(_update)
    _state = copy.deepcopy(InitBaseClass._state)
    _state.add(save=_create, update=_update)
    _schema = InitWindagesSchema

    def __init__(self, windage_range=(0.01, 0.04), windage_persist=900):
        """
        Initializes the windages, windage_range, windage_persist data arrays.
        Initial values for windages use infinite persistence. These are updated
        by the WindMover for particles with non-zero persistence.

        Optional arguments:

        :param windage_range=(0.01, 0.04): the windage range of the elements
            default is (0.01, 0.04) from 1% to 4%.
        :type windage_range: tuple: (min, max)

        :param windage_persist=-1: Default is 900s, so windage is updated every
            900 sec. -1 means the persistence is infinite so it is only set at
            the beginning of the run.
        :type windage_persist: integer seconds
        """
        super(InitWindages, self).__init__()
        self.windage_persist = windage_persist
        self.windage_range = windage_range
        self.array_types.update({'windages': array_types.windages,
                                 'windage_range': array_types.windage_range,
                                 'windage_persist': array_types.windage_persist
                                 })
        self.name = 'windages'

    def __repr__(self):
        return ('{0.__class__.__module__}.{0.__class__.__name__}('
                'windage_range={0.windage_range}, '
                'windage_persist={0.windage_persist}'
                ')'.format(self))

    @property
    def windage_persist(self):
        return self._windage_persist

    @windage_persist.setter
    def windage_persist(self, val):
        if val == 0:
            raise ValueError("'windage_persist' cannot be 0. "
                             "For infinite windage, windage_persist=-1 "
                             "otherwise windage_persist > 0.")
        self._windage_persist = val

    @property
    def windage_range(self):
        return self._windage_range

    @windage_range.setter
    def windage_range(self, val):
        if np.any(np.asarray(val) < 0) or np.asarray(val).size != 2:
            raise ValueError("'windage_range' >= (0, 0). "
                             "Nominal values vary between 1% to 4%. "
                             "Default windage_range=(0.01, 0.04)")
        self._windage_range = val

    def initialize(self, num_new_particles, spill, data_arrays,
                   substance=None):
        """
        Since windages exists in data_arrays, so must windage_range and
        windage_persist if this initializer is used/called
        """
        (data_arrays['windage_range'][-num_new_particles:, 0],
         data_arrays['windage_range'][-num_new_particles:, 1],
         data_arrays['windage_persist'][-num_new_particles:]) = \
            (self.windage_range[0],
             self.windage_range[1],
             self.windage_persist)

        # initialize all windages - ignore persistence during initialization
        # if we have infinite persistence, these values are never updated
        random_with_persistance(
                    data_arrays['windage_range'][-num_new_particles:][:, 0],
                    data_arrays['windage_range'][-num_new_particles:][:, 1],
                    data_arrays['windages'][-num_new_particles:])


# do following two classes work for a time release spill?


class InitMassFromSpillAmount(InitBaseClass, Serializable):
    """
    Initialize the 'mass' array based on total mass or volume spilled
    """

    _state = copy.deepcopy(InitBaseClass._state)
    _schema = base_schema.ObjType

    def __init__(self):
        """
        update array_types
        """
        super(InitMassFromSpillAmount, self).__init__()
        self.array_types.update({'mass': array_types.mass})
        self.name = 'mass'
        self.total_mass = None  # always in SI units

    def _set_total_mass(self, spill, substance):
        ''' set 'total_mass' property from spill since we only need to do this
        once '''
        if spill.get_mass('kg') is None:
            self.total_mass = 0     # do we want to raise an error?
        else:
            self.total_mass = spill.get_mass('kg')

    def initialize(self, num_new_particles, spill, data_arrays, substance):
        # store total_mass - it doesn't change so store it locally. The
        # windages are also tied to the spill
        if self.total_mass is None:
            self._set_total_mass(spill, substance)

        data_arrays['mass'][-num_new_particles:] = (self.total_mass /
                                                    spill.release.num_elements)


class InitMassFromPlume(InitBaseClass, Serializable):
    """
    Initialize the 'mass' array based on mass flux from the plume spilled
    """
    _state = copy.deepcopy(InitBaseClass._state)
    _schema = base_schema.ObjType

    def __init__(self):
        """
        update array_types
        """
        super(InitMassFromPlume, self).__init__()
        self.array_types.update({'mass': array_types.mass})
        self.name = 'mass'

    def initialize(self, num_new_particles, spill, data_arrays, substance):
        if spill.plume_gen is None:
            raise ValueError('plume_gen attribute of spill is None - cannot'
                             ' compute mass without plume mass flux')

        data_arrays['mass'][-num_new_particles:] = \
            spill.plume_gen.mass_of_an_le * 1000


class DistributionBaseSchema(base_schema.ObjType):
    'Add schema to base class since all derived classes use same schema'
    description = 'dynamically adds distribution schema to self'

    def __init__(self, **kwargs):
        dist = kwargs.pop('distribution')
        self.add(dist)
        super(DistributionBaseSchema, self).__init__(**kwargs)


class DistributionBase(InitBaseClass, Serializable):
    '''
    Define a base class for all initializers that contain a distribution.
    Keep the code to serialize/deserialize distribution objects here so we only
    have to write it once.
    '''
    _state = copy.deepcopy(InitBaseClass._state)
    _state.add(save=['distribution'], update=['distribution'])
    _schema = DistributionBaseSchema

    def serialize(self, json_='webapi'):
        'Add distribution schema based on "distribution" - then serialize'

        dict_ = self.to_serialize(json_)
        schema = self.__class__._schema(name=self.__class__.__name__,
                   distribution=self.distribution._schema(name='distribution'))
        return schema.serialize(dict_)

    @classmethod
    def deserialize(cls, json_):
        'Add distribution schema based on "distribution" - then deserialize'
        dist_type = json_['distribution']['obj_type']
        to_eval = "{0}._schema(name='distribution')".format(dist_type)
        dist_schema = eval(to_eval)
        schema = cls._schema(name=cls.__name__, distribution=dist_schema)
        dict_ = schema.deserialize(json_)

        # convert nested object ['distribution'] saved as a
        # dict, back to an object if json_ == 'save' here itself
        if json_['json_'] == 'save':
            distribution = dict_.get('distribution')
            to_eval = '{0}.new_from_dict(distribution)'.format(
                                                    distribution['obj_type'])
            dict_['distribution'] = eval(to_eval)

        return dict_


class InitRiseVelFromDist(DistributionBase):
    _state = copy.deepcopy(DistributionBase._state)

    def __init__(self, distribution=None, **kwargs):
        """
        Set the rise velocity parameters to be sampled from a distribution.

        Use distribution to define rise_vel

        :param distribution: An object capable of generating a probability
                             distribution.
        :type distribution: Right now, we have:
                              - UniformDistribution
                              - NormalDistribution
                              - LogNormalDistribution
                              - WeibullDistribution
                            New distribution classes could be made.  The only
                            requirement is they need to have a set_values()
                            method which accepts a NumPy array.
                            (presumably, this function will also modify
                             the array in some way)
        """
        super(InitRiseVelFromDist, self).__init__(**kwargs)

        if distribution:
            self.distribution = distribution
        else:
            self.distribution = UniformDistribution()

        self.array_types.update({'rise_vel': array_types.rise_vel})
        self.name = 'rise_vel'

    def initialize(self, num_new_particles, spill, data_arrays,
                   substance=None):
        'Update values of "rise_vel" data array for new particles'
        self.distribution.set_values(
                            data_arrays['rise_vel'][-num_new_particles:])


class InitRiseVelFromDropletSizeFromDist(DistributionBase):
    _state = copy.deepcopy(DistributionBase._state)

    def __init__(self, distribution=None,
                 water_density=1020.0, water_viscosity=1.0e-6,
                 **kwargs):
        """
        Set the droplet size from a distribution. Use the C++ get_rise_velocity
        function exposed via cython (rise_velocity_from_drop_size) to obtain
        rise_velocity from droplet size. Even though the droplet size is not
        changing over time, it is still stored in data array, as it can be
        useful for post-processing (called 'droplet_diameter')

        Use distribution to define rise_vel

        :param distribution: An object capable of generating a probability
                             distribution.
        :type distribution: Right now, we have:
                              - UniformDistribution
                              - NormalDistribution
                              - LogNormalDistribution
                              - WeibullDistribution
                            New distribution classes could be made.  The only
                            requirement is they need to have a set_values()
                            method which accepts a NumPy array.
                            (presumably, this function will also modify
                             the array in some way)

        :param water_density: 1020.0 [kg/m3]
        :type water_density: float
        :param water_viscosity: 1.0e-6 [m^2/s]
        :type water_viscosity: float
        """
        super(InitRiseVelFromDropletSizeFromDist, self).__init__(**kwargs)

        if distribution:
            self.distribution = distribution
        else:
            self.distribution = UniformDistribution()

        self.water_viscosity = water_viscosity
        self.water_density = water_density
        self.array_types.update({'rise_vel': array_types.rise_vel,
                            'droplet_diameter': array_types.droplet_diameter})
        self.name = 'rise_vel'

    def initialize(self, num_new_particles, spill, data_arrays, substance):
        """
        Update values of 'rise_vel' and 'droplet_diameter' data arrays for
        new particles. First create a droplet_size array sampled from specified
        distribution, then use the cython wrapped (C++) function to set the
        'rise_vel' based on droplet size and properties like LE_density,
        water density and water_viscosity:
        gnome.cy_gnome.cy_rise_velocity_mover.rise_velocity_from_drop_size()
        """
        drop_size = np.zeros((num_new_particles, ), dtype=np.float64)
        le_density = np.zeros((num_new_particles, ), dtype=np.float64)

        self.distribution.set_values(drop_size)

        data_arrays['droplet_diameter'][-num_new_particles:] = drop_size
        le_density[:] = substance.get_density()

        # now update rise_vel with droplet size - dummy for now
        rise_velocity_from_drop_size(
                                data_arrays['rise_vel'][-num_new_particles:],
                                le_density, drop_size,
                                self.water_viscosity, self.water_density)
