import math

def secondsToFormatted(length):
  return f"{math.floor(length / 60)}:{str(length % 60)}"
