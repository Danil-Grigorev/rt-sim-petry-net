#!/usr/bin/python3.7

import signal
import snakes
from snakes.nets import *   # Site, mista, prechody...
from simul import PNSim     # Simulacni knihovna
snakes.plugins.load(
    ["gv", "timed_pl", "sim_pl", "prob_pl", "prior_pl"],
    "snakes.nets",
    "plugins") # Seznam rozsireni pro import
from plugins import * # Redefinovane metody z rozsireni

nodes = []

class Terminate(Exception):
    '''
    Simulation end event, raised when SIGINT or SIGTERM
    was captured.
    '''
    pass


def terminate(*args):
    raise Terminate


def temp_generator(name, low, high, timeout):
    n = PetriNet(name)

    f = 48 # Frekvence mereni behem dne
    T = 24*60*60/f # Perioda zmen teploty
    k = 0 # Citac pro generator

    n.declare('from math import cos, pi')
    n.declare('import time, random')
    n.declare('random.seed(time.time)')
    n.declare('from random import random as r')
    n.declare(f'f = {f}')
    n.declare('def temp_placement(Tmin, Tmax, k):'
              '\n\tif k == 0:'
              '\n\t\treturn float(format(Tmax, ".1f"))'
              '\n\telse:'
              '\n\t\treturn float(format('
              'Tmin + (Tmax-Tmin)*(cos(2*pi*k/f)/2 + 1/2),'
                '".1f"))')
    temp_pl = Place('Temp_placement', [(low, high)], check=tTuple)
    gen = Place('Generator', [k], check=tInteger)
    gen_k = Place('Generator_k', [], check=tInteger)
    traw = Place('Temperature_raw', [], check=tFloat)
    meas = Place('Measurement', [0.], check=tFloat)
    n.add_place(gen)
    n.add_place(temp_pl)
    n.add_place(gen_k)
    n.add_place(traw)
    n.add_place(meas)

    takt = Transition('takt', timeout=timeout)
    takt.add_input(gen, Variable('k'))
    takt.add_output(gen, Expression('(1 + k) % f'))
    takt.add_output(gen_k, Variable('k'))
    n.add_transition(takt)

    tcalc = Transition('tcalc')
    tcalc.add_input(gen_k, Variable('k'))
    tcalc.add_output(traw, Expression('temp_placement(Tmin, Tmax, k)'))
    tcalc.add_input(temp_pl, Tuple((
        Variable('Tmin'), Variable('Tmax'))))
    tcalc.add_output(temp_pl, Tuple((
        Variable('Tmin'), Variable('Tmax'))))
    n.add_transition(tcalc)

    trainy = Transition('trainy', prob=0.2)
    tsunny = Transition('tsunny', prob=0.2)
    texpec = Transition('texpec', prob=0.6)
    trainy.add_neighbour_transition(texpec)
    trainy.add_neighbour_transition(tsunny)

    trainy.add_input(traw, Variable('Tnew'))
    trainy.add_output(meas, Expression('Tnew-r()*2'))
    n.add_transition(trainy)

    tsunny.add_input(traw, Variable('Tnew'))
    tsunny.add_output(meas, Expression('Tnew+r()*2'))
    n.add_transition(tsunny)

    texpec.add_input(traw, Variable('Tnew'))
    texpec.add_output(meas, Variable('Tnew'))
    n.add_transition(texpec)

    n.add_remote_output(meas, 'temp_sens/Input temp')

    n.draw(f'nets_png/{name}.png')

    return n


def execute():
    sim = PNSim()
    temp_gen = temp_generator('temp_gen', 5, 18, 30)

    temp_gen.add_simulator(sim)
    sim.schedule_at([sim.execute_net, temp_gen.name], PNSim.NOW)

    sim.setup()
    nodes.append(sim)
    try:
        sim.start()
        for node in nodes:
            node.join()
    except Terminate:
        for node in nodes:
            node.kill = True
        for node in nodes:
            if node.is_alive():
                node.wake()
    for name, net in sim._nets.items():
        net.draw(f'nets_png/{name}.png')


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    execute()
