from typing import Tuple

MIN_LAT, MAX_LAT = -85.05112878, 85.05112878


def convert_to_redis_coords(lon: float, lat: float) -> Tuple[float, float]:
    """
    Redis uses a different coordinate system for storing the geocoordinates
    (EPSG:900913 / EPSG:3785 / OSGEO:41001) which is a subset of the WSG84 used
    by the other engines. Redis can only represent longitudes from -180 to 180
    degrees and latitudes are from -85.05112878 to 85.05112878 degrees.
    :param lon:
    :param lat:
    :return:
    """
    if MIN_LAT <= lat <= MAX_LAT:
        return lon, lat
    if lat < MIN_LAT:
        return lon, MIN_LAT
    return lon, MAX_LAT
