#!/usr/bin/python3.7

import signal
import snakes
import snakes.plugins
from simul import PNSim
snakes.plugins.load(["gv", "prob_timed_pl", "prior_pl"], "snakes.nets", "plugins")
from snakes.nets import *
from plugins import *

nodes = []


class Terminate(Exception):
    '''
    Simulation end event, raised when SIGINT or SIGTERM
    was captured.
    '''
    pass


def terminate(*args):
    raise Terminate

def temp_sensor(name, expected):

    n = PetriNet(name)

    n.declare('import random')
    n.declare(f'global name; name = "{name}" + str(random.randint(0, 1000))')

    temp_new = 12.
    temp_act = 0.
    timeout = 2 # sec

    w = Place('Wait', dot, check=tBlackToken)
    u = Place('Update', [], check=tBlackToken)
    it = Place('Input temp', [temp_new], check=tFloat)
    ta = Place('Current temp', [temp_act], check=tFloat)
    texp = Place('Temperature expected', [expected], check=tFloat)
    hen = Place('Enable_heater', [], check=tTuple)
    n.add_place(w)
    n.add_place(u)
    n.add_place(it)
    n.add_place(ta)
    n.add_place(hen)
    n.add_place(texp)

    timed = Transition('Next update', timeout=timeout)
    timed.add_input(w, Variable('x'))
    timed.add_output(u, Variable('x'))
    n.add_transition(timed)

    updated = Transition('Updated')
    updated.add_input(u, Variable('x'))
    updated.add_output(w, Variable('x'))
    updated.add_input(it, Variable('t'))
    updated.add_output(ta, Variable('t'))
    n.add_transition(updated)

    hswitch = Transition('Temperature switch')
    hswitch.add_input(ta, Variable('Tcurr'))
    hswitch.add_input(texp, Variable('Texp'))
    hswitch.add_output(texp, Variable('Texp'))
    hswitch.add_output(hen, Tuple((Expression('name'), Expression('Tcurr < Texp'))))
    n.add_transition(hswitch)

    n.add_remote_input(it, 'temp_gen/Measurement')
    n.add_remote_output(hen, 'boiler_logic/Sensory_input')

    n.draw(f'nets_png/{name}.png')

    return n

def execute():
    sim = PNSim()
    sens = temp_sensor('temp_sens', 14.0)

    sens.add_simulator(sim)
    sim.schedule_at([sim.execute_net, sens.name], PNSim.NOW)

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
