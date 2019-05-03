#!/usr/bin/python3
import inspect
from template import *

def temp_placement(Tmin, Tmax, k):
    if k == 0:
        return float(format(Tmax, ".1f"))
    else:
        return float(
            format(Tmin + (Tmax-Tmin)*(cos(2*pi*k/f)/2 + 1/2), ".1f"))


def temp_generator(name, low, high, samples=48, speedup=1):
    """
    Jednoduchy generator vnejsiho prostredi - pocasi a casu

    name -- jmeno site
    low -- nejmensi teplota za den
    high -- nejversi teplota za den
    samples -- frekvence mereni teploty behem dne.
    speedup -- nasobici argument pro beh casu
    """

    n = PetriNet(name)

    assert speedup >= 1
    T = 24*60*60/samples/speedup  # Perioda zmen teploty
    k = 0  # Citac pro generator

    n.declare('from math import cos, pi')
    n.declare('import time, random')
    n.declare('random.seed(time.time)')
    n.declare('from random import random as r')
    n.declare(f'f = {samples}')
    n.declare(inspect.getsource(temp_placement))
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

    takt = Transition('takt', timeout=T)
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

    # n.add_remote_output(meas, 'temp_sens/Input temp')

    n.draw(f'nets_png/{name}.png')

    return n


def execute():
    temp_gen = temp_generator(
        'T outside generator', low=5, high=18, samples=100, speedup=100)
    execute_nets(temp_gen, sim_id='Surroundings-simulation')

if __name__ == '__main__':
    execute()
