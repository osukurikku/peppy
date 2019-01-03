import json

import tornado.gen

from common.sentry import sentry
from common.web import requestsManager
from objects import glob
from constants import exceptions

class handler(requestsManager.asyncRequestHandler):
    @tornado.web.asynchronous
    @tornado.gen.engine
    @sentry.captureTornado
    def asyncGet(self):
        statusCode = 400
        data = {"message": "unknown error"}
        try:
            # Check arguments
            if "mp" not in self.request.arguments:
                raise exceptions.invalidArgumentsException()

            match_id = self.request.arguments['mp'][0].decode()
            print(match_id)
            if not match_id.isdigit():
                data['message'] = "unknown match id"
                statusCode = 400
                return

            # Get MP INFO WOOOOW RIPPLE DON'T MAKES THIS
            print(glob.matches.matches)

            match = glob.matches.matches.get(int(match_id), None)
            print(match)
            if not match:
                data['message'] = "unknown match or match is ended"
                statusCode = 400
                return

            output = {
                "match": {
                    'match_id': match_id,
                    'name': match.matchName,
                    'creation_time': match.createTime,
                    'end_time': None,
                    'mods': match.mods,
                    'inProgress': match.inProgress
                },
                "games": match.games
            }

            # Status code and message
            statusCode = 200
            data['response'] = output
            data["message"] = "ok"
        except exceptions.invalidArgumentsException:
            statusCode = 400
            data["message"] = "missing required arguments"
        finally:
            # Add status code to data
            data["status"] = statusCode

            # Send response
            self.write(json.dumps(data))
            self.set_status(statusCode)
