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

def boiler_logic(name):
    n = PetriNet(name)

    sin = Place('Sensory_input', [('x', True), ('y', False), ('x', False)], check=tTuple)
    newn = Place('New net', [], check=tTuple)
    tabl = Place('Table', [], check=tTuple)
    n.add_place(tabl)
    n.add_place(newn)
    n.add_place(sin)

    utable = Transition('Update table')
    utable.add_input(sin, Tuple((Variable('name'), Variable('enabled'))))
    utable.add_output(newn, Tuple((Variable('name'), Variable('enabled'))))
    n.add_transition(utable)

    ustate = Transition('Update state', guard=Expression('name == existing_name'), prior=1)
    ustate.add_input(sin, Tuple((Variable('name'), Variable('enabled'))))
    ustate.add_input(tabl, Tuple((Variable('existing_name'), Variable('x'))))
    ustate.add_output(tabl, Tuple((Variable('name'), Variable('enabled'))))
    n.add_transition(ustate)

    itable = Transition('Insert table')
    itable.add_input(newn, Tuple((Variable('name'), Variable('enabled'))))
    itable.add_output(tabl, Tuple((Variable('name'), Variable('enabled'))))
    n.add_transition(itable)

    n.draw(f'nets_png/{name}.png')

    return n

def execute():
    sim = PNSim()
    boiler_log = boiler_logic('boiler_logic')

    boiler_log.add_simulator(sim)
    sim.schedule_at([sim.execute_net, boiler_log.name], PNSim.NOW)

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
