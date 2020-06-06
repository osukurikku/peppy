from objects import glob
from constants import clientPackets, serverPackets
from common.log import logUtils as log

def handle(userToken, packetData):
	# get token data
	userID = userToken.userID

	# Send spectator frames to every spectator
	streamName = "spect/{}".format(userID)

	data = clientPackets.readSpectatorFrame(packetData)
	glob.streams.broadcast(streamName, serverPackets.spectatorFrames(data))
	log.debug("Broadcasting {}'s frames to {} clients".format(
		userID,
		len(glob.streams.streams[streamName].clients))
	)