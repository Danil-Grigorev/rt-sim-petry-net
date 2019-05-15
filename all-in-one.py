#!/usr/bin/python3.7
from template import *
from sample_nets import *


def execute_boiler():
    boiler_log = boiler_logic('boiler-logic')
    return([boiler_log])

def execute_surround():
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
    temp_gen = temp_generator(
        'weather-generator', low=5, high=18, samples=100, speedup=100)
    nets.append(temp_gen)
    for room in timetable:
        nets.append(room_timetable(room, timetable[room]))

    return nets

def execute_rooms(rooms=None):
    nets = []

    if rooms is None:
        rooms = {
            'kitchen': {
                'qpc': 17.5,
                'q_gps': 0.34,  # W/s
                'q_lps': 0.2,  # W/s
                'heat_time': 5,  # Timeout for heater output update
                'exch_time': 30,  # Timeout for temp loss/gain update
                'exp_temp': 20.0,
                'starting_temp': 18.0
            },
            'dining_room': {
                'qpc': 24.0,
                'q_gps': 0.5,  # W/s
                'q_lps': 0.4,  # W/s
                'heat_time': 5,  # Timeout for heater output update
                'exch_time': 30,  # Timeout for temp loss/gain update
                'exp_temp': 19.0,
                'starting_temp': 18.0
            },
            'storeroom': {
                'qpc': 13.0,
                'q_gps': 0.26,  # W/s
                'q_lps': 0.17,  # W/s
                'heat_time': 5,  # Timeout for heater output update
                'exch_time': 30,  # Timeout for temp loss/gain update
                'exp_temp': 15.0,
                'starting_temp': 5.0
            }
        }
    for room in rooms:
        args = rooms[room]
        nets.append(room_heating(room, args['q_gps'], args['heat_time']))
        nets.append(room_temp_update(room, args['qpc'], args['starting_temp']))
        nets.append(room_outside_exchange(
            room, args['q_lps'], args['exch_time']))
        nets.append(room_sens(room, args['exp_temp']))
    return nets

def execute_all_in_one():
    nets = []

    nets.extend(execute_boiler())
    nets.extend(execute_rooms())
    nets.extend(execute_surround())

    execute_nets(nets, sim_id='all-in-one')

if __name__ == "__main__":
    execute_all_in_one()
