
""" King of the hill script by Sarcen """

from cuwo.script import ServerScript, ConnectionScript, command, admin
from cuwo.entity import (ItemData, ItemUpgrade, NAME_BIT,
                         AppearanceData, EntityData)
from cuwo.packet import KillAction, create_entity_data, MissionData
from cuwo.vector import Vector3
from cuwo.constants import CHUNK_SCALE, SECTOR_SCALE, BLOCK_SCALE
from cuwo.common import set_bit
from cuwo.server import entity_packet

import time
import math
import random
import copy

KOTH_DATA = 'kingofthehill_settings'

REWARD_WEAPONS = dict({
    # Weapons
    (3, 0): (1, ),   # 1h swords only iron
    (3, 1): (1, ),   # axes only iron
    (3, 2): (1, ),   # maces only iron
    (3, 3): (1, ),   # daggers only iron
    (3, 4): (1, ),   # fists only iron
    (3, 5): (1, ),   # longswords only iron
    (3, 6): (2, ),   # bows, only wood
    (3, 7): (2, ),   # crossbows, only wood
    (3, 8): (2, ),   # boomerangs, only wood

    (3, 10): (2, ),  # wands, only wood
    (3, 11): (2, ),     # staffs, only wood
    (3, 12): (11, 12),   # bracelets, silver, gold

    (3, 13): (1, ),    # shields, only iron

    (3, 15): (1, ),    # 2h, only iron
    (3, 16): (1, ),    # 2h, only iron
    (3, 17): (1, 2),   # 2h mace, iron and wood
})

REWARD_ARMOR = dict({
    # Equipment
    # chest warrior (iron), mage (silk), ranger(linen), rogue(cotton)
    (4, 0): (1, 25, 26, 27),
    # gloves warrior (iron), mage (silk), ranger(linen), rogue(cotton)
    (5, 0): (1, 25, 26, 27),
    # boots warrior (iron), mage (silk), ranger(linen), rogue(cotton)
    (6, 0): (1, 25, 26, 27),
    # shoulder warrior (iron), mage (silk), ranger(linen), rogue(cotton)
    (7, 0): (1, 25, 26, 27),
    (8, 0): (11, 12),  # rings, gold and silver
    (9, 0): (11, 12),  # amulets, gold and silver
})

REWARD_MISC = dict({
    (11, 14): (128, 129, 130, 131),
})

REWARD_PET_ITEMS = dict({})

REWARD_PETS = (19, 22, 23, 25, 26, 27, 30, 33, 34, 35, 36, 37, 38, 39, 40, 50,
               53, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 74, 75,
               86, 87, 88, 90, 91, 92, 93, 98, 99, 102, 103, 104, 105, 106,
               151)


# generate pets and petfood in the reward item list based on reward pets
def generate_pets():
    for pet in REWARD_PETS:
        REWARD_PET_ITEMS[(19, pet)] = (0, )
        REWARD_PET_ITEMS[(20, pet)] = (0, )


generate_pets()


def create_item_data():
    item_data = ItemData()
    item_data.type = 0
    item_data.sub_type = 0
    item_data.modifier = 0
    item_data.minus_modifier = 0
    item_data.rarity = 0
    item_data.material = 0
    item_data.flags = 0
    item_data.level = 0
    item_data.items = []
    for _ in xrange(32):
        new_item = ItemUpgrade()
        new_item.x = 0
        new_item.y = 0
        new_item.z = 0
        new_item.material = 0
        new_item.level = 0
        item_data.items.append(new_item)
    item_data.upgrade_count = 0
    return item_data


class KotHConnection(ConnectionScript):
    reward_points = 0

    def on_join(self, event):
        if not self.parent.event_entity is None:
            entity_packet.set_entity(self.parent.event_entity,
                                     self.parent.event_entity.entity_id)
            self.connection.send_packet(entity_packet)

        if not self.parent.event_dummy is None:
            entity_packet.set_entity(self.parent.event_dummy,
                                     self.parent.event_dummy.entity_id)
            self.connection.send_packet(entity_packet)

    def add_points(self, pts):
        new_points = self.reward_points + pts

        pct = [0.25, 0.75, 0.50]
        maxpts = self.parent.reward_points

        for i in xrange(len(pct)):
            if (new_points >= pct[i] * maxpts and
                    self.reward_points < pct[i] * maxpts):
                self.connection.send_chat((("You are {}% on your way" +
                                          " to receiving an item.")
                                          .format(int(pct[i] * 100))))

        self.reward_points = new_points

    def remove_points(self, pts):
        self.reward_points -= pts


class KotHServer(ServerScript):
    connection_class = KotHConnection
    proximity_radius = 1700000 ** 2
    tick_frequency = 5.0
    last_tick = 0
    item_drop_radius = 1000000
    reward_points = 10000
    copper_per_tick = 0
    xp_per_tick = 2
    king_xp_bonus = 10
    points_per_tick = 0
    king_points_per_tick = 0
    event_active = False
    event_location = None
    event_entity = None
    event_dummy = None
    event_mission = None
    players_in_proximity = []
    king = None
    king_start = 0
    king_rewards = 0
    king_next_reward = 0
    max_level = 0

    def on_load(self):
        self.load_config()

        try:
            self.max_level = self.server.config.anticheat.level_cap
        except KeyError:
            pass
        except AttributeError:
            pass

        config = self.server.config.kingofthehill
        self.king_xp_bonus = config.king_xp_bonus
        self.xp_per_tick = config.xp_per_tick
        self.copper_per_tick = config.copper_per_tick
        self.tick_frequency = config.tick_frequency

        self.points_per_tick = (self.reward_points /
                               (config.reward_frequency /
                                self.tick_frequency))

        self.king_points_per_tick = (self.reward_points /
                                    (config.king_reward_frequency /
                                     self.tick_frequency))

    def load_config(self):
        self.saved_config = self.server.load_data(KOTH_DATA, {})

        if 'location_x' in self.saved_config:
            self.event_location = Vector3(self.saved_config['location_x'],
                                          self.saved_config['location_y'],
                                          self.saved_config['location_z'])
        if 'radius' in self.saved_config:
            self.proximity_radius = self.saved_config['radius']

        if not self.event_location is None:
            self.start(self.event_location)

    def save_config(self):
        if not self.event_location is None:
            self.saved_config['location_x'] = self.event_location.x
            self.saved_config['location_y'] = self.event_location.y
            self.saved_config['location_z'] = self.event_location.z
        self.saved_config['radius'] = self.proximity_radius

        self.server.save_data(KOTH_DATA, self.saved_config)

    def update(self, event=None):
        if not self.event_active:
            return

        if not self.event_mission is None:
            self.server.update_packet.missions.append(self.event_mission)

        if (time.time() - self.last_tick >
                self.tick_frequency):
            self.do_proximity_check()
            self.grant_xp_and_gold()
            self.last_tick = time.time()

    def do_proximity_check(self):
        server = self.server
        players = server.players.values()
        bad_items = []
        for player in self.players_in_proximity:
            if not player in players:
                bad_items.append(player)

        for player in bad_items:
            self.players_in_proximity.remove(player)

        for player in players:
            distance = (self.event_location -
                        player.position).magnitude_squared()

            if (distance < self.proximity_radius and
                    player.entity_data.hp > 0):
                if not player in self.players_in_proximity:
                    self.players_in_proximity.append(player)
            elif player in self.players_in_proximity:
                self.players_in_proximity.remove(player)

        if len(self.players_in_proximity) > 0:
            if (self.king is None or
                (self.king.entity_id
                    != self.players_in_proximity[0].entity_id)):
                self.king_start = time.time()
                self.king = self.players_in_proximity[0]
                self.event_entity.name = self.king.name
                self.event_entity.mask = 0x0000FFFFFFFFFFFF
                print "New king of the hill", self.king.name
        elif not self.king is None:
            self.event_entity.name = u"King ofthe Hill"
            self.event_entity.mask = 0x0000FFFFFFFFFFFF
            self.king = None

    def find_player_script(self, player):
        for child in self.children:
            if child.connection == player:
                return child
        return None

    def grant_xp_and_gold(self):
        if len(self.players_in_proximity) == 0:
            return

        for player in self.players_in_proximity:
            xp = self.xp_per_tick
            player_script = player.scripts.kingofthehill
            if player.entity_id == self.king.entity_id:
                xp += self.king_xp_bonus
                player_script.add_points(self.king_points_per_tick)
            else:
                player_script.add_points(self.king_points_per_tick)

            self.give_xp(player, xp)

            if player_script.reward_points > self.reward_points:
                player_script.remove_points(self.reward_points)
                message = (("{name} has reached {points} points," +
                           " and receives an additional reward!")
                           .format(name=player.name,
                                   points=self.reward_points))

                print message
                self.server.send_chat(message)
                item = self.generate_item(self.king.entity_data)
                self.king.give_item(item)

        self.drop_gold(self.copper_per_tick)

    def drop_gold(self, amount):
        gold_coins = int(amount / 10000)
        amount -= gold_coins * 10000
        silver_coins = int(amount / 100)
        amount -= silver_coins * 100
        copper_coins = amount

        # signed short limit
        if gold_coins > 32767:
            gold_coins = 32767

        if gold_coins > 0:
            gold = create_item_data()
            gold.type = 12
            gold.material = 11
            gold.level = gold_coins
            self.drop_item(gold)

        if silver_coins > 0:
            silver = create_item_data()
            silver.type = 12
            silver.material = 12
            silver.level = silver_coins
            self.drop_item(silver)

        if copper_coins > 0:
            copper = create_item_data()
            copper.type = 12
            copper.material = 10
            copper.level = copper_coins
            self.drop_item(copper)

    def drop_item(self, item):
        position = self.event_location.copy()

        d = random.uniform(0, 1) * math.pi * 2
        r = math.sqrt(random.uniform(0, 1)) * self.item_drop_radius
        position.x += math.cos(d) * r
        position.y += math.sin(d) * r
        self.server.drop_item(item, position)

    def give_xp(self, player, amount):
        # don't give XP to max levels
        if self.max_level == 0 or player.entity_data.level < self.max_level:
            update_packet = self.server.update_packet
            action = KillAction()
            action.entity_id = player.entity_id
            action.target_id = self.event_dummy.entity_id
            action.xp_gained = amount
            update_packet.kill_actions.append(action)

    def set_radius(self, topostion):
        if not self.event_location is None:
            dist = (self.event_location - topostion).magnitude_squared()
            self.proximity_radius = dist
            self.save_config()

    def start(self, location):
        print "King of the hill mode activated at " + str(location)
        self.event_location = location.copy()
        self.event_active = True

        entity = self.event_entity
        if entity is None:
            entity = EntityData()

        # Fixed entity id, should be changed to some sort of entity spawning
        # system.
        entity.mask = 0x0000FFFFFFFFFFFF
        entity.entity_id = 1000
        entity.pos = location.copy()
        entity.pos += Vector3(0, 0, 100000)
        entity.body_roll = 0
        entity.body_pitch = 0
        entity.body_yaw = 0
        entity.velocity = Vector3()
        entity.accel = Vector3()
        entity.extra_vel = Vector3()
        entity.look_pitch = 0
        entity.physics_flags = 0
        entity.speed_flags = 6
        entity.entity_type = 140  # Scarecrow
        entity.current_mode = 0
        entity.last_shoot_time = 0
        entity.hit_counter = 0
        entity.last_hit_time = 0

        entity.appearance = AppearanceData()
        appearance = entity.appearance
        appearance.not_used_1 = 0
        appearance.not_used_2 = 0
        appearance.hair_red = 0
        appearance.hair_green = 0
        appearance.hair_blue = 0
        appearance.movement_flags = 1
        appearance.entity_flags = 0
        appearance.scale = 2.0
        appearance.bounding_radius = 1.0
        appearance.bounding_height = 6.0
        appearance.head_model = -32767
        appearance.hair_model = -32767
        appearance.hand_model = -32767
        appearance.foot_model = -32767
        appearance.body_model = 2109
        appearance.back_model = -32767
        appearance.shoulder_model = -32767
        appearance.wing_model = -32767
        appearance.head_scale = 1.0
        appearance.body_scale = 1.0
        appearance.hand_scale = 1.0
        appearance.foot_scale = 1.0
        appearance.shoulder_scale = 1.0
        appearance.weapon_scale = 1.0
        appearance.back_scale = 1.0
        appearance.unknown = 1.0
        appearance.wing_scale = 1.0
        appearance.body_pitch = 0
        appearance.arm_pitch = 0
        appearance.arm_roll = 0
        appearance.arm_yaw = 0
        appearance.feet_pitch = 0
        appearance.wing_pitch = 0
        appearance.back_pitch = 0
        appearance.body_offset = Vector3()
        appearance.head_offset = Vector3()
        appearance.hand_offset = Vector3()
        appearance.foot_offset = Vector3()
        appearance.back_offset = Vector3()
        appearance.wing_offset = Vector3()

        entity.flags_1 = 0
        entity.flags_2 = 0
        entity.roll_time = 0
        entity.stun_time = -10000
        entity.slowed_time = 0
        entity.make_blue_time = 0
        entity.speed_up_time = 0
        entity.show_patch_time = 0
        entity.class_type = 0
        entity.specialization = 0
        entity.charged_mp = 0
        entity.not_used_1 = 0
        entity.not_used_2 = 0
        entity.not_used_3 = 0
        entity.not_used_4 = 0
        entity.not_used_5 = 0
        entity.not_used_6 = 0
        entity.ray_hit = Vector3()
        entity.hp = 10000000000
        entity.mp = 0
        entity.block_power = 0
        entity.max_hp_multiplier = 1000
        entity.shoot_speed = 0
        entity.damage_multiplier = 0
        entity.armor_multiplier = 10000
        entity.resi_multiplier = 10000
        entity.not_used7 = 0
        entity.not_used8 = 0
        entity.level = math.pow(2, 31) - 1
        entity.current_xp = 0
        entity.parent_owner = 0
        entity.unknown_or_not_used1 = 0
        entity.unknown_or_not_used2 = 0
        entity.unknown_or_not_used3 = 0
        entity.unknown_or_not_used4 = 0
        entity.unknown_or_not_used5 = 0
        entity.not_used11 = 0
        entity.not_used12 = 0
        entity.super_weird = 0
        entity.spawn_pos = entity.pos
        entity.not_used19 = 0
        entity.not_used20 = 0
        entity.not_used21 = 0
        entity.not_used22 = 0
        entity.consumable = create_item_data()
        entity.equipment = []
        for _ in xrange(13):
            new_item = create_item_data()
            entity.equipment.append(new_item)
        entity.skills = []
        for _ in xrange(11):
            entity.skills.append(0)
        entity.mana_cubes = 0
        entity.name = u"King ofthe Hill"

        self.event_entity = entity
        self.server.entities[entity.entity_id] = entity

        dummy = copy.deepcopy(self.event_entity)
        dummy.entity_id = 1001
        dummy.speed_flags = 1  # Hostile dummy, required for KillAction to work
        dummy.pos = Vector3(10000, 10000, 10000)
        self.event_dummy = dummy
        self.server.entities[dummy.entity_id] = dummy

        self.create_mission_data()

        self.save_config()

    def create_mission_data(self):
        mission = MissionData()
        mission.section_x = int(self.event_entity.pos.x / SECTOR_SCALE)
        mission.section_y = int(self.event_entity.pos.y / SECTOR_SCALE)
        mission.something1 = 1
        mission.something2 = 1
        mission.something3 = 1
        mission.something4 = 1
        mission.something5 = 1
        mission.monster_id = self.event_entity.entity_id
        mission.quest_level = 500
        mission.something8 = 1
        mission.something9 = 1
        mission.something10 = 100
        mission.something11 = 100
        mission.chunk_x = int(self.event_entity.pos.x / CHUNK_SCALE)
        mission.chunk_y = int(self.event_entity.pos.y / CHUNK_SCALE)
        self.event_mission = mission

    def random_item(self, itemdict):
        list = itemdict.keys()
        item_key = list[random.randint(0, len(list) - 1)]
        item = create_item_data()
        item.type = item_key[0]
        item.sub_type = item_key[1]
        materials = itemdict[item_key]
        item.material = materials[random.randint(0, len(materials) - 1)]
        return item

    def generate_item(self, entity_data):
        item_bias = random.randint(0, 100)

        if item_bias < 30:
            item = self.random_item(REWARD_WEAPONS)
        elif item_bias < 60:
            item = self.random_item(REWARD_ARMOR)
        elif item_bias < 95:
            item = self.random_item(REWARD_MISC)
        else:
            item = self.random_item(REWARD_PET_ITEMS)

        if item.type == 11:
            item.rarity = 2
        elif item.type == 20 or item.type == 19:
            item.rarity = 0
        else:
            item.rarity = random.randint(3, 4)

        if item.type == 19 or item.type == 11:
            item.modifier = 0
        else:
            item.modifier = random.randint(0, 16777216)

        if item.type == 20:
            item.level = 1
        else:
            item.level = entity_data.level

        return item

    def get_mode(self, event):
        return 'king of the hill'


def get_class():
    return KotHServer


@command
@admin
def koth_set_radius(script):
    script.parent.set_radius(script.connection.position)


# koth_start, starts a king of the hill event at the location of the caller
@command
@admin
def koth_start(script):
    script.parent.start(script.connection.position)
