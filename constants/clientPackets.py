from constants import dataTypes
from helpers import packetHelper
from constants import slotStatuses


""" Users listing packets """
def userActionChange(stream):
	return packetHelper.readPacketData(stream,
	[
		["actionID", dataTypes.BYTE],
		["actionText", dataTypes.STRING],
		["actionMd5", dataTypes.STRING],
		["actionMods", dataTypes.UINT32],
		["gameMode", dataTypes.BYTE],
		["beatmapID", dataTypes.SINT32]
	])

def userStatsRequest(stream):
	return packetHelper.readPacketData(stream, [["users", dataTypes.INT_LIST]])

def userPanelRequest(stream):
	return packetHelper.readPacketData(stream, [["users", dataTypes.INT_LIST]])


""" Client chat packets """
def sendPublicMessage(stream):
	return packetHelper.readPacketData(stream,
	[
		["unknown", dataTypes.STRING],
		["message", dataTypes.STRING],
		["to", dataTypes.STRING]
	])

def sendPrivateMessage(stream):
	return packetHelper.readPacketData(stream,
	[
		["unknown", dataTypes.STRING],
		["message", dataTypes.STRING],
		["to", dataTypes.STRING],
		["unknown2", dataTypes.UINT32]
	])

def setAwayMessage(stream):
	return packetHelper.readPacketData(stream,
	[
		["unknown", dataTypes.STRING],
		["awayMessage", dataTypes.STRING]
	])

def channelJoin(stream):
	return packetHelper.readPacketData(stream, [["channel", dataTypes.STRING]])

def channelPart(stream):
	return packetHelper.readPacketData(stream, [["channel", dataTypes.STRING]])

def addRemoveFriend(stream):
	return packetHelper.readPacketData(stream, [["friendID", dataTypes.SINT32]])


""" Spectator packets """
def startSpectating(stream):
	return packetHelper.readPacketData(stream, [["userID", dataTypes.SINT32]])

def readSpectatorFrame(stream):
	struct = [
		["extra", dataTypes.SINT32],
		["count", dataTypes.UINT16],
	]
	firstData = packetHelper.readPacketData(stream, struct)

	if firstData["count"] > 0:
		for i in range(0, firstData["count"]):
			# okay now add to struct
			struct.extend([
				[f"____frames_{i}_ButtonState", dataTypes.BYTE],
				[f"____frames_{i}_Button", dataTypes.BYTE],
				[f"____frames_{i}_MouseX", dataTypes.FFLOAT],
				[f"____frames_{i}_MouseY", dataTypes.FFLOAT],
				[f"____frames_{i}_Time", dataTypes.SINT32]
			])
	
	struct.extend([
		["action", dataTypes.BYTE],
		["time", dataTypes.SINT32],
		["id", dataTypes.BYTE],
		["count300", dataTypes.UINT16],
		["count100", dataTypes.UINT16],
		["count50", dataTypes.UINT16],
		["countGeki", dataTypes.UINT16],
		["countKatu", dataTypes.UINT16],
		["countMiss", dataTypes.UINT16],
		["totalScore", dataTypes.SINT32],
		["maxCombo", dataTypes.UINT16],
		["currentCombo", dataTypes.UINT16],
		["perfect", dataTypes.BYTE],
		["currentHp", dataTypes.BYTE],
		["tagByte", dataTypes.BYTE],
		["usingScoreV2", dataTypes.BYTE]
	])

	#print(struct)
	partly = packetHelper.readPacketData(stream, struct)
	if bool(partly['usingScoreV2']):
		struct.extend([
			["comboPortion", dataTypes.FFLOAT],
			["bonusPortion", dataTypes.FFLOAT]
		])
	
	data = packetHelper.readPacketData(stream, struct)
	if not 'comboPortion' in data and not 'bonusPortion' in data:
		data['comboPortion'] = 0
		data['bonusPortion'] = 0

	cleared_data = {}
	for (k, v) in data.items():
		if k.startswith("____"):
			k = k.replace("____", "")
			info = k.split("_")		
			if not info[0] in cleared_data:
				cleared_data[info[0]] = []
			#cleared_data.frames = []

			if len(cleared_data[info[0]]) < int(info[1])+1:
				cleared_data[info[0]].append({})
			#cleared_data.frames[].position{}
			
			cleared_data[info[0]][int(info[1])][info[2]] = v
			continue
		
		cleared_data[k] = v

	return cleared_data

""" Multiplayer packets """
def matchSettings(stream):
	# Data to return, will be merged later
	data = []

	# Some settings
	struct = [
		["matchID", dataTypes.UINT16],
		["inProgress", dataTypes.BYTE],
		["matchType", dataTypes.BYTE],
		["mods", dataTypes.UINT32],
		["matchName", dataTypes.STRING],
		["matchPassword", dataTypes.STRING],
		["beatmapName", dataTypes.STRING],
		["beatmapID", dataTypes.UINT32],
		["beatmapMD5", dataTypes.STRING]
	]

	# Slot statuses
	for i in range(0,16):
		struct.append(["slot{}Status".format(str(i)), dataTypes.BYTE])

	# Slot statuses
	for i in range(0,16):
		struct.append(["slot{}Team".format(str(i)), dataTypes.BYTE])

	# New multiplayer packet struct by @KotRikD
	slotData = packetHelper.readPacketData(stream, struct) # read part I

	for i in range(0,16):
		# Get status
		s = slotData["slot{}Status".format(str(i))]
		if s & (4 | 8 | 16 | 32 | 64) > 0:
			# user exists on that slot
			# add new entrie to struct
			struct.append(["slot{}UserId".format(str(i)), dataTypes.SINT32])

	# Now extend struct by osu packet values
	struct.extend([
		["hostUserID", dataTypes.SINT32],
		["gameMode", dataTypes.BYTE],
		["scoringType", dataTypes.BYTE],
		["teamType", dataTypes.BYTE],
		["freeMods", dataTypes.BYTE],
	])

	# Now make result
	result = packetHelper.readPacketData(stream, struct)
	return result

def createMatch(stream):
	return matchSettings(stream)

def changeMatchSettings(stream):
	return matchSettings(stream)

def changeSlot(stream):
	return packetHelper.readPacketData(stream, [["slotID", dataTypes.UINT32]])

def joinMatch(stream):
	return packetHelper.readPacketData(stream, [["matchID", dataTypes.UINT32], ["password", dataTypes.STRING]])

def changeMods(stream):
	return packetHelper.readPacketData(stream, [["mods", dataTypes.UINT32]])

def lockSlot(stream):
	return packetHelper.readPacketData(stream, [["slotID", dataTypes.UINT32]])

def transferHost(stream):
	return packetHelper.readPacketData(stream, [["slotID", dataTypes.UINT32]])

def matchInvite(stream):
	return packetHelper.readPacketData(stream, [["userID", dataTypes.UINT32]])

def matchFrames(stream):
	struct = [
		["time", dataTypes.SINT32],
		["id", dataTypes.BYTE],
		["count300", dataTypes.UINT16],
		["count100", dataTypes.UINT16],
		["count50", dataTypes.UINT16],
		["countGeki", dataTypes.UINT16],
		["countKatu", dataTypes.UINT16],
		["countMiss", dataTypes.UINT16],
		["totalScore", dataTypes.SINT32],
		["maxCombo", dataTypes.UINT16],
		["currentCombo", dataTypes.UINT16],
		["perfect", dataTypes.BYTE],
		["currentHp", dataTypes.BYTE],
		["tagByte", dataTypes.BYTE],
		["usingScoreV2", dataTypes.BYTE]
	]

	return packetHelper.readPacketData(stream, struct)

def tournamentMatchInfoRequest(stream):
	return packetHelper.readPacketData(stream, [["matchID", dataTypes.UINT32]])

def tournamentJoinMatchChannel(stream):
	return packetHelper.readPacketData(stream, [["matchID", dataTypes.UINT32]])

def tournamentLeaveMatchChannel(stream):
	return packetHelper.readPacketData(stream, [["matchID", dataTypes.UINT32]])
