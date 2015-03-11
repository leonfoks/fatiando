r"""
Calculates the potential fields of a tesseroid (spherical prism).

.. admonition:: Coordinate systems

    The gravitational attraction
    and gravity gradient tensor
    are calculated with respect to
    the local coordinate system of the computation point.
    This system has **x -> North**, **y -> East**, **z -> up**
    (radial direction).

**Gravity**

.. warning:: The :math:`g_z` component is an **exception** to this.
    In order to conform with the regular convention
    of z-axis pointing toward the center of the Earth,
    **this component only** is calculated with **z -> Down**.
    This way, gravity anomalies of
    tesseroids with positive density
    are positive, not negative.

Functions:
:func:`~fatiando.gravmag.prism.potential`,
:func:`~fatiando.gravmag.prism.gx`,
:func:`~fatiando.gravmag.prism.gy`,
:func:`~fatiando.gravmag.prism.gz`,
:func:`~fatiando.gravmag.prism.gxx`,
:func:`~fatiando.gravmag.prism.gxy`,
:func:`~fatiando.gravmag.prism.gxz`,
:func:`~fatiando.gravmag.prism.gyy`,
:func:`~fatiando.gravmag.prism.gyz`,
:func:`~fatiando.gravmag.prism.gzz`

The gravitational fields are calculated using the formula of Grombein et al.
(2013):

.. math::
    V(r,\phi,\lambda) = G \rho
        \displaystyle\int_{\lambda_1}^{\lambda_2}
        \displaystyle\int_{\phi_1}^{\phi_2}
        \displaystyle\int_{r_1}^{r_2}
        \frac{1}{\ell} \kappa \ d r' d \phi' d \lambda'

.. math::
    g_{\alpha}(r,\phi,\lambda) = G \rho
        \displaystyle\int_{\lambda_1}^{\lambda_2}
        \displaystyle\int_{\phi_1}^{\phi_2} \displaystyle\int_{r_1}^{r_2}
        \frac{\Delta_{\alpha}}{\ell^3} \kappa \ d r' d \phi' d \lambda'
        \ \ \alpha \in \{x,y,z\}

.. math::
    g_{\alpha\beta}(r,\phi,\lambda) = G \rho
        \displaystyle\int_{\lambda_1}^{\lambda_2}
        \displaystyle\int_{\phi_1}^{\phi_2} \displaystyle\int_{r_1}^{r_2}
        I_{\alpha\beta}({r'}, {\phi'}, {\lambda'} )
        \ d r' d \phi' d \lambda'
        \ \ \alpha,\beta \in \{x,y,z\}

.. math::
    I_{\alpha\beta}({r'}, {\phi'}, {\lambda'}) =
        \left(
            \frac{3\Delta_{\alpha} \Delta_{\beta}}{\ell^5} -
            \frac{\delta_{\alpha\beta}}{\ell^3}
        \right)
        \kappa\
        \ \ \alpha,\beta \in \{x,y,z\}

where :math:`\rho` is density,
:math:`\{x, y, z\}` correspond to the local coordinate system
of the computation point P,
:math:`\delta_{\alpha\beta}` is the `Kronecker delta`_, and

.. math::
   :nowrap:

    \begin{eqnarray*}
        \Delta_x &=& r' K_{\phi} \\
        \Delta_y &=& r' \cos \phi' \sin(\lambda' - \lambda) \\
        \Delta_z &=& r' \cos \psi - r\\
        \ell &=& \sqrt{r'^2 + r^2 - 2 r' r \cos \psi} \\
        \cos\psi &=& \sin\phi\sin\phi' + \cos\phi\cos\phi'
                     \cos(\lambda' - \lambda) \\
        K_{\phi} &=& \cos\phi\sin\phi' - \sin\phi\cos\phi'
                     \cos(\lambda' - \lambda)\\
        \kappa &=& {r'}^2 \cos \phi'
    \end{eqnarray*}


:math:`\phi` is latitude,
:math:`\lambda` is longitude, and
:math:`r` is radius.

.. _Kronecker delta: http://en.wikipedia.org/wiki/Kronecker_delta

**Numerical integration**

The above integrals are solved using the Gauss-Legendre Quadrature rule
(Asgharzadeh et al., 2007;
Wild-Pfeiffer, 2008):

.. math::
    g_{\alpha\beta}(r,\phi,\lambda) \approx G \rho
        \frac{(\lambda_2 - \lambda_1)(\phi_2 - \phi_1)(r_2 - r_1)}{8}
        \displaystyle\sum_{k=1}^{N^{\lambda}}
        \displaystyle\sum_{j=1}^{N^{\phi}}
        \displaystyle\sum_{i=1}^{N^r}
        W^r_i W^{\phi}_j W^{\lambda}_k
        I_{\alpha\beta}({r'}_i, {\phi'}_j, {\lambda'}_k )
        \ \alpha,\beta \in \{1,2,3\}

where :math:`W_i^r`, :math:`W_j^{\phi}`, and :math:`W_k^{\lambda}`
are weighting coefficients
and :math:`N^r`, :math:`N^{\phi}`, and :math:`N^{\lambda}`
are the number of quadrature nodes
(i.e., the order of the quadrature),
for the radius, latitude, and longitude, respectively.


**References**

Asgharzadeh, M. F., R. R. B. von Frese, H. R. Kim, T. E. Leftwich,
and J. W. Kim (2007),
Spherical prism gravity effects by Gauss-Legendre quadrature integration,
Geophysical Journal International, 169(1), 1-11,
doi:10.1111/j.1365-246X.2007.03214.x.

Grombein, T.; Seitz, K.; Heck, B. (2013), Optimized formulas for the
gravitational field of a tesseroid, Journal of Geodesy,
doi: 10.1007/s00190-013-0636-1

Wild-Pfeiffer, F. (2008),
A comparison of different mass elements for use in gravity gradiometry,
Journal of Geodesy, 82(10), 637-653, doi:10.1007/s00190-008-0219-8.


----

"""
from __future__ import division
import multiprocessing

import numpy as np
try:
    import numba
    from . import _tesseroid_numba
except ImportError:
    numba = None
try:
    from . import _tesseroid
except ImportError:
    cython = None

from ..constants import SI2MGAL, SI2EOTVOS, MEAN_EARTH_RADIUS, G

RATIO_V = 1
RATIO_G = 1.6
RATIO_GG = 8
STACK_SIZE = 500


def _check_input(lon, lat, height, model, ratio, njobs):
    """
    Check if the inputs are as expected and generate the output array.
    """
    assert lon.shape == lat.shape == height.shape, \
        "Input coordinate arrays must have same shape"
    assert ratio > 0, "Invalid ratio {}. Must be > 0.".format(ratio)
    assert njobs > 0, "Invalid number of jobs {}. Must be > 0.".format(njobs)
    result = np.zeros_like(lon)
    return result


def _convert_coords(lon, lat, height):
    """
    Convert angles to radians and heights to radius.

    Pre-compute the sine and cossine of latitude because that is what we need
    from it.
    """
    # Convert things to radians
    lon = np.radians(lon)
    lat = np.radians(lat)
    sinlat = np.sin(lat)
    coslat = np.cos(lat)
    # Transform the heights into radius
    radius = MEAN_EARTH_RADIUS + height
    return lon, sinlat, coslat, radius


def _get_engine(engine):
    """
    Get the correct module to perform the computations.

    Options are the Cython version, a pure Python version, and a numba version.
    """
    if engine == 'default':
        if numba is None:
            engine = 'numpy'
        else:
            engine = 'numba'
    assert engine in ['numpy', 'numba'], \
        "Invalid compute module {}".fotmat(engine)
    if engine == 'numba':
        module = _tesseroid_numba
    elif engine == 'numpy':
        module = _tesseroid_numpy
    return module


def _get_density(tesseroid, dens):
    """
    Get the density information from the tesseroid or the given value.
    """
    if tesseroid is None:
        return None
    if 'density' not in tesseroid.props and dens is None:
        return None
    if dens is not None:
        density = dens
    else:
        density = tesseroid.props['density']
    return density


def _dispatcher(args):
    """
    Run the computations on the model for a given list of arguments.

    This is used because multiprocessing.Pool.map can only use functions that
    receive a single argument.

    Arguments should be, in order:

    lon, lat, height, result, model, dens, ratio, engine, field
    """
    lon, lat, height, result, model, dens, ratio, engine, field = args
    lon, sinlat, coslat, radius = _convert_coords(lon, lat, height)
    module = _get_engine(engine)
    func = getattr(module, field)
    for tesseroid in model:
        density = _get_density(tesseroid, dens)
        if density is None:
            continue
        func(lon, sinlat, coslat, radius, tesseroid, density, ratio,
             STACK_SIZE, result)
    return result


def _split_arrays(arrays, extra_args, nparts):
    """
    Split the coordinate arrays into nparts. Add extra_args to each part.

    Example::

    >>> chunks = _split_arrays([[1, 2, 3]], ['meh'], 3)
    >>> chunks[0]
    [1, 'meh']
    >>> chunks[1]
    [2, 'meh']
    >>> chunks[2]
    [3, 'meh']

    """
    size = len(arrays[0])
    n = size//nparts
    strides = [(i*n, (i + 1)*n) for i in xrange(nparts - 1)]
    strides.append((strides[-1][-1], size))
    chunks = [[x[low:high] for x in arrays] + extra_args
              for low, high in strides]
    return chunks


def potential(lon, lat, height, model, dens=None, ratio=RATIO_V,
              engine='default', njobs=1):
    """
    Calculate the gravitational potential due to a tesseroid model.

    Parameters:

    * lon, lat, height : arrays
        Arrays with the longitude, latitude and height coordinates of the
        computation points.
    * model : list of :class:`~fatiando.mesher.Tesseroid`
        The density model used to calculate the gravitational effect.
        Tesseroids must have the property ``'density'``. Those that don't have
        this property will be ignored in the computations. Elements that are
        None will also be ignored.
    * dens : float or None
        If not None, will use this value instead of the ``'density'`` property
        of the tesseroids. Use this, e.g., for sensitivity matrix building.
    * ratio : float
        Will divide each tesseroid until the distance between it and the
        computation points is < ratio*size of tesseroid. Used to guarantee the
        accuracy of the numerical integration.

    Returns:

    * res : array
        The calculated field in SI units

    """
    result = _check_input(lon, lat, height, model, ratio, njobs)
    field = 'potential'
    if njobs == 1:
        _dispatcher([lon, lat, height, result, model, dens, ratio, engine,
                     field])
    else:
        chunks = _split_arrays(arrays=[lon, lat, height, result],
                               extra_args=[model, dens, ratio, engine, field],
                               nparts=njobs)
        pool = multiprocessing.Pool(njobs)
        result = np.hstack(pool.map(_dispatcher, chunks))
        pool.close()
    result *= G
    return result


def gx(lon, lat, height, model, dens=None, ratio=RATIO_G, engine='default',
       njobs=1):
    """
    Calculate the North component of the gravitational attraction.

    Parameters:

    * lon, lat, height : arrays
        Arrays with the longitude, latitude and height coordinates of the
        computation points.
    * model : list of :class:`~fatiando.mesher.Tesseroid`
        The density model used to calculate the gravitational effect.
        Tesseroids must have the property ``'density'``. Those that don't have
        this property will be ignored in the computations. Elements that are
        None will also be ignored.
    * dens : float or None
        If not None, will use this value instead of the ``'density'`` property
        of the tesseroids. Use this, e.g., for sensitivity matrix building.
    * ratio : float
        Will divide each tesseroid until the distance between it and the
        computation points is < ratio*size of tesseroid. Used to guarantee the
        accuracy of the numerical integration.

    Returns:

    * res : array
        The calculated field in mGal

    """
    result = _check_input(lon, lat, height, model, ratio, njobs)
    field = 'gx'
    if njobs == 1:
        _dispatcher([lon, lat, height, result, model, dens, ratio, engine,
                     field])
    else:
        chunks = _split_arrays(arrays=[lon, lat, height, result],
                               extra_args=[model, dens, ratio, engine, field],
                               nparts=njobs)
        pool = multiprocessing.Pool(njobs)
        result = np.hstack(pool.map(_dispatcher, chunks))
        pool.close()
    result *= SI2MGAL*G
    return result


def gy(lon, lat, height, model, dens=None, ratio=RATIO_G, engine='default',
       njobs=1):
    """
    Calculate the East component of the gravitational attraction.

    Parameters:

    * lon, lat, height : arrays
        Arrays with the longitude, latitude and height coordinates of the
        computation points.
    * model : list of :class:`~fatiando.mesher.Tesseroid`
        The density model used to calculate the gravitational effect.
        Tesseroids must have the property ``'density'``. Those that don't have
        this property will be ignored in the computations. Elements that are
        None will also be ignored.
    * dens : float or None
        If not None, will use this value instead of the ``'density'`` property
        of the tesseroids. Use this, e.g., for sensitivity matrix building.
    * ratio : float
        Will divide each tesseroid until the distance between it and the
        computation points is < ratio*size of tesseroid. Used to guarantee the
        accuracy of the numerical integration.

    Returns:

    * res : array
        The calculated field in mGal

    """
    result = _check_input(lon, lat, height, model, ratio, njobs)
    field = 'gy'
    if njobs == 1:
        _dispatcher([lon, lat, height, result, model, dens, ratio, engine,
                     field])
    else:
        chunks = _split_arrays(arrays=[lon, lat, height, result],
                               extra_args=[model, dens, ratio, engine, field],
                               nparts=njobs)
        pool = multiprocessing.Pool(njobs)
        result = np.hstack(pool.map(_dispatcher, chunks))
        pool.close()
    result *= SI2MGAL*G
    return result


def gz(lon, lat, height, model, dens=None, ratio=RATIO_G, engine='default',
       njobs=1):
    """
    Calculate the radial component of the gravitational attraction.

    .. warning::
        In order to conform with the regular convention of positive density
        giving positive gz values, **this component only** is calculated
        with **z axis -> Down**.

    Parameters:

    * lon, lat, height : arrays
        Arrays with the longitude, latitude and height coordinates of the
        computation points.
    * model : list of :class:`~fatiando.mesher.Tesseroid`
        The density model used to calculate the gravitational effect.
        Tesseroids must have the property ``'density'``. Those that don't have
        this property will be ignored in the computations. Elements that are
        None will also be ignored.
    * dens : float or None
        If not None, will use this value instead of the ``'density'`` property
        of the tesseroids. Use this, e.g., for sensitivity matrix building.
    * ratio : float
        Will divide each tesseroid until the distance between it and the
        computation points is < ratio*size of tesseroid. Used to guarantee the
        accuracy of the numerical integration.

    Returns:

    * res : array
        The calculated field in mGal

    """
    result = _check_input(lon, lat, height, model, ratio, njobs)
    field = 'gz'
    if njobs == 1:
        _dispatcher([lon, lat, height, result, model, dens, ratio, engine,
                     field])
    else:
        chunks = _split_arrays(arrays=[lon, lat, height, result],
                               extra_args=[model, dens, ratio, engine, field],
                               nparts=njobs)
        pool = multiprocessing.Pool(njobs)
        result = np.hstack(pool.map(_dispatcher, chunks))
        pool.close()
    result *= SI2MGAL*G
    return result


def gxx(lon, lat, height, model, dens=None, ratio=RATIO_GG, engine='default',
        njobs=1):
    """
    Calculate the xx component of the gravity gradient tensor.

    Parameters:

    * lon, lat, height : arrays
        Arrays with the longitude, latitude and height coordinates of the
        computation points.
    * model : list of :class:`~fatiando.mesher.Tesseroid`
        The density model used to calculate the gravitational effect.
        Tesseroids must have the property ``'density'``. Those that don't have
        this property will be ignored in the computations. Elements that are
        None will also be ignored.
    * dens : float or None
        If not None, will use this value instead of the ``'density'`` property
        of the tesseroids. Use this, e.g., for sensitivity matrix building.
    * ratio : float
        Will divide each tesseroid until the distance between it and the
        computation points is < ratio*size of tesseroid. Used to guarantee the
        accuracy of the numerical integration.

    Returns:

    * res : array
        The calculated field in Eotvos

    """
    result = _check_input(lon, lat, height, model, ratio, njobs)
    field = 'gxx'
    if njobs == 1:
        _dispatcher([lon, lat, height, result, model, dens, ratio, engine,
                     field])
    else:
        chunks = _split_arrays(arrays=[lon, lat, height, result],
                               extra_args=[model, dens, ratio, engine, field],
                               nparts=njobs)
        pool = multiprocessing.Pool(njobs)
        result = np.hstack(pool.map(_dispatcher, chunks))
        pool.close()
    result *= SI2EOTVOS*G
    return result


def gxy(lon, lat, height, model, dens=None, ratio=RATIO_GG, engine='default',
        njobs=1):
    """
    Calculate the xy component of the gravity gradient tensor.

    Parameters:

    * lon, lat, height : arrays
        Arrays with the longitude, latitude and height coordinates of the
        computation points.
    * model : list of :class:`~fatiando.mesher.Tesseroid`
        The density model used to calculate the gravitational effect.
        Tesseroids must have the property ``'density'``. Those that don't have
        this property will be ignored in the computations. Elements that are
        None will also be ignored.
    * dens : float or None
        If not None, will use this value instead of the ``'density'`` property
        of the tesseroids. Use this, e.g., for sensitivity matrix building.
    * ratio : float
        Will divide each tesseroid until the distance between it and the
        computation points is < ratio*size of tesseroid. Used to guarantee the
        accuracy of the numerical integration.

    Returns:

    * res : array
        The calculated field in Eotvos

    """
    result = _check_input(lon, lat, height, model, ratio, njobs)
    field = 'gxy'
    if njobs == 1:
        _dispatcher([lon, lat, height, result, model, dens, ratio, engine,
                     field])
    else:
        chunks = _split_arrays(arrays=[lon, lat, height, result],
                               extra_args=[model, dens, ratio, engine, field],
                               nparts=njobs)
        pool = multiprocessing.Pool(njobs)
        result = np.hstack(pool.map(_dispatcher, chunks))
        pool.close()
    result *= SI2EOTVOS*G
    return result


def gxz(lon, lat, height, model, dens=None, ratio=RATIO_GG, engine='default',
        njobs=1):
    """
    Calculate the xz component of the gravity gradient tensor.

    Parameters:

    * lon, lat, height : arrays
        Arrays with the longitude, latitude and height coordinates of the
        computation points.
    * model : list of :class:`~fatiando.mesher.Tesseroid`
        The density model used to calculate the gravitational effect.
        Tesseroids must have the property ``'density'``. Those that don't have
        this property will be ignored in the computations. Elements that are
        None will also be ignored.
    * dens : float or None
        If not None, will use this value instead of the ``'density'`` property
        of the tesseroids. Use this, e.g., for sensitivity matrix building.
    * ratio : float
        Will divide each tesseroid until the distance between it and the
        computation points is < ratio*size of tesseroid. Used to guarantee the
        accuracy of the numerical integration.

    Returns:

    * res : array
        The calculated field in Eotvos

    """
    result = _check_input(lon, lat, height, model, ratio, njobs)
    field = 'gxz'
    if njobs == 1:
        _dispatcher([lon, lat, height, result, model, dens, ratio, engine,
                     field])
    else:
        chunks = _split_arrays(arrays=[lon, lat, height, result],
                               extra_args=[model, dens, ratio, engine, field],
                               nparts=njobs)
        pool = multiprocessing.Pool(njobs)
        result = np.hstack(pool.map(_dispatcher, chunks))
        pool.close()
    result *= SI2EOTVOS*G
    return result


def gyy(lon, lat, height, model, dens=None, ratio=RATIO_GG, engine='default',
        njobs=1):
    """
    Calculate the yy component of the gravity gradient tensor.

    Parameters:

    * lon, lat, height : arrays
        Arrays with the longitude, latitude and height coordinates of the
        computation points.
    * model : list of :class:`~fatiando.mesher.Tesseroid`
        The density model used to calculate the gravitational effect.
        Tesseroids must have the property ``'density'``. Those that don't have
        this property will be ignored in the computations. Elements that are
        None will also be ignored.
    * dens : float or None
        If not None, will use this value instead of the ``'density'`` property
        of the tesseroids. Use this, e.g., for sensitivity matrix building.
    * ratio : float
        Will divide each tesseroid until the distance between it and the
        computation points is < ratio*size of tesseroid. Used to guarantee the
        accuracy of the numerical integration.

    Returns:

    * res : array
        The calculated field in Eotvos

    """
    result = _check_input(lon, lat, height, model, ratio, njobs)
    field = 'gyy'
    if njobs == 1:
        _dispatcher([lon, lat, height, result, model, dens, ratio, engine,
                     field])
    else:
        chunks = _split_arrays(arrays=[lon, lat, height, result],
                               extra_args=[model, dens, ratio, engine, field],
                               nparts=njobs)
        pool = multiprocessing.Pool(njobs)
        result = np.hstack(pool.map(_dispatcher, chunks))
        pool.close()
    result *= SI2EOTVOS*G
    return result


def gyz(lon, lat, height, model, dens=None, ratio=RATIO_GG, engine='default',
        njobs=1):
    """
    Calculate the yz component of the gravity gradient tensor.

    Parameters:

    * lon, lat, height : arrays
        Arrays with the longitude, latitude and height coordinates of the
        computation points.
    * model : list of :class:`~fatiando.mesher.Tesseroid`
        The density model used to calculate the gravitational effect.
        Tesseroids must have the property ``'density'``. Those that don't have
        this property will be ignored in the computations. Elements that are
        None will also be ignored.
    * dens : float or None
        If not None, will use this value instead of the ``'density'`` property
        of the tesseroids. Use this, e.g., for sensitivity matrix building.
    * ratio : float
        Will divide each tesseroid until the distance between it and the
        computation points is < ratio*size of tesseroid. Used to guarantee the
        accuracy of the numerical integration.

    Returns:

    * res : array
        The calculated field in Eotvos

    """
    result = _check_input(lon, lat, height, model, ratio, njobs)
    field = 'gyz'
    if njobs == 1:
        _dispatcher([lon, lat, height, result, model, dens, ratio, engine,
                     field])
    else:
        chunks = _split_arrays(arrays=[lon, lat, height, result],
                               extra_args=[model, dens, ratio, engine, field],
                               nparts=njobs)
        pool = multiprocessing.Pool(njobs)
        result = np.hstack(pool.map(_dispatcher, chunks))
        pool.close()
    result *= SI2EOTVOS*G
    return result


def gzz(lon, lat, height, model, dens=None, ratio=RATIO_GG, engine='default',
        njobs=1):
    """
    Calculate the zz component of the gravity gradient tensor.

    Parameters:

    * lon, lat, height : arrays
        Arrays with the longitude, latitude and height coordinates of the
        computation points.
    * model : list of :class:`~fatiando.mesher.Tesseroid`
        The density model used to calculate the gravitational effect.
        Tesseroids must have the property ``'density'``. Those that don't have
        this property will be ignored in the computations. Elements that are
        None will also be ignored.
    * dens : float or None
        If not None, will use this value instead of the ``'density'`` property
        of the tesseroids. Use this, e.g., for sensitivity matrix building.
    * ratio : float
        Will divide each tesseroid until the distance between it and the
        computation points is < ratio*size of tesseroid. Used to guarantee the
        accuracy of the numerical integration.

    Returns:

    * res : array
        The calculated field in Eotvos

    """
    result = _check_input(lon, lat, height, model, ratio, njobs)
    field = 'gzz'
    if njobs == 1:
        _dispatcher([lon, lat, height, result, model, dens, ratio, engine,
                     field])
    else:
        chunks = _split_arrays(arrays=[lon, lat, height, result],
                               extra_args=[model, dens, ratio, engine, field],
                               nparts=njobs)
        pool = multiprocessing.Pool(njobs)
        result = np.hstack(pool.map(_dispatcher, chunks))
        pool.close()
    result *= SI2EOTVOS*G
    return result
