#!/usr/bin/python3.7

import signal
import snakes
from snakes.nets import *   # Site, mista, prechody...
from simul import PNSim     # Simulacni knihovna
snakes.plugins.load(
    ["gv", "timed_pl", "sim_pl", "prob_pl", "prior_pl"],
    "snakes.nets",
    "plugins")  # Seznam rozsireni pro import
from plugins import *  # Redefinovane metody z rozsireni


class Terminate(Exception):
    '''
    Simulation end event, raised when SIGINT or SIGTERM
    was captured.
    '''
    pass


def terminate(*args):
    raise Terminate


def add_net(net, sim):
    net.add_simulator(sim)
    sim.schedule_at([sim.execute_net, net.name], PNSim.NOW)


def execute_nets(net_list, broker=None, sim_id=None, detached=True, debug=True):
    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    sim = PNSim(broker=broker, simul_id=sim_id, detached=detached, debug=debug)
    if isinstance(net_list, list):
        for net in net_list:
            add_net(net, sim)
    else:
        net = net_list
        add_net(net, sim)

    sim.setup()
    try:
        sim.start()
        sim.join()
    except Terminate:
        sim.kill = True
        if sim.is_alive():
            sim.wake()
    for name, net in sim._nets.items():
        net.draw(f'nets_png/{name}.png')

