#!/usr/bin/python3.7
from template import *
from sample_nets import *


def execute_boiler():
    boiler_log = boiler_logic('boiler-logic')
    return([boiler_log])


def execute_rooms(rooms=None):
    nets = []

    rooms = {
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
    room = 'storeroom'
    args = rooms[room]
    nets.append(room_heating(room, args['q_gps'], args['heat_time']))
    nets.append(room_temp_update(room, args['qpc'], args['starting_temp']))
    nets.append(room_outside_exchange(
        room, args['q_lps'], args['exch_time']))
    nets.append(room_sens(room, args['exp_temp']))
    return nets


def execute_all_in_one():
    nets = []

    nets.extend(execute_rooms())

    execute_nets(nets, sim_id='storeroom')


if __name__ == "__main__":
    execute_all_in_one()
