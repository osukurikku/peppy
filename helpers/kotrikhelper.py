import math
from objects import glob

def secondsToFormatted(length):
  return f"{math.floor(length / 60)}:{str(length % 60)}"


def setUserLastOsuVer(userID: int, osuVer: str):
	"""
	Set userID's osu ver

	:param userID int: user id
	:param osuVer str: osu ver
	:return:
	"""
	glob.db.execute("UPDATE users SET osuver = %s WHERE id = %s LIMIT 1", [osuVer, userID])