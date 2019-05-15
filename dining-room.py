#!/usr/bin/python3.7
from template import *
from sample_nets import *

def dining_room():
    nets = []

    rooms = {
        'dining_room': {
            'qpc': 24.0,
            'q_gps': 0.5,  # W/s
            'q_lps': 0.4,  # W/s
            'heat_time': 5,  # Timeout for heater output update
            'exch_time': 30,  # Timeout for temp loss/gain update
            'exp_temp': 19.0,
            'starting_temp': 18.0
        }
    }
    room = 'dining_room'
    args = rooms[room]
    nets.append(room_heating(room, args['q_gps'], args['heat_time']))
    nets.append(room_temp_update(room, args['qpc'], args['starting_temp']))
    nets.append(room_outside_exchange(
        room, args['q_lps'], args['exch_time']))
    nets.append(room_sens(room, args['exp_temp']))
    return nets


def execute_all_in_one():
    nets = []

    nets.extend(dining_room())

    execute_nets(nets, sim_id='dining-room')


if __name__ == "__main__":
    execute_all_in_one()
