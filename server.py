#!/usr/bin/python3.7
from template import *
from sample_nets import *


def timetables():
    nets = []


    timetable = {
        'kitchen': [
            (23, 00, 19.0),
            (6, 00, 22.0),
            (10, 00, 20.0),
            (19, 00, 21.0)
        ],
        'dining_room': [
            (23, 00, 18.0),
            (6, 30, 22.0),
            (10, 00, 19.0),
            (17, 00, 21.0)
        ]
    }

    for room in timetable:
        nets.append(room_timetable(room, timetable[room]))

    return nets


def execute_room_sensors(rooms=None):
    nets = []

    if rooms is None:
        rooms = {
            'kitchen': {
                'exp_temp': 20.0,
            },
            'dining_room': {
                'exp_temp': 19.0,
            },
            'storeroom': {
                'exp_temp': 15.0,
            }
        }
    for room in rooms:
        nets.append(room_sens(room, rooms[room]['exp_temp']))
    return nets


def start_server():
    nets = []

    nets.extend(execute_room_sensors())
    nets.extend(timetables())

    execute_nets(nets, sim_id='server')


if __name__ == "__main__":
    start_server()
