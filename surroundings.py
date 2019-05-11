#!/usr/bin/python3.7
from template import *
from sample_nets import *


def execute_surroundings():
    nets = []
    temp_gen = temp_generator(
        'weather-generator', low=5, high=18, samples=100, speedup=100)
    nets.append(temp_gen)

    execute_nets(nets, sim_id='surroundings')


if __name__ == "__main__":
    execute_surroundings()
