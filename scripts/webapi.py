"""
Publishes a webapi for cuwo
"""

from twisted.internet import reactor
from twisted.web.resource import Resource
from twisted.web.server import Site
from cuwo.script import ServerScript

import json
import time

WEBAPI_VERSION = '0.0.3'

ERROR_UNAUTHORIZED = -1
ERROR_INVALID_RESOURCE = -2
ERROR_INVALID_PLAYER = -3
ERROR_INVALID_TIME = -4
ERROR_INVALID_METHOD = -5


def encode_item_upgrade(upgrade):
    encoded = {
        'x': upgrade.x,
        'y': upgrade.y,
        'z': upgrade.z,
        'material': upgrade.material,
        'level': upgrade.level
    }
    return encoded


def encode_item(item):
    encoded = {
        'type': item.type,
        'sub-type': item.sub_type,
        'modifier': item.modifier,
        'minus-modifier': item.minus_modifier,
        'rarity': item.rarity,
        'material': item.material,
        'flags': item.material,
        'level': item.level,
        'power-level': get_power_level(item.level),
        'upgrades': [encode_item_upgrade(item.items[i])
                     for i in xrange(item.upgrade_count)]
    }
    return encoded


def encode_player(player, includeSkills=False, includeEquipment=False):
    encoded = {
        'name': player.name,
        'position': {'x': player.x, 'y': player.y, 'z': player.z},
        'class': player.class_type,
        'specialization': player.specialization,
        'level': player.level,
        'power-level': get_power_level(player.level)
    }
    if includeSkills:
        skills = {
            'pet-master': player.skills[0],
            'riding': player.skills[1],
            'climbing': player.skills[2],
            'hang-gliding': player.skills[3],
            'swimming': player.skills[4],
            'sailing': player.skills[5],
            'class-skill-1': player.skills[6],
            'class-skill-2': player.skills[7],
            'class-skill-3': player.skills[8]
        }
        encoded['skills'] = skills
    if includeEquipment:
        encoded['equipment'] = [encode_item(item) for item in player.equipment]
    return encoded


def get_player(server, name):
    name = name.lower()
    for player in server.connections.values():
        if player.has_joined:
            player_name = player.entity_data.name.lower()
            if player_name == name:
                return player
    return None


# Thanks to Sarcen for the formula
def get_power_level(level):
    power = 101 - 100 / (0.05 * (level - 1) + 1)
    return int(power)


class ErrorResource(Resource):
    isLeaf = True

    def __init__(self, message):
        self.message = message

    def render(self, request):
        return json.dumps({'error': self.message})


class SuccessResource(Resource):
    isLeaf = True

    def render(self, request):
        return json.dumps({'success': 1})


class APIResource(Resource):
    def __init__(self, server):
        Resource.__init__(self)
        self.server = server


class WebAPI(Resource):
    def __init__(self, server, keys):
        Resource.__init__(self)
        self.server = server
        self.keys = keys
        self.putChild('player', PlayerResource(self.server))
        self.putChild('kick', KickResource(self.server))
        self.putChild('time', TimeResource(self.server))
        self.putChild('message', MessageResource(self.server))

    def getChildWithDefault(self, name, request):
        if name is '':
            return self
        if 'key' not in request.args:
            return ErrorResource(ERROR_UNAUTHORIZED)
        if request.args['key'][0] not in self.keys:
            return ErrorResource(ERROR_UNAUTHORIZED)
        return Resource.getChildWithDefault(self, name, request)

    def getChild(self, path, request):
        return ErrorResource(ERROR_INVALID_RESOURCE)

    def render(self, request):
        return json.dumps({'version': WEBAPI_VERSION})


class PlayerResource(APIResource):
    def getChild(self, path, request):
        if path is '':
            return self
        player = get_player(self.server, path)
        if player is None:
            return ErrorResource(ERROR_INVALID_PLAYER)
        return PlayerDetailResource(player.entity_data)

    def render(self, request):
        players = [connection.name
                   for connection in self.server.connections.values()
                   if connection.has_joined]
        return json.dumps({'players': players})


class PlayerDetailResource(Resource):
    isLeaf = True

    def __init__(self, player):
        self.player = player

    def render(self, request):
        includeSkills = False
        includeEquipment = False
        if 'include' in request.args:
            inclusion = [item.lower()
                         for item in request.args['include'][0].split(',')
                         if item is not '']
            if 'skills' in inclusion:
                includeSkills = True
            if 'equipment' in inclusion:
                includeEquipment = True
        return json.dumps({'player': encode_player(self.player, includeSkills,
                                                   includeEquipment)})


class KickResource(APIResource):
    def getChild(self, path, request):
        player = get_player(self.server, path)
        if player is None:
            return ErrorResource(ERROR_INVALID_PLAYER)
        player.kick()
        return SuccessResource()


class TimeResource(APIResource):
    def getChild(self, path, request):
        if path == '':
            return self
        try:
            time.strptime(path, '%H:%M')
            self.server.set_clock(path)
            return SuccessResource()
        except ValueError:
            pass
        return ErrorResource(ERROR_INVALID_TIME)

    def render(self, request):
        return json.dumps({'time': self.server.get_clock()})


class MessageResource(APIResource):
    def getChild(self, path, request):
        if request.content.seek(0, 2) != 0:
            message = request.content.getvalue()
            if path == '':
                self.server.send_chat(message)
                return SuccessResource()
            else:
                player = get_player(self.server, path)
                if player is None:
                    return ErrorResource(ERROR_INVALID_PLAYER)
                player.send_chat(message)
                return SuccessResource()
        return ErrorResource(ERROR_INVALID_METHOD)


class WebAPISite(Site):
    def __init__(self, server, keys):
        Site.__init__(self, WebAPI(server, keys))

    def startFactory(self):
        pass


class WebAPIScriptFactory(ServerScript):
    def on_load(self):
        config = self.server.config.webapi
        keys = config.get('keys', None)
        port = config.get('port', 12350)
        if keys is None or len(keys) == 0:
            print "You need to specify at least one key to use " \
                "webapi"
            return
        self.server.listen_tcp(port, WebAPISite(self.server, keys))
        print ("webapi (%s) running on port %s" %
               (WEBAPI_VERSION, port))


def get_class():
    return WebAPIScriptFactory
