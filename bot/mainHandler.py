import traceback
import sys
from common.log import logUtils as log

class Stoaring:

    def __init__(self):
        self.handlers = {}

    def add_handler(self, cmd, array):
        self.handlers[cmd] = array
        return True

    def call_safed(self, funcd, *args, **kwargs):
        try:
            result = funcd(*args, **kwargs)
            return result
        except Exception as e:
            log.error("FokaBot error. Log:")
            traceback.print_exc()
            return False

    def call_command(self, cmd, fro, chan, message):
        func = self.handlers.get(cmd, None)
        return self.call_safed(func['callback'], fro, chan, message)


class BotCommands:

    def __init__(self, store):
        self.store = store
        if not self.store:
            log.error("Store is not presented!")

    def on_command(self, command, **kwargs):
        def wrapper(func):
            if type(command) in (tuple, list):
                for cmd in command:
                    to_store = {}
                    to_store['syntax'] = kwargs.get("syntax", "")
                    to_store['privileges'] = kwargs.get("privileges", None)
                    to_store['callback'] = func

                    self.store.add_handler(cmd, to_store)
            else:
                to_store = {}
                to_store['syntax'] = kwargs.get("syntax", "")
                to_store['privileges'] = kwargs.get("privileges", None)
                to_store['callback'] = func

                self.store.add_handler(command, to_store)
            return func

        return wrapper

store = Stoaring()
botCommands = BotCommands(store)

# Import workers
sys.path.insert(0, "bot")
__import__("multiplayerWorker")
__import__("botWorker")
