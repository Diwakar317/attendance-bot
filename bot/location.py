from bot.config import OFFICE_LAT, OFFICE_LON, OFFICE_RADIUS_METERS
import math


def distance(lat1, lon1, lat2, lon2):

    R = 6371000

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi/2)**2 +
        math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    )

    return R * (2*math.atan2(math.sqrt(a), math.sqrt(1-a)))


def is_valid_location(lat, lon):

    return distance(lat, lon, OFFICE_LAT, OFFICE_LON) <= OFFICE_RADIUS_METERS
