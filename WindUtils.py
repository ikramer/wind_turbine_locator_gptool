import math

def getBearing(x1, y1, x2, y2):
    distX = math.abs(x2 - x1)
    y = math.sin(distX) * math.cos(y2)
    x = math.cos(y1) * math.sin(y2) - math.sin(y1) * math.cos(y2) * math.cos(distX)
    bearing = math.atan2(y, x)
    return bearing * (180 / math.pi)

def checkInList(list, val):
    for item in list:
        if item == val:
            return True

    return False