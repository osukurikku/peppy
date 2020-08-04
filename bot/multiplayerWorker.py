from bot.mainHandler import botCommands
import threading

from common import generalUtils
from common.constants import mods
from common.constants import privileges
from common.ripple import userUtils
from constants import exceptions, slotStatuses, matchModModes, matchTeams, matchTeamTypes, matchScoringTypes
from constants import serverPackets
from helpers import chatHelper as chat
from objects import glob

@botCommands.on_command("!mp", syntax="<subcommand>")
def multiplayer(fro, chan, message):
    def get_match_id_from_channel(chan):
        if not chan.lower().startswith("#multi_"):
            raise exceptions.wrongChannelException()
        parts = chan.lower().split("_")
        if len(parts) < 2 or not parts[1].isdigit():
            raise exceptions.wrongChannelException()
        matchID = int(parts[1])
        if matchID not in glob.matches.matches:
            raise exceptions.matchNotFoundException()
        return matchID
    
    def can_user_touch_lobby(lobbyID: int, uID: int, checkUserIn: bool = False, canRefEdit: bool = True):
        if lobbyID:
            match = glob.matches.matches[lobbyID]
            if checkUserIn:
                # check user is tourneyHost
                if match.isTourney and match.tourneyHost == uID:
                    return True

            # check user is hostUserID
            if match.hostUserID == uID:
                return True # user can edit this

            if canRefEdit:
                # check user is ref
                if uID in match.refs:
                    return True

        # check user is tournament staff or its bot ;d
        if (userUtils.getPrivileges(userUtils.getID(fro)) & privileges.USER_TOURNAMENT_STAFF) > 0 or \
           fro == glob.BOT_NAME:
           return True

        return False

    def mp_make():
        if len(message) < 2:
            raise exceptions.invalidArgumentsException("Wrong syntax: !mp make <name>")
        matchName = " ".join(message[1:]).strip()
        if not matchName:
            raise exceptions.invalidArgumentsException("Match name must not be empty!")
        userID = userUtils.getID(fro)

        for (_, __match) in glob.matches.matches.items():
            if __match.hostUserID == userID:
                return "You have opened match {}, please close it before use this command!".format(__match.matchID)

        matchID = glob.matches.createMatch(matchName, generalUtils.stringMd5(generalUtils.randomString(32)), 0,
                                           "Tournament", "", 0, userID, isTourney=True)
        glob.matches.matches[matchID].sendUpdates()
        return "Tourney match #{} created!".format(matchID)

    def mp_join():
        if len(message) < 2 or not message[1].isdigit():
            raise exceptions.invalidArgumentsException("Wrong syntax: !mp join <id>")
        matchID = int(message[1])
        if not matchID in glob.matches.matches:
            return False

        userID = userUtils.getID(fro)
        if can_user_touch_lobby(matchID, userID, True):
            userToken = glob.tokens.getTokenFromUsername(fro, ignoreIRC=True)
            if userToken and not userToken.tournament:
                userToken.joinMatch(matchID)
            else:
                chat.joinChannel(token=userToken, channel="#multi_{}".format(matchID))
                return "Attempting to join match #{} with tournament client!".format(matchID)

            return "Attempting to join match #{}!".format(matchID)

        return False

    def mp_close():
        matchID = get_match_id_from_channel(chan)
        userID = userUtils.getID(fro)
        if not can_user_touch_lobby(matchID, userID):
            return False
        glob.matches.disposeMatch(matchID)
        return "Multiplayer match #{} disposed successfully".format(matchID)

    def mp_lock():
        matchID = get_match_id_from_channel(chan)
        userID = userUtils.getID(fro)
        if not can_user_touch_lobby(matchID, userID):
            return False
        glob.matches.matches[matchID].isLocked = True
        return "This match has been locked"

    def mp_unlock():
        matchID = get_match_id_from_channel(chan)
        userID = userUtils.getID(fro)
        if not can_user_touch_lobby(matchID, userID):
            return False
        glob.matches.matches[matchID].isLocked = False
        return "This match has been unlocked"

    def mp_size():
        userID = userUtils.getID(fro)
        if not can_user_touch_lobby(get_match_id_from_channel(chan), userID):
            return False
        if len(message) < 2 or not message[1].isdigit() or int(message[1]) < 2 or int(message[1]) > 16:
            raise exceptions.invalidArgumentsException("Wrong syntax: !mp size <slots(2-16)>")
        matchSize = int(message[1])
        _match = glob.matches.matches[get_match_id_from_channel(chan)]
        _match.forceSize(matchSize)
        return "Match size changed to {}".format(matchSize)

    def mp_move():
        userID = userUtils.getID(fro)
        if not can_user_touch_lobby(get_match_id_from_channel(chan), userID):
            return False
        if len(message) < 3 or not message[2].isdigit() or int(message[2]) < 0 or int(message[2]) > 16:
            raise exceptions.invalidArgumentsException("Wrong syntax: !mp move <username> <slot>")
        username = message[1]
        newSlotID = int(message[2])
        userID = userUtils.getIDSafe(username)
        if userID is None:
            raise exceptions.userNotFoundException("No such user")
        _match = glob.matches.matches[get_match_id_from_channel(chan)]
        success = _match.userChangeSlot(userID, newSlotID)
        if success:
            result = "Player {} moved to slot {}".format(username, newSlotID)
        else:
            result = "You can't use that slot: it's either already occupied by someone else or locked"
        return result

    def mp_host():
        userID = userUtils.getID(fro)
        if not can_user_touch_lobby(get_match_id_from_channel(chan), userID):
            return False
        if len(message) < 2:
            raise exceptions.invalidArgumentsException("Wrong syntax: !mp host <username>")
        username = message[1].strip()
        if not username:
            raise exceptions.invalidArgumentsException("Please provide a username")
        userID = userUtils.getIDSafe(username)
        if userID is None:
            raise exceptions.userNotFoundException("No such user")
        _match = glob.matches.matches[get_match_id_from_channel(chan)]
        success = _match.setHost(userID)
        return "{} is now the host".format(username) if success else "Couldn't give host to {}".format(username)

    def mp_clear_host():
        matchID = get_match_id_from_channel(chan)
        userID = userUtils.getID(fro)
        if not can_user_touch_lobby(matchID, userID):
            return False
        glob.matches.matches[matchID].removeHost()
        return "Host has been removed from this match"

    def mp_start():
        matchID = get_match_id_from_channel(chan)
        userID = userUtils.getID(fro)
        if not can_user_touch_lobby(matchID, userID):
            return False

        def _start():
            matchID = get_match_id_from_channel(chan)
            success = glob.matches.matches[matchID].start()
            if not success:
                chat.sendMessage(glob.BOT_NAME, chan, "Couldn't start match. Make sure there are enough players and "
                                                      "teams are valid. The match has been unlocked.")
            else:
                chat.sendMessage(glob.BOT_NAME, chan, "Have fun!")

        def _decreaseTimer(t):
            if t <= 0:
                _start()
            else:
                if t % 10 == 0 or t <= 5:
                    chat.sendMessage(glob.BOT_NAME, chan, "Match starts in {} seconds.".format(t))
                threading.Timer(1.00, _decreaseTimer, [t - 1]).start()

        if len(message) < 2 or not message[1].isdigit():
            startTime = 0
        else:
            startTime = int(message[1])

        force = False if len(message) < 2 else message[1].lower() == "force"
        _match = glob.matches.matches[get_match_id_from_channel(chan)]

        # Force everyone to ready
        someoneNotReady = False
        for i, slot in enumerate(_match.slots):
            if slot.status != slotStatuses.READY and slot.user is not None:
                someoneNotReady = True
                if force:
                    _match.toggleSlotReady(i)

        if someoneNotReady and not force:
            return "Some users aren't ready yet. Use '!mp start force' if you want to start the match, " \
                   "even with non-ready players."

        if startTime == 0:
            _start()
            return "Starting match"
        else:
            _match.isStarting = True
            threading.Timer(1.00, _decreaseTimer, [startTime - 1]).start()
            return "Match starts in {} seconds. The match has been locked. " \
                   "Please don't leave the match during the countdown " \
                   "or you might receive a penalty.".format(startTime)

    def mp_timer():
        matchID = get_match_id_from_channel(chan)
        userID = userUtils.getID(fro)
        if not can_user_touch_lobby(matchID, userID):
            return False

        if len(message) < 2 or not message[1].isdigit() or int(message[1]) < 1:
            return "Wrong argument"
        secondsWatch = int(message[1])

        match = glob.matches.matches[matchID]
        if match.timerRunned:
            chat.sendMessage(glob.BOT_NAME, chan, "You can't run another timer, if you had another runned timer.\nEnter !mp aborttimer to stop.")
            return False

        def _decreaseTimer(t):
            if match.timerForce:
                chat.sendMessage(glob.BOT_NAME, chan, "Time is up!")
                match.timerForce = False
                match.timerRunned = False
            elif t <= 0:
                chat.sendMessage(glob.BOT_NAME, chan, "Time is up!")
                match.timerRunned = False
            else:
                if t % 10 == 0 or t <= 5:
                    chat.sendMessage(glob.BOT_NAME, chan, "Timer ends in {} seconds.".format(t))
                threading.Timer(1.00, _decreaseTimer, [t - 1]).start()
    
        match.timerRunned = True
        threading.Timer(1.00, _decreaseTimer, [secondsWatch - 1]).start()
        return "Timer started!"

    def mp_abort_timer():
        matchID = get_match_id_from_channel(chan)
        userID = userUtils.getID(fro)
        if not can_user_touch_lobby(matchID, userID):
            return False

        match = glob.matches.matches[matchID]
        if not match.timerRunned:
            return "Timer is not runned!"
        
        if match.timerForce:
            return "Another dude stopped timer!"
        
        match.timerForce = True
        return False

    def mp_invite():
        userID = userUtils.getID(fro)
        if not can_user_touch_lobby(get_match_id_from_channel(chan), userID, True):
            return False
        if len(message) < 2:
            raise exceptions.invalidArgumentsException("Wrong syntax: !mp invite <username>")
        username = message[1].strip()
        if not username:
            raise exceptions.invalidArgumentsException("Please provide a username")
        userID = userUtils.getIDSafe(username)
        if userID is None:
            raise exceptions.userNotFoundException("No such user")
        token = glob.tokens.getTokenFromUserID(userID, ignoreIRC=True)
        if token is None:
            raise exceptions.invalidUserException("That user is not connected to bancho right now.")
        _match = glob.matches.matches[get_match_id_from_channel(chan)]
        _match.invite(999, userID)
        token.enqueue(serverPackets.notification("Please accept the invite you've just received from {} to "
                                                 "enter your tourney match.".format(glob.BOT_NAME)))
        return "An invite to this match has been sent to {}".format(username)

    def mp_map():
        userID = userUtils.getID(fro)
        if not can_user_touch_lobby(get_match_id_from_channel(chan), userID, True):
            return False
        if len(message) < 2 or not message[1].isdigit() or (len(message) == 3 and not message[2].isdigit()):
            raise exceptions.invalidArgumentsException("Wrong syntax: !mp map <beatmapid> [<gamemode>]")
        beatmapID = int(message[1])
        gameMode = int(message[2]) if len(message) == 3 else 0
        if gameMode < 0 or gameMode > 3:
            raise exceptions.invalidArgumentsException("Gamemode must be 0, 1, 2 or 3")
        beatmapData = glob.db.fetch("SELECT * FROM beatmaps WHERE beatmap_id = %s LIMIT 1", [beatmapID])
        if beatmapData is None:
            raise exceptions.invalidArgumentsException("The beatmap you've selected couldn't be found in the database."
                                                       "If the beatmap id is valid, please load the scoreboard first in "
                                                       "order to cache it, then try again.")
        _match = glob.matches.matches[get_match_id_from_channel(chan)]
        _match.beatmapID = beatmapID
        _match.beatmapName = beatmapData["song_name"]
        _match.beatmapMD5 = beatmapData["beatmap_md5"]
        _match.gameMode = gameMode
        _match.resetReady()
        _match.sendUpdates()
        return "Match map has been updated"

    def mp_set():
        userID = userUtils.getID(fro)
        if not can_user_touch_lobby(get_match_id_from_channel(chan), userID):
            return False
        if len(message) < 2 or not message[1].isdigit() or \
                (len(message) >= 3 and not message[2].isdigit()) or \
                (len(message) >= 4 and not message[3].isdigit()):
            raise exceptions.invalidArgumentsException("Wrong syntax: !mp set <teammode> [<scoremode>] [<size>]")
        _match = glob.matches.matches[get_match_id_from_channel(chan)]
        matchTeamType = int(message[1])
        matchScoringType = int(message[2]) if len(message) >= 3 else _match.matchScoringType
        if not 0 <= matchTeamType <= 3:
            raise exceptions.invalidArgumentsException("Match team type must be between 0 and 3")
        if not 0 <= matchScoringType <= 3:
            raise exceptions.invalidArgumentsException("Match scoring type must be between 0 and 3")
        oldMatchTeamType = _match.matchTeamType
        _match.matchTeamType = matchTeamType
        _match.matchScoringType = matchScoringType
        if len(message) >= 4:
            _match.forceSize(int(message[3]))
        if _match.matchTeamType != oldMatchTeamType:
            _match.initializeTeams()
        if _match.matchTeamType == matchTeamTypes.TAG_COOP or _match.matchTeamType == matchTeamTypes.TAG_TEAM_VS:
            _match.matchModMode = matchModModes.NORMAL

        _match.sendUpdates()
        return "Match settings have been updated!"

    def mp_abort():
        userID = userUtils.getID(fro)
        if not can_user_touch_lobby(get_match_id_from_channel(chan), userID):
            return False
        _match = glob.matches.matches[get_match_id_from_channel(chan)]
        _match.abort()
        return "Match aborted!"

    def mp_kick():
        userID = userUtils.getID(fro)
        if not can_user_touch_lobby(get_match_id_from_channel(chan), userID, False, False):
            return False
        if len(message) < 2:
            raise exceptions.invalidArgumentsException("Wrong syntax: !mp kick <username>")
        username = message[1].strip()
        if not username:
            raise exceptions.invalidArgumentsException("Please provide a username")
        userID = userUtils.getIDSafe(username)
        if userID is None:
            raise exceptions.userNotFoundException("No such user")
        _match = glob.matches.matches[get_match_id_from_channel(chan)]
        slotID = _match.getUserSlotID(userID)
        if slotID is None:
            raise exceptions.userNotFoundException("The specified user is not in this match")
        for i in range(0, 2):
            _match.toggleSlotLocked(slotID)
        return "{} has been kicked from the match.".format(username)

    def mp_password():
        userID = userUtils.getID(fro)
        if not can_user_touch_lobby(get_match_id_from_channel(chan), userID):
            return False
        password = "" if len(message) < 2 or not message[1].strip() else message[1]
        _match = glob.matches.matches[get_match_id_from_channel(chan)]
        _match.changePassword(password)
        return "Match password has been changed!"

    def mp_random_password():
        userID = userUtils.getID(fro)
        if not can_user_touch_lobby(get_match_id_from_channel(chan), userID):
            return False
        password = generalUtils.stringMd5(generalUtils.randomString(32))
        _match = glob.matches.matches[get_match_id_from_channel(chan)]
        _match.changePassword(password)
        return "Match password has been changed to a random one"

    def mp_mods():
        userID = userUtils.getID(fro)
        if not can_user_touch_lobby(get_match_id_from_channel(chan), userID, True):
            return False
        if len(message) < 2:
            raise exceptions.invalidArgumentsException("Wrong syntax: !mp <mod1> [<mod2>] ...")
        _match = glob.matches.matches[get_match_id_from_channel(chan)]
        newMods = 0
        freeMod = False
        for _mod in message[1:]:
            if _mod.lower().strip() == "hd":
                newMods |= mods.HIDDEN
            elif _mod.lower().strip() == "hr":
                newMods |= mods.HARDROCK
            elif _mod.lower().strip() == "dt":
                newMods |= mods.DOUBLETIME
            elif _mod.lower().strip() == "fl":
                newMods |= mods.FLASHLIGHT
            elif _mod.lower().strip() == "fi":
                newMods |= mods.FADEIN
            if _mod.lower().strip() == "none":
                newMods = 0

            if _mod.lower().strip() == "freemod":
                freeMod = True

        _match.matchModMode = matchModModes.FREE_MOD if freeMod else matchModModes.NORMAL
        _match.resetReady()
        if _match.matchModMode == matchModModes.FREE_MOD:
            _match.resetMods()
        _match.changeMods(newMods)
        return "Match mods have been updated!"

    def mp_team():
        userID = userUtils.getID(fro)
        if not can_user_touch_lobby(get_match_id_from_channel(chan), userID):
            return False
        if len(message) < 3:
            raise exceptions.invalidArgumentsException("Wrong syntax: !mp team <username> <colour>")
        username = message[1].strip()
        if not username:
            raise exceptions.invalidArgumentsException("Please provide a username")
        colour = message[2].lower().strip()
        if colour not in ["red", "blue"]:
            raise exceptions.invalidArgumentsException("Team colour must be red or blue")
        userID = userUtils.getIDSafe(username)
        if userID is None:
            raise exceptions.userNotFoundException("No such user")
        _match = glob.matches.matches[get_match_id_from_channel(chan)]
        _match.changeTeam(userID, matchTeams.BLUE if colour == "blue" else matchTeams.RED)
        return "{} is now in {} team".format(username, colour)

    def mp_settings():
        userID = userUtils.getID(fro)
        if not can_user_touch_lobby(get_match_id_from_channel(chan), userID):
            return False
        _match = glob.matches.matches[get_match_id_from_channel(chan)]
        msg = "PLAYERS IN THIS MATCH:\n"
        empty = True
        for slot in _match.slots:
            if slot.user is None:
                continue
            readable_statuses = {
                slotStatuses.READY: "ready",
                slotStatuses.NOT_READY: "not ready",
                slotStatuses.NO_MAP: "no map",
                slotStatuses.PLAYING: "playing",
            }
            if slot.status not in readable_statuses:
                readable_status = "???"
            else:
                readable_status = readable_statuses[slot.status]
            empty = False
            msg += "* [{team}] <{status}> ~ {username}{mods}\n".format(
                team="red" if slot.team == matchTeams.RED else "blue" if slot.team == matchTeams.BLUE else "!! no team !!",
                status=readable_status,
                username=glob.tokens.tokens[slot.user].username,
                mods=" (+ {})".format(generalUtils.readableMods(slot.mods)) if slot.mods > 0 else ""
            )
        if empty:
            msg += "Nobody.\n"
        return msg

    def mpScoreV():
        userID = userUtils.getID(fro)
        if not can_user_touch_lobby(get_match_id_from_channel(chan), userID):
            return False
        if len(message) < 2 or message[1] not in ("1", "2"):
            raise exceptions.invalidArgumentsException("Wrong syntax: !mp scorev <1|2>")
        
        _match = glob.matches.matches[get_match_id_from_channel(chan)]
        _match.matchScoringType = matchScoringTypes.SCORE_V2 if message[1] == "2" else matchScoringTypes.SCORE
        _match.sendUpdates()
        return "Match scoring type set to scorev{}".format(message[1])
    
    def mp_addRef():
        userID = userUtils.getID(fro)
        if not can_user_touch_lobby(get_match_id_from_channel(chan), userID, False, False):
            return False
        
        if len(message) < 2:
            raise exceptions.invalidArgumentsException("Wrong syntax: !mp addref <ref username>")
        
        # check is correct nickname
        userID = userUtils.getID(fro)
        userRefID = userUtils.getIDSafe(message[1])
        if not userRefID:
            raise exceptions.invalidArgumentsException("User not found")
        
        if userID == userRefID:
            return False

        tokens = glob.tokens.getTokenFromUsername(userUtils.safeUsername(message[1]), safe=True, _all=True)
        if len(tokens) == 0:
            return "{} is not online".format(message[1])

        _match = glob.matches.matches[get_match_id_from_channel(chan)]
        if userRefID in _match.refs:
            return "This referre added already :) He can join with command !mp join {}".format(_match.matchID)
        
        _match.refs.append(userRefID)
        _match.sendUpdates()
        return "Added {} to match referre. He can join with command !mp join {}".format(userRefID, _match.matchID)

    def mp_removeRef():
        userID = userUtils.getID(fro)
        if not can_user_touch_lobby(get_match_id_from_channel(chan), userID, False, False):
            return False
        
        if len(message) < 2:
            raise exceptions.invalidArgumentsException("Wrong syntax: !mp removeref <ref username>")
        
        userRefID = userUtils.getIDSafe(message[1])
        if not userRefID:
            raise exceptions.invalidArgumentsException("User not found")
        
        _match = glob.matches.matches[get_match_id_from_channel(chan)]
        if not userRefID in _match.refs:
            return "This user is not referre."

        _match.refs.remove(userRefID)
        _match.sendUpdates()
        chat.partChannel(userRefID, "#multi_{}".format(_match.matchID), kick=True)
        chat.partChannel(userRefID, "#multiplayer", kick=True)
        return "Match referre was deleted!"

    try:
        subcommands = {
            "make": mp_make,
            "close": mp_close,
            "join": mp_join,
            "lock": mp_lock,
            "unlock": mp_unlock,
            "size": mp_size,
            "move": mp_move,
            "host": mp_host,
            "clearhost": mp_clear_host,
            "start": mp_start,
            "invite": mp_invite,
            "map": mp_map,
            "set": mp_set,
            "abort": mp_abort,
            "kick": mp_kick,
            "password": mp_password,
            "randompassword": mp_random_password,
            "mods": mp_mods,
            "team": mp_team,
            "scorev": mpScoreV,
            "settings": mp_settings,
            "addref": mp_addRef,
            "removeref": mp_removeRef,
            "timer": mp_timer,
            "aborttimer": mp_abort_timer
        }
        requestedSubcommand = message[0].lower().strip()
        if requestedSubcommand not in subcommands:
            raise exceptions.invalidArgumentsException("Invalid subcommand")
        return subcommands[requestedSubcommand]()
    except (
            exceptions.invalidArgumentsException, exceptions.userNotFoundException,
            exceptions.invalidUserException) as e:
        return str(e)
    except exceptions.wrongChannelException:
        return "This command only works in multiplayer chat channels"
    except exceptions.matchNotFoundException:
        return "Match not found"
    except:
        raise