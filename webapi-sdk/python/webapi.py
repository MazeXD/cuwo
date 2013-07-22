
import json
import time
from urllib import urlencode
import urllib2


URL_FORMAT = 'http://{host}:{port}/{endpoint}'


class UnauthorizedError (Exception):
    pass


class InvalidResourceError (Exception):
    pass


class InvalidPlayerError (Exception):
    pass


class InvalidTimeError (Exception):
    pass


class InvalidMethodError (Exception):
    pass


ERROR_CODES = {
    -1: UnauthorizedError,
    -2: InvalidResourceError,
    -3: InvalidPlayerError,
    -4: InvalidTimeError,
    -5: InvalidMethodError
}


class Status (object):
    def __init__(self, result):
        self.players = result['players']
        self.player_limit = result['player-limit']
        self.seed = result['seed']

    def __str__(self):
        return 'Status {players=%s, player_limit=%s, seed=%s}' % (
            self.players, self.player_limit, self.seed)


class Player (object):
    def __init__(self, result):
        self.has_equipment = 'equipment' in result
        self.has_skills = 'skills' in result
        self.name = result['name']
        self.position = {'x': result['position']['x'],
                         'y': result['position']['y'],
                         'z': result['position']['z']}
        self.class_type = result['class']
        self.specialization = result['specialization']
        self.level = result['level']
        self.power_level = result['power-level']
        if self.has_equipment:
            self._parse_equipment(result['equipment'])
        if self.has_skills:
            self._parse_skills(result['skills'])

    def _parse_equipment(self, result):
        self.equipment = []
        for item in result:
            self.equipment.append(Item(item))

    def _parse_skills(self, result):
        self.skills = {
            'pet_master': result['pet-master'],
            'riding': result['riding'],
            'climbing': result['climbing'],
            'hang_gliding': result['hang-gliding'],
            'swimming': result['swimming'],
            'sailing': result['sailing'],
            'class_skill_1': result['class-skill-1'],
            'class_skill_2': result['class-skill-2'],
            'class_skill_3': result['class-skill-3'],
        }

    def __str__(self):
        string = "Player {name=%s, position=%s, ...}" % (
            self.name, self.position)
        if self.has_equipment:
            string += ' [Has_Equipment]'
        if self.has_skills:
            string += ' [Has_Skills]'
        return string


class Item (object):
    def __init__(self, result):
        self.type = result['type'],
        self.sub_type = result['sub-type']
        self.modifier = result['modifier']
        self.minus_modifier = result['minus-modifier']
        self.rarity = result['rarity']
        self.material = result['material']
        self.flags = result['flags']
        self.level = result['level']
        self.power_level = result['power-level']
        self.upgrades = []
        for upgrade in result['upgrades']:
            self.upgrades.append(ItemUpgrade(upgrade))

    def __str__(self):
        string = "Item {type=%s, sub_type=%s, rarity=%s, ...}" % (
            self.type, self.sub_type, self.rarity)
        string += " [%s upgrades]" % len(self.upgrades)
        return string


class ItemUpgrade (object):
    def __init__(self, result):
        self.x = result['x']
        self.y = result['y']
        self.z = result['z']
        self.material = result['material']
        self.level = result['level']

    def __str__(self):
        return "ItemUpgrade {x=%s, y=%s, z=%s, material=%s, level=%s}" % (
            self.x, self.y, self.z, self.material, self.level)


class WebAPI (object):
    def __init__(self, key, host, port=12350):
        self.__key = key
        self.__host = host
        self.__port = port
        self._setup_opener()

    def _setup_opener(self):
        opener = urllib2.build_opener()
        opener.addheaders = [('User-Agent', 'CuwoAPI/0.0.3')]
        self.opener = opener

    def _generate_url(self, endpoint, secure, query_params=None):
        url = URL_FORMAT.format(host=self.__host, port=self.__port,
                                endpoint=endpoint)
        if secure:
            url += '?' + urlencode({'key': self.__key})

        if query_params is not None:
            if secure:
                url += '&'
            else:
                url += '?'
            params = urlencode(query_params)
            url += params
        return url

    def _send(self, endpoint='', data=None, secure=True, query_params=None):
        url = self._generate_url(endpoint, secure, query_params)
        request = urllib2.Request(url, data)
        if data is not None:
            request.add_header("Content-Type",
                               "application/x-www-form-urlencoded")
        result = self.opener.open(request).read()
        return self._parse(result)

    def _handle_error(self, result):
        error_code = result['error']
        raise ERROR_CODES[error_code]()

    def _parse(self, data):
        result = json.loads(data)
        if 'error' in result:
            self._handle_error(result)
        return result

    def version(self):
        result = self._send(secure=False)
        return result['version']

    def status(self):
        result = self._send('status')
        return Status(result)

    def player(self, name, include_equipment=False, include_skills=False):
        inclusion = []
        if include_equipment:
            inclusion.append('equipment')
        if include_skills:
            inclusion.append('skills')
        params = None
        if(len(inclusion) > 0):
            params = {'include': ','.join(inclusion)}
        result = self._send('player/%s' % name, query_params=params)
        return Player(result['player'])

    def kick(self, name):
        result = self._send('kick/%s' % name)
        return 'success' in result

    def time(self, value=None):
        if value is None:
            result = self._send('time')
            return result['time']
        try:
            time.strptime(value, '%H:%M')
            result = self._send('time/%s' % value)
            return 'success' in result
        except ValueError:
            raise InvalidTimeError()

    def message(self, message, receiver=None):
        endpoint = 'message/'
        if receiver is not None:
            endpoint += '%s/' % receiver
        result = self._send(endpoint, message)
        return 'success' in result


def main():
    api = WebAPI('demo', '127.0.0.1')

    # Get version
    print 'Version: %s' % api.version()

    # Get status
    status = api.status()
    print status

    # Get player details
    if 'Xharon' in status.players:
        player = api.player('Xharon', include_equipment=True,
                            include_skills=True)
        print player

    # Set time
    if api.time('16:05'):
        print 'Time set'

    # Get time
    time = api.time()
    print 'Time: %s' % time

    # Send global message
    if api.message('Hello server - API'):
        print 'Message has been sent'

    # Send message to player
    if 'Xharon' in status.players:
        if api.message('Hey. How are you?', 'Xharon'):
            print 'Message has been sent to Xharon'

    # Kick player
    if 'Xharon' in status.players:
        if api.kick('Xharon'):
            print 'Xharon has been kicked'

if __name__ == '__main__':
    main()
