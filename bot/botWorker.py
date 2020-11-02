from bot.mainHandler import botCommands

import json
import random
import time

import requests
from common import generalUtils
from common.constants import gameModes
from common.constants import mods
from common.constants import privileges
from constants import countries
from common.log import logUtils as log
from common.ripple import userUtils
from common.web import cheesegull
from constants import exceptions
from constants import serverPackets
from helpers import chatHelper as chat
from helpers import systemHelper, humanize
from objects import fokabot
from objects import glob
from helpers import kotrikhelper

"""
fokaBot by ripple. Re-factored by KotRik
Instruction by KotRik

@botCommands.on_command(command=str, priviliges=int, syntax=str)
def wrapper(fro, chan, message):
    pass
    
For example:
@botCommands.on_command("!echo", priviliges=privileges.USER_DONOR, syntax="<message>")
def echo(fro, chan, message):
    return f"You write: {" ".join(message)}"

fro = Player username
chan = Channel where the message came from
If chan startswith # it's channel, any it's any player

#osu - channel
crystal - playernickname

message - it's list with arguments
e.x. 
message[0]
message[1]
message[2]

all_args = " ".join(message) - it's string with all arguments

Happy Codding!
"""


@botCommands.on_command("!ir", privileges=privileges.ADMIN_MANAGE_SERVERS)
def instant_restart(fro, chan, message):
    glob.streams.broadcast("main", serverPackets.notification("We are restarting Bancho. Be right back!"))
    systemHelper.scheduleShutdown(0, True, delay=5)
    return False


@botCommands.on_command("!faq", syntax="<name>")
def faq(fro, chan, message):
    key = message[0].lower()
    if key not in glob.conf.extra["faq"]:
        return False
    return glob.conf.extra["faq"][key]


@botCommands.on_command("!roll")
def roll(fro, chan, message):
    maxPoints = 100
    if len(message) >= 1:
        if message[0].isdigit() == True and int(message[0]) > 0:
            maxPoints = int(message[0])

    points = random.randrange(0, maxPoints)
    return "{} rolls {} points!".format(fro, str(points))


@botCommands.on_command("!alert", syntax="<message>", privileges=privileges.ADMIN_SEND_ALERTS)
def alert(fro, chan, message):
    msg = ' '.join(message[:]).strip()
    if not msg:
        return False
    glob.streams.broadcast("main", serverPackets.notification(msg))
    return False

@botCommands.on_command("!useralert", syntax="<message>", privileges=privileges.ADMIN_SEND_ALERTS)
def alertUser(fro, chan, message):
    target = message[0].lower()
    targetToken = glob.tokens.getTokenFromUsername(userUtils.safeUsername(target), safe=True)
    if targetToken is not None:
        msg = ' '.join(message[1:]).strip()
        if not msg:
            return False
        targetToken.enqueue(serverPackets.notification(msg))
        return False
    else:
        return "User offline."


@botCommands.on_command("!moderated", privileges=privileges.ADMIN_CHAT_MOD)
def moderated(fro, chan, message):
    try:
        # Make sure we are in a channel and not PM
        if not chan.startswith("#"):
            raise exceptions.moderatedPMException

        # Get on/off
        enable = True
        if len(message) >= 1:
            if message[0] == "off":
                enable = False

        # Turn on/off moderated mode
        glob.channels.channels[chan].moderated = enable
        return "This channel is {} in moderated mode!".format("now" if enable else "no longer")
    except exceptions.moderatedPMException:
        return "You are trying to put a private chat in moderated mode. Are you serious?!? You're fired."


@botCommands.on_command("!kickall", privileges=privileges.ADMIN_MANAGE_SERVERS)
def kick_all(fro, chan, message):
    # Kick everyone but mods/admins
    toKick = []
    with glob.tokens:
        for key, value in glob.tokens.tokens.items():
            if not value.admin:
                toKick.append(key)

    # Loop though users to kick (we can't change dictionary size while iterating)
    for i in toKick:
        if i in glob.tokens.tokens:
            glob.tokens.tokens[i].kick()

    return "Whoops! Rip everyone."


@botCommands.on_command("!kick", syntax="<target>", privileges=privileges.ADMIN_KICK_USERS)
def kick(fro, chan, message):
    # Get parameters
    target = message[0].lower()
    if target == glob.BOT_NAME.lower():
        return "Nope."

    # Get target token and make sure is connected
    tokens = glob.tokens.getTokenFromUsername(userUtils.safeUsername(target), safe=True, _all=True)
    if len(tokens) == 0:
        return "{} is not online".format(target)

    # Kick users
    for i in tokens:
        i.kick()

    # Bot response
    return "{} has been kicked from the server.".format(target)


@botCommands.on_command("!crystal reconnect", privileges=privileges.ADMIN_MANAGE_SERVERS)
def fokabot_reconnect(fro, chan, message):
    # Check if fokabot is already connected
    if glob.tokens.getTokenFromUserID(999) is not None:
        return "{} is already connected to Bancho".format(glob.BOT_NAME)

    # Fokabot is not connected, connect it
    fokabot.connect()
    return False


@botCommands.on_command("!silence", syntax="<target> <amount> <unit(s/m/h/d)> <reason>",
                        privileges=privileges.ADMIN_SILENCE_USERS)
def silence(fro, chan, message):
    message = [x.lower() for x in message]
    target = message[0]
    amount = message[1]
    unit = message[2]
    reason = ' '.join(message[3:]).strip()
    if not reason:
        return "Please provide a valid reason."
    if not amount.isdigit():
        return "The amount must be a number."

    # Get target user ID
    targetUserID = userUtils.getIDSafe(target)
    userID = userUtils.getID(fro)

    # Make sure the user exists
    if not targetUserID:
        return "{}: user not found".format(target)

    # Calculate silence seconds
    if unit == 's':
        silenceTime = int(amount)
    elif unit == 'm':
        silenceTime = int(amount) * 60
    elif unit == 'h':
        silenceTime = int(amount) * 3600
    elif unit == 'd':
        silenceTime = int(amount) * 86400
    else:
        return "Invalid time unit (s/m/h/d)."

    # Max silence time is 7 days
    if silenceTime > 604800:
        return "Invalid silence time. Max silence time is 7 days."

    # Send silence packet to target if he's connected
    targetToken = glob.tokens.getTokenFromUsername(userUtils.safeUsername(target), safe=True)
    if targetToken is not None:
        # user online, silence both in db and with packet
        targetToken.silence(silenceTime, reason, userID)
    else:
        # User offline, silence user only in db
        userUtils.silence(targetUserID, silenceTime, reason, userID)

    # Log message
    msg = "{} has been silenced for the following reason: {}".format(target, reason)
    return msg


@botCommands.on_command("!removesilence", syntax="<target>", privileges=privileges.ADMIN_SILENCE_USERS)
def remove_silence(fro, chan, message):
    # Get parameters
    for i in message:
        i = i.lower()
    target = message[0]

    # Make sure the user exists
    targetUserID = userUtils.getIDSafe(target)
    userID = userUtils.getID(fro)
    if not targetUserID:
        return "{}: user not found".format(target)

    # Send new silence end packet to user if he's online
    targetToken = glob.tokens.getTokenFromUsername(userUtils.safeUsername(target), safe=True)
    if targetToken is not None:
        # User online, remove silence both in db and with packet
        targetToken.silence(0, "", userID)
    else:
        # user offline, remove islene ofnlt from db
        userUtils.silence(targetUserID, 0, "", userID)

    return "{}'s silence reset".format(target)


@botCommands.on_command("!ban", syntax="<target>", privileges=privileges.ADMIN_BAN_USERS)
def ban(fro, chan, message):
    # Get parameters
    for i in message:
        i = i.lower()
    target = message[0]

    # Make sure the user exists
    targetUserID = userUtils.getIDSafe(target)
    userID = userUtils.getID(fro)
    if not targetUserID:
        return "{}: user not found".format(target)

    # Set allowed to 0
    userUtils.ban(targetUserID)

    # Send ban packet to the user if he's online
    targetToken = glob.tokens.getTokenFromUsername(userUtils.safeUsername(target), safe=True)
    if targetToken is not None:
        targetToken.enqueue(serverPackets.loginBanned())

    # Posting to discord
    requests.get(glob.conf.config["discord"]["krbot"] + "api/v1/submitBanOrRestrict", params={
        'token': glob.conf.config["discord"]["krbotToken"],
        'banned': target,
        'type': 1,
        'author': fro
    })
    log.rap(userID, "has banned {}".format(target), True)
    return "RIP {}. You will not be missed.".format(target)


@botCommands.on_command("!lock", syntax="<target>", privileges=privileges.ADMIN_BAN_USERS)
def lock_user(fro, chan, message):
    # Get parameters
    for i in message:
        i = i.lower()
    target = message[0]

    # Make sure the user exists
    targetUserID = userUtils.getIDSafe(target)
    userID = userUtils.getID(fro)
    if not targetUserID:
        return "{}: user not found".format(target)

    # only lock client now ;d
    #userUtils.ban(targetUserID)

    targetToken = glob.tokens.getTokenFromUsername(userUtils.safeUsername(target), safe=True)
    if targetToken is not None:
        targetToken.enqueue(serverPackets.banClient())

    return "RIP {}. Now he have locked osu!client!".format(target)


@botCommands.on_command("!unban", syntax="<target>", privileges=privileges.ADMIN_BAN_USERS)
def unban(fro, chan, message):
    # Get parameters
    for i in message:
        i = i.lower()
    target = message[0]

    # Make sure the user exists
    targetUserID = userUtils.getIDSafe(target)
    userID = userUtils.getID(fro)
    if not targetUserID:
        return "{}: user not found".format(target)

    # Set allowed to 1
    userUtils.unban(targetUserID)
    requests.get(glob.conf.config["discord"]["krbot"] + "api/v1/submitBanOrRestrict", params={
        'token': glob.conf.config["discord"]["krbotToken"],
        'banned': target,
        'type': 3,
        'author': fro
    })

    log.rap(userID, "has unbanned {}".format(target), True)
    return "Welcome back {}!".format(target)


@botCommands.on_command("!restrict", syntax="<target>", privileges=privileges.ADMIN_BAN_USERS)
def restrict(fro, chan, message):
    # Get parameters
    for i in message:
        i = i.lower()
    target = message[0]

    # Make sure the user exists
    targetUserID = userUtils.getIDSafe(target)
    userID = userUtils.getID(fro)
    if not targetUserID:
        return "{}: user not found".format(target)

    # Put this user in restricted mode
    userUtils.restrict(targetUserID)

    # Send restricted mode packet to this user if he's online
    targetToken = glob.tokens.getTokenFromUsername(userUtils.safeUsername(target), safe=True)
    if targetToken is not None:
        targetToken.setRestricted()

    requests.get(glob.conf.config["discord"]["krbot"] + "api/v1/submitBanOrRestrict", params={
        'token': glob.conf.config["discord"]["krbotToken"],
        'banned': target,
        'type': 0,
        'author': fro
    })
    log.rap(userID, "has put {} in restricted mode".format(target), True)
    return "Bye bye {}. See you later, maybe.".format(target)


@botCommands.on_command("!unrestrict", syntax="<target>", privileges=privileges.ADMIN_BAN_USERS)
def unrestrict(fro, chan, message):
    # Get parameters
    for i in message:
        i = i.lower()
    target = message[0]

    # Make sure the user exists
    targetUserID = userUtils.getIDSafe(target)
    userID = userUtils.getID(fro)
    if not targetUserID:
        return "{}: user not found".format(target)

    # Set allowed to 1
    userUtils.unrestrict(targetUserID)
    requests.get(glob.conf.config["discord"]["krbot"] + "api/v1/submitBanOrRestrict", params={
        'token': glob.conf.config["discord"]["krbotToken"],
        'banned': target,
        'type': 2,
        'author': fro
    })

    log.rap(userID, "has removed restricted mode from {}".format(target), True)
    return "Welcome back {}!".format(target)


def restart_shutdown(restart):
    """Restart (if restart = True) or shutdown (if restart = False) pep.py safely"""
    msg = "We are performing some maintenance. Bancho will {} in 5 seconds. Thank you for your patience.".format(
        "restart" if restart else "shutdown")
    systemHelper.scheduleShutdown(5, restart, msg)
    return msg


@botCommands.on_command("!system restart", privileges=privileges.ADMIN_MANAGE_SERVERS)
def system_restart(fro, chan, message):
    return restart_shutdown(True)


@botCommands.on_command("!system shutdown", privileges=privileges.ADMIN_MANAGE_SERVERS)
def system_shutdown(fro, chan, message):
    return restart_shutdown(False)


@botCommands.on_command("!system reload", privileges=privileges.ADMIN_MANAGE_SETTINGS)
def system_reload(fro, chan, message):
    glob.banchoConf.reload()
    return "Bancho settings reloaded!"


@botCommands.on_command("!system maintenance", privileges=privileges.ADMIN_MANAGE_SERVERS)
def system_maintenance(fro, chan, message):
    # Turn on/off bancho maintenance
    maintenance = True

    # Get on/off
    if len(message) >= 2:
        if message[1] == "off":
            maintenance = False

    # Set new maintenance value in bancho_settings table
    glob.banchoConf.setMaintenance(maintenance)

    if maintenance:
        # We have turned on maintenance mode
        # Users that will be disconnected
        who = []

        # Disconnect everyone but mod/admins
        with glob.tokens:
            for _, value in glob.tokens.tokens.items():
                if not value.admin:
                    who.append(value.userID)

        glob.streams.broadcast("main", serverPackets.notification(
            "Our bancho server is in maintenance mode. Please try to login again later."))
        glob.tokens.multipleEnqueue(serverPackets.loginError(), who)
        msg = "The server is now in maintenance mode!"
    else:
        # We have turned off maintenance mode
        # Send message if we have turned off maintenance mode
        msg = "The server is no longer in maintenance mode!"

    # Chat output
    return msg


@botCommands.on_command("!system status", privileges=privileges.ADMIN_MANAGE_SERVERS)
def systemStatus(fro, chan, message):
    # Print some server info
    data = systemHelper.getSystemInfo()

    # Final message
    lets_version = glob.redis.get("lets:version")
    if lets_version is None:
        lets_version = "\_(xd)_/"
    else:
        lets_version = lets_version.decode("utf-8")
    msg = "pep.py bancho server v{}\n".format(glob.VERSION)
    msg += "LETS scores server v{}\n".format(lets_version)
    msg += "made by the Ripple team\n"
    msg += "\n"
    msg += "=== BANCHO STATS ===\n"
    msg += "Connected users: {}\n".format(data["connectedUsers"])
    msg += "Multiplayer matches: {}\n".format(data["matches"])
    msg += "Uptime: {}\n".format(data["uptime"])
    msg += "\n"
    msg += "=== SYSTEM STATS ===\n"
    msg += "CPU: {}%\n".format(data["cpuUsage"])
    msg += "RAM: {}GB/{}GB\n".format(data["usedMemory"], data["totalMemory"])
    if data["unix"]:
        msg += "Load average: {}/{}/{}\n".format(data["loadAverage"][0], data["loadAverage"][1], data["loadAverage"][2])

    return msg


def get_pp_message(userID, just_data=False):
    try:
        # Get user token
        token = glob.tokens.getTokenFromUserID(userID)
        if token is None:
            return False

        currentMap = token.tillerino[0]
        currentMods = token.tillerino[1]
        currentAcc = token.tillerino[2]

        # Send request to LETS api
        resp = requests.get("http://127.0.0.1:5002/api/v1/pp?b={}&m={}".format(currentMap, currentMods),
                            timeout=10).text
        data = json.loads(resp)

        # Make sure status is in response data
        if "status" not in data:
            raise exceptions.apiException

        # Make sure status is 200
        if data["status"] != 200:
            if "message" in data:
                return "Error in LETS API call ({}).".format(data["message"])
            else:
                raise exceptions.apiException

        if just_data:
            return data

        # Return response in chat
        # Song name and mods
        msg = "{song}{plus}{mods}  ".format(song=data["song_name"], plus="+" if currentMods > 0 else "",
                                            mods=generalUtils.readableMods(currentMods))

        # PP values
        if currentAcc == -1:
            msg += "95%: {pp95}pp | 98%: {pp98}pp | 99% {pp99}pp | 100%: {pp100}pp".format(pp100=data["pp"][0],
                                                                                           pp99=data["pp"][1],
                                                                                           pp98=data["pp"][2],
                                                                                           pp95=data["pp"][3])
        else:
            msg += "{acc:.2f}%: {pp}pp".format(acc=token.tillerino[2], pp=data["pp"][0])

        originalAR = data["ar"]
        # calc new AR if HR/EZ is on
        if (currentMods & mods.EASY) > 0:
            data["ar"] = max(0, data["ar"] / 2)
        if (currentMods & mods.HARDROCK) > 0:
            data["ar"] = min(10, data["ar"] * 1.4)

        arstr = " ({})".format(originalAR) if originalAR != data["ar"] else ""

        # Beatmap info
        msg += " | {bpm} BPM | AR {ar}{arstr} | {stars:.2f} stars".format(bpm=data["bpm"], stars=data["stars"],
                                                                          ar=data["ar"], arstr=arstr)

        # Return final message
        return msg
    except requests.exceptions.RequestException:
        # RequestException
        return "API Timeout. Please try again in a few seconds."
    except exceptions.apiException:
        # API error
        return "Unknown error in LETS API call."


@botCommands.on_command(["\x01ACTION is listening to", "\x01ACTION is playing", "\x01ACTION is watching"])
def tillerino_np(fro, chan, message):
    try:
        # Run the command in PM only
        if userUtils.getPrivileges(userUtils.getID(fro)) & privileges.USER_DONOR == 0 and chan.startswith("#"):
            return "Only donors can write here this command."

        playWatch = message[1] == "playing" or message[1] == "watching"
        # Get URL from message
        beatmap_URL = message[0][1:]

        modsEnum = 0
        mapping = {
            "-Easy": mods.EASY,
            "-NoFail": mods.NOFAIL,
            "+Hidden": mods.HIDDEN,
            "+HardRock": mods.HARDROCK,
            "+Nightcore": mods.NIGHTCORE,
            "+DoubleTime": mods.DOUBLETIME,
            "-HalfTime": mods.HALFTIME,
            "+Flashlight": mods.FLASHLIGHT,
            "-SpunOut": mods.SPUNOUT
        }

        if playWatch:
            for part in message:
                part = part.replace("\x01", "")
                if part in mapping.keys():
                    modsEnum += mapping[part]

        # Get beatmap id from URL
        beatmap_ID = fokabot.npRegex.search(beatmap_URL).groups(0)[0]

        # Update latest tillerino song for current token
        token = glob.tokens.getTokenFromUsername(fro)
        if token is not None:
            token.tillerino = [int(beatmap_ID), modsEnum, -1.0]
        userID = token.userID

        # Return tillerino message
        return get_pp_message(userID)
    except:
        return False


@botCommands.on_command("!with", syntax="<mods>")
def tillerino_mods(fro, chan, message):
    try:
        # Run the command in PM only
        if userUtils.getPrivileges(userUtils.getID(fro)) & privileges.USER_DONOR == 0 and chan.startswith("#"):
            return "Only donors can write here this command."

        # Get token and user ID
        token = glob.tokens.getTokenFromUsername(fro)
        if token is None:
            return False
        userID = token.userID

        # Make sure the user has triggered the bot with /np command
        if token.tillerino[0] == 0:
            return "Please give me a beatmap first with /np command."

        # Check passed mods and convert to enum
        modsList = [message[0][i:i + 2].upper() for i in range(0, len(message[0]), 2)]
        modsEnum = 0
        for i in modsList:
            if i not in ["NO", "NF", "EZ", "HD", "HR", "DT", "HT", "NC", "FL", "SO", "AP", "RX"]:
                return "Invalid mods. Allowed mods: NO, RX, NF, EZ, HD, HR, DT, HT, NC, FL, SO, RX, AP. Do not use spaces for multiple mods."
            if i == "NO":
                modsEnum = 0
                break
            elif i == "NF":
                modsEnum += mods.NOFAIL
            elif i == "EZ":
                modsEnum += mods.EASY
            elif i == "HD":
                modsEnum += mods.HIDDEN
            elif i == "HR":
                modsEnum += mods.HARDROCK
            elif i == "DT":
                modsEnum += mods.DOUBLETIME
            elif i == "HT":
                modsEnum += mods.HALFTIME
            elif i == "NC":
                modsEnum += mods.NIGHTCORE
            elif i == "FL":
                modsEnum += mods.FLASHLIGHT
            elif i == "SO":
                modsEnum += mods.SPUNOUT
            elif i == "AP":
                modsEnum += mods.RELAX2
            elif i == "RX":
                modsEnum += mods.RELAX

        # Set mods
        token.tillerino[1] = modsEnum

        # Return tillerino message for that beatmap with mods
        return get_pp_message(userID)
    except:
        return False


# def tillerino_acc(fro, chan, message):
#     try:
#         # Run the command in PM only
#         if chan.startswith("#"):
#             return False
#
#         # Get token and user ID
#         token = glob.tokens.getTokenFromUsername(fro)
#         if token is None:
#             return False
#         userID = token.userID
#
#         # Make sure the user has triggered the bot with /np command
#         if token.tillerino[0] == 0:
#             return "Please give me a beatmap first with /np command."
#
#         # Convert acc to float
#         acc = float(message[0])
#
#         # Set new tillerino list acc value
#         token.tillerino[2] = acc
#
#         # Return tillerino message for that beatmap with mods
#         return getPPMessage(userID)
#     except ValueError:
#         return "Invalid acc value"
#     except:
#         return False

@botCommands.on_command("!last")
def tillerinoLast(fro, chan, message):
    try:
        # Run the command in PM only
        if userUtils.getPrivileges(userUtils.getID(fro)) & privileges.USER_DONOR == 0 and chan.startswith("#"):
            return "Only donors can write here this command."

        data = glob.db.fetch("""SELECT beatmaps.song_name as sn, scores.*,
			beatmaps.beatmap_id as bid, beatmaps.difficulty_std, beatmaps.difficulty_taiko, beatmaps.difficulty_ctb, beatmaps.difficulty_mania, beatmaps.max_combo as fc
		FROM scores
		LEFT JOIN beatmaps ON beatmaps.beatmap_md5=scores.beatmap_md5
		LEFT JOIN users ON users.id = scores.userid
		WHERE users.username = %s
		ORDER BY scores.time DESC
		LIMIT 1""", [fro])
        if data is None:
            return False

        diffString = "difficulty_{}".format(gameModes.getGameModeForDB(data["play_mode"]))
        rank = generalUtils.getRank(data["play_mode"], data["mods"], data["accuracy"],
                                    data["300_count"], data["100_count"], data["50_count"], data["misses_count"])

        ifPlayer = "{0} | ".format(fro) if chan != glob.BOT_NAME else ""
        ifFc = " (FC)" if data["max_combo"] == data["fc"] else " {0}x/{1}x".format(data["max_combo"], data["fc"])
        beatmapLink = "[http://osu.ppy.sh/b/{1} {0}]".format(data["sn"], data["bid"])

        hasPP = data["play_mode"] != gameModes.CTB

        msg = ifPlayer
        msg += beatmapLink
        if data["play_mode"] != gameModes.STD:
            msg += " <{0}>".format(gameModes.getGameModeForPrinting(data["play_mode"]))

        if data["mods"]:
            msg += ' +' + generalUtils.readableMods(data["mods"])

        if not hasPP:
            msg += " | {0:,}".format(data["score"])
            msg += ifFc
            msg += " | {0:.2f}%, {1}".format(data["accuracy"], rank.upper())
            msg += " {{ {0} / {1} / {2} / {3} }}".format(data["300_count"], data["100_count"], data["50_count"],
                                                         data["misses_count"])
            msg += " | {0:.2f} stars".format(data[diffString])
            return msg

        msg += " ({0:.2f}%, {1})".format(data["accuracy"], rank.upper())
        msg += ifFc
        msg += " | {0:.2f}pp".format(data["pp"])

        stars = data[diffString]
        if data["mods"]:
            token = glob.tokens.getTokenFromUsername(fro)
            if token is None:
                return False
            userID = token.userID
            token.tillerino[0] = data["bid"]
            token.tillerino[1] = data["mods"]
            token.tillerino[2] = data["accuracy"]
            oppai_data = get_pp_message(userID, just_data=True)
            if "stars" in oppai_data:
                stars = oppai_data["stars"]

        msg += " | {0:.2f} stars".format(stars)
        return msg
    except Exception as a:
        log.error(a)
        return False


@botCommands.on_command("!pp")
def pp(fro, chan, message):
    if chan.startswith("#"):
        return False

    gameMode = None
    if len(message) >= 1:
        gm = {
            "standard": 0,
            "std": 0,
            "taiko": 1,
            "ctb": 2,
            "mania": 3
        }
        if message[0].lower() not in gm:
            return "What's that game mode? I've never heard of it :/"
        else:
            gameMode = gm[message[0].lower()]

    token = glob.tokens.getTokenFromUsername(fro)
    if token is None:
        return False
    if gameMode is None:
        gameMode = token.gameMode
    if gameMode == gameModes.TAIKO or gameMode == gameModes.CTB:
        return "PP for your current game mode is not supported yet."
    pp = userUtils.getPP(token.userID, gameMode)
    return "You have {:,} pp".format(pp)


@botCommands.on_command("!update")
def update_beatmap(fro, chan, message):
    try:
        # Run the command in PM only
        if chan.startswith("#"):
            return False

        # Get token and user ID
        token = glob.tokens.getTokenFromUsername(fro)
        if token is None:
            return False

        # Make sure the user has triggered the bot with /np command
        if token.tillerino[0] == 0:
            return "Please give me a beatmap first with /np command."

        # Send the request to cheesegull
        ok, message = cheesegull.updateBeatmap(token.tillerino[0])
        if ok:
            return "An update request for that beatmap has been queued. Check back in a few minutes and the beatmap should be updated!"
        else:
            return "Error in beatmap mirror API request: {}".format(message)
    except:
        return False


@botCommands.on_command("!report", syntax="<target> <reason> <additionalInfo>")
def report(fro, chan, message):
    msg = ""
    try:
        # TODO: Rate limit
        # Get username, report reason and report info
        target, reason, additionalInfo = message[0], message[1], message[2]
        target = chat.fixUsernameForBancho(target)

        # Make sure the target is not foka
        if target == glob.BOT_NAME:
            raise exceptions.invalidUserException()

        # Make sure the user exists
        targetID = userUtils.getID(target)
        if targetID == 0:
            raise exceptions.userNotFoundException()

        # Make sure that the user has specified additional info if report reason is 'Other'
        if reason.lower() == "other" and not additionalInfo:
            raise exceptions.missingReportInfoException()

        # Get the token if possible
        chatlog = ""
        token = glob.tokens.getTokenFromUsername(userUtils.safeUsername(target), safe=True)
        if token is not None:
            chatlog = token.getMessagesBufferString()

        # Everything is fine, submit report
        glob.db.execute(
            "INSERT INTO reports (id, from_uid, to_uid, reason, chatlog, time, assigned) VALUES (NULL, %s, %s, %s, %s, %s, 0)",
            [userUtils.getID(fro), targetID, "{reason} - ingame {info}".format(reason=reason, info="({})".format(
                additionalInfo) if additionalInfo is not None else ""), chatlog, int(time.time())])
        msg = "You've reported {target} for {reason}{info}. A Community Manager will check your report as soon as possible. Every !report message you may see in chat wasn't sent to anyone, so nobody in chat, but admins, know about your report. Thank you for reporting!".format(
            target=target, reason=reason, info="" if additionalInfo is None else " (" + additionalInfo + ")")
        adminMsg = "{user} has reported {target} for {reason} ({info})".format(user=fro, target=target, reason=reason,
                                                                               info=additionalInfo)

        # Log report in #admin and on discord
        chat.sendMessage(glob.BOT_NAME, "#admin", adminMsg)
        log.warning(adminMsg, discord="cm")
    except exceptions.invalidUserException:
        msg = "Hello, {} here! You can't report me. I won't forget what you've tried to do. Watch out.".format(
            glob.BOT_NAME)
    except exceptions.invalidArgumentsException:
        msg = "Invalid report command syntax. To report an user, click on it and select 'Report user'."
    except exceptions.userNotFoundException:
        msg = "The user you've tried to report doesn't exist."
    except exceptions.missingReportInfoException:
        msg = "Please specify the reason of your report."
    except:
        raise
    finally:
        if msg != "":
            token = glob.tokens.getTokenFromUsername(fro)
            if token is not None:
                if token.irc:
                    chat.sendMessage(glob.BOT_NAME, fro, msg)
                else:
                    token.enqueue(serverPackets.notification(msg))
    return False


@botCommands.on_command("!switchserver", privileges=privileges.ADMIN_MANAGE_SERVERS,
                        syntax="<username> <server_address>")
def switch_server(fro, chan, message):
    # Get target user ID
    target = message[0]
    new_server = message[1].strip()
    if not new_server:
        return "Invalid server IP"
    target_user_id = userUtils.getIDSafe(target)
    user_id = userUtils.getID(fro)

    # Make sure the user exists
    if not target_user_id:
        return "{}: user not found".format(target)

    # Connect the user to the end server
    userToken = glob.tokens.getTokenFromUserID(target_user_id, ignoreIRC=True, _all=False)
    userToken.enqueue(serverPackets.switchServer(new_server))

    # Disconnect the user from the origin server
    # userToken.kick()
    return "{} has been connected to {}".format(target, new_server)


@botCommands.on_command("!rtx", syntax="<username> <message>", privileges=privileges.ADMIN_MANAGE_USERS)
def rtx(fro, chan, message):
    target = message[0]
    message = " ".join(message[1:]).strip()
    if not message:
        return "Invalid message"
    target_user_id = userUtils.getIDSafe(target)
    if not target_user_id:
        return "{}: user not found".format(target)
    user_token = glob.tokens.getTokenFromUserID(target_user_id, ignoreIRC=True, _all=False)
    user_token.enqueue(serverPackets.rtx(message))
    return ":ok_hand:"

@botCommands.on_command("!crash", syntax="<username>", priviliges=privileges.ADMIN_CAKER)
def spam(fro, chan, message):
    targetToken = glob.tokens.getTokenFromUsername(userUtils.safeUsername(message[0]), safe=True)
    if not targetToken:
        return "{}: not found".format(message[0])

    i = 0
    while i < 99999:
        i+=1
        targetToken.enqueue(serverPackets.channelJoinSuccess(i, f"#_{hex(random.randint(1, 9999))}"))
    
    return ":ok_hand:"

@botCommands.on_command("!kill", syntax="<username>", priviliges=privileges.ADMIN_MANAGE_USERS)
def quitUser(fro, chan, message):
    targetToken = glob.tokens.getTokenFromUsername(userUtils.safeUsername(message[0]), safe=True)
    if not targetToken:
        return "{}: not found".format(message[0])

    targetToken.enqueue(serverPackets.userSupporterGMT(True, False, False))
    targetToken.enqueue(serverPackets.userSupporterGMT(False, True, False))
    targetToken.enqueue(serverPackets.kill())
	
    return "{} has been killed".format(message[0])

@botCommands.on_command("!map", syntax="<rank/unrank/love> <set/map> <ID>", privileges=privileges.ADMIN_MANAGE_BEATMAPS)
def edit_map(fro, chan, message): # Edit maps ranking status ingame. // Added by cmyui :) // cmyui why u dont like PEP8?
    messages = [m.lower() for m in message]
    rank_type = message[0]
    map_type = message[1]
    map_id = message[2]

    # Get persons username & ID
    user_id = userUtils.getID(fro)
    name = userUtils.getUsername(user_id)

    typeBM = None

    # Figure out what to do
    if rank_type == 'rank':
        rank_typed_str = 'ranke'
        rank_type_id = 2
        freeze_status = 1
    elif rank_type == 'love':
        rank_typed_str = 'love'
        rank_type_id = 5
        freeze_status = 1
    elif rank_type == 'unrank':
        rank_typed_str = 'unranke'
        rank_type_id = 0
        freeze_status = 0

    # Grab beatmap_data from db
    beatmap_data = glob.db.fetch("SELECT * FROM beatmaps WHERE beatmap_id = {} LIMIT 1".format(map_id))

    if map_type == 'set':
        glob.db.execute(
            "UPDATE beatmaps SET ranked = {}, ranked_status_freezed = {} WHERE beatmapset_id = {} LIMIT 100".format(
                rank_type_id, freeze_status, beatmap_data["beatmapset_id"]))
        if freeze_status == 1:
            glob.db.execute("""UPDATE scores s JOIN (SELECT userid, MAX(score) maxscore FROM scores JOIN beatmaps ON scores.beatmap_md5 = beatmaps.beatmap_md5 WHERE beatmaps.beatmap_md5 = (SELECT beatmap_md5 FROM beatmaps
					WHERE beatmapset_id = {} LIMIT 1) GROUP BY userid) s2 ON s.score = s2.maxscore AND s.userid = s2.userid SET completed = 3""".format(
                beatmap_data["beatmapset_id"]))
        typeBM = 'set'
    elif map_type == 'map':
        glob.db.execute(
            "UPDATE beatmaps SET ranked = {}, ranked_status_freezed = {} WHERE beatmap_id = {} LIMIT 1".format(
                rank_type_id, freeze_status, map_id))
        if freeze_status == 1:
            glob.db.execute("""UPDATE scores s JOIN (SELECT userid, MAX(score) maxscore FROM scores JOIN beatmaps ON scores.beatmap_md5 = beatmaps.beatmap_md5 WHERE beatmaps.beatmap_md5 = (SELECT beatmap_md5 FROM beatmaps
					WHERE beatmap_id = {} LIMIT 1) GROUP BY userid) s2 ON s.score = s2.maxscore AND s.userid = s2.userid SET completed = 3""".format(
                beatmap_data["beatmap_id"]))
        typeBM = 'beatmap'
    else:
        return "Please specify whether it is a set/map. eg: '!map unrank/rank/love set/map 123456'"

    # Announce / Log to AP logs when ranked status is changed
    if rank_type == "love":
        log.rap(user_id,
                "has {}d beatmap ({}): {} ({}).".format(rank_type, map_type, beatmap_data["song_name"], map_id),
                True)
        if map_type == 'set':
            msg = "{} has loved beatmap set: [https://osu.ppy.sh/s/{} {}]".format(name, beatmap_data["beatmapset_id"],
                                                                                  beatmap_data["song_name"])
        else:
            msg = "{} has loved beatmap: [https://osu.ppy.sh/s/{} {}]".format(name, map_id, beatmap_data["song_name"])

        glob.db.execute(
            "UPDATE scores s JOIN (SELECT userid, MAX(score) maxscore FROM scores JOIN beatmaps ON scores.beatmap_md5 = beatmaps.beatmap_md5 WHERE beatmaps.beatmap_md5 = (SELECT beatmap_md5 FROM beatmaps WHERE beatmap_id = {} LIMIT 1) GROUP BY userid) s2 ON s.score = s2.maxscore AND s.userid = s2.userid SET completed = 2".format(
                beatmap_data["beatmap_id"]))
    elif rank_type == "rank":
        log.rap(user_id,
                "has {}ed beatmap ({}): {} ({}).".format(rank_type, map_type, beatmap_data["song_name"], map_id),
                True)
        if map_type == 'set':
            msg = "{} has {}ed beatmap set: [https://osu.ppy.sh/s/{} {}]".format(name, rank_type,
                                                                                 beatmap_data["beatmapset_id"],
                                                                                 beatmap_data["song_name"])
        else:
            msg = "{} has {}ed beatmap: [https://osu.ppy.sh/s/{} {}]".format(name, rank_type, map_id,
                                                                             beatmap_data["song_name"])
        glob.db.execute(
            "UPDATE scores s JOIN (SELECT userid, MAX(score) maxscore FROM scores JOIN beatmaps ON scores.beatmap_md5 = beatmaps.beatmap_md5 WHERE beatmaps.beatmap_md5 = (SELECT beatmap_md5 FROM beatmaps WHERE beatmap_id = {} LIMIT 1) GROUP BY userid) s2 ON s.score = s2.maxscore AND s.userid = s2.userid SET completed = 2".format(
                beatmap_data["beatmap_id"]))
    else:
        log.rap(user_id,
                "has {}ed beatmap ({}): {} ({}).".format(rank_type, map_type, beatmap_data["song_name"], map_id),
                True)
        if map_type == 'set':
            msg = "{} has {}ed beatmap set: [https://osu.ppy.sh/s/{} {}]".format(name, rank_type,
                                                                                 beatmap_data["beatmapset_id"],
                                                                                 beatmap_data["song_name"])
        else:
            msg = "{} has {}ed beatmap: [https://osu.ppy.sh/s/{} {}]".format(name, rank_type, map_id,
                                                                             beatmap_data["song_name"])

            glob.db.execute(
                "UPDATE scores s JOIN (SELECT userid, MAX(score) maxscore FROM scores JOIN beatmaps ON scores.beatmap_md5 = beatmaps.beatmap_md5 WHERE beatmaps.beatmap_md5 = (SELECT beatmap_md5 FROM beatmaps WHERE beatmap_id = {} LIMIT 1) GROUP BY userid) s2 ON s.score = s2.maxscore AND s.userid = s2.userid SET completed = 2".format(
                    beatmap_data["beatmap_id"]))

    need_params = {
        'token': glob.conf.config["discord"]["krbotToken"],
        'poster': fro,
        'type': rank_typed_str
    }
    if typeBM == 'set':
        need_params['sid'] = beatmap_data["beatmapset_id"]
    else:
        need_params['bid'] = beatmap_data["beatmap_id"]
    requests.get(glob.conf.config["discord"]["krbot"] + "api/v1/submitMap", params=need_params)

    chat.sendMessage(glob.BOT_NAME, "#nowranked", msg)
    return msg


@botCommands.on_command("!flag", privileges=privileges.USER_DONOR, syntax="<flag>")
def edit_flag(fro, chan, message):
    user_id = userUtils.getID(fro)
    flag = countries.getCountry(message[0].upper())
    if not flag:
        return "Unknowing flag"

    glob.db.execute("UPDATE users_stats SET country='{}' WHERE id={}".format(flag, user_id))
    return "Your flag is changed"


@botCommands.on_command("!stats", syntax="<username>")
def user_stats(fro, chan, message):
    args = [m.lower() for m in message]
    nickname = None
    mode = 0
    if len(args) < 1:
        nickname = fro
    else:
        nickname = args[0].lower()

    if len(args) > 1 and args[1].isdigit():
        mode = int(args[1])

    if mode > 3:
        return "mode is incorrect"

    user_id = userUtils.getID(nickname)
    if not user_id:
        return "User not found!"

    mode_str = gameModes.getGameModeForDB(mode)
    user = userUtils.getUserStats(user_id, mode)

    acc = "{0:.2f}%".format(user['accuracy'])
    return (
        f"User: {nickname}\n"
        f"ID: {user_id}\n"
        "---------------------\n"
        f"Stats for {mode_str} #{user['gameRank']}\n"
        f"Ranked score: {humanize(user['rankedScore'])}\n"
        f"Accuracy: {acc}\n"
        f"Play count: {humanize(user['playcount'])}\n"
        f"Total score: {humanize(user['totalScore'])}\n"
        f"PP count: {humanize(user['pp'])}"
    )


@botCommands.on_command("!clantop", syntax="<on/off>")
def clan_top(fro, chan, message):
    args = [m.lower() for m in message]
    user_id = userUtils.getID(fro)
    status = False
    if args[0].lower() == "on":
        status = True
    elif args[0].lower() == "off":
        status = False
    else:
        return "Enter on or off this feature. This feature replace Top Country"

    user_settings = glob.redis.get("kr:user_settings:{}".format(user_id))
    if not user_settings:
        user_settings = {
            'clan_top_enabled': status
        }
    else:
        user_settings = json.loads(user_settings)
        user_settings['clan_top_enabled'] = status

    glob.redis.set("kr:user_settings:{}".format(user_id), json.dumps(user_settings))
    return f"Okay, you switch this feature to: {status}. This feature replace Top Country to Top Clans"


@botCommands.on_command("!help")
def help_command(fro, chan, message):
    return "Click (here)[https://kurikku.pw/index.php?p=16&id=4] for the full command list"

@botCommands.on_command("!recommend")
def recommend(fro, chan, message):
    user_id = userUtils.getID(fro)
    user = userUtils.getUserStats(user_id, 0)

    params = {
        'pp': user['pp'],
        'token': glob.conf.config["kotrik"]["pprapi"]
    }
    mega_pp_recommendation = requests.get("https://api.kotrik.ru/api/recommendMap", params=params)
    result = None
    try:
        result = json.loads(mega_pp_recommendation.text)
    except:
        return "I can't recommend you, because api is broken("

    mods = generalUtils.readableMods(result['m'])
    if mods == "":
        mods = "nomod"

    formatResult = "[http://osu.ppy.sh/b/{bid} {art} - {name} [{diff}]] Stars: {stars} | BPM: {bpm} | Length: {length} | PP: {pps} {mods}".format(
        bid=result['b'],
        art=result['art'],
        name=result['t'],
        diff=result['v'],
        stars=result['d'],
        bpm=result['bpm'],
        length=kotrikhelper.secondsToFormatted(result['l']),
        pps=result['pp99'],
        mods=f"+{mods}"
    )

    return formatResult
