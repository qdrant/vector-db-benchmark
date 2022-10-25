MIN_LAT, MAX_LAT = -85.05112878, 85.05112878


def epsg_4326_to_900913(lon, lat):
    if MIN_LAT <= lat <= MAX_LAT:
        return lon, lat
    if lat < MIN_LAT:
        return lon, MIN_LAT
    return lon, MAX_LAT
