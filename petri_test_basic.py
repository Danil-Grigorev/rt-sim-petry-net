#!/usr/bin/python3.7

import signal
import snakes
import snakes.plugins
from simul import PNSim
snakes.plugins.load(["gv", "prob_timed_pl", "prior_pl"], "snakes.nets", "plugins")
from snakes.nets import *
from plugins import *

import time

nodes = []

class Terminate(Exception):
    '''
    Simulation end event, raised when SIGINT or SIGTERM
    was captured.
    '''
    pass


def terminate(*args):
    raise Terminate

def factory(cons, prod, init=[1, 2, 3]):
    n = PetriNet("N")
    n.add_place(Place("src", init))
    n.add_place(Place("tgt", []))
    t = Transition("t")
    n.add_transition(t)
    n.add_input("src", "t", cons)
    n.add_output("tgt", "t", prod)
    return n, t, t.modes()


def transport_proto(name):

    n = PetriNet(name)


    packets = [
        (1, "COL"),
        (2, "OUR"),
        (3, "ED"),
        (4, "PET"),
        (5, "RI"),
        (6, "NET")
    ]
    n.add_place(Place("Packets to send", packets, check=tPair))
    n.add_place(Place("NextSend", [1], check=tInteger))
    n.add_place(Place("A", check=tPair))

    snd_pack = Transition("Send Packet")
    n.add_transition(snd_pack)

    n.add_input("Packets to send", "Send Packet", Tuple([Variable("n"), Variable("d")]))
    n.add_output("Packets to send", "Send Packet", Tuple([Variable("n"), Variable("d")]))
    n.add_input("NextSend", "Send Packet", Variable("n"))
    n.add_output("NextSend", "Send Packet", Variable("n"))

    n.add_place(Place("B", check=tPair))

    # trans_pack = Transition("Transmit Packet", Expression("update_success()"))
    trans_pack = Transition("Transmit Packet")
    n.add_transition(trans_pack)
    n.add_output("A", "Send Packet", Tuple([Variable("n"), Variable("d")]))
    n.add_input("A", "Transmit Packet", Tuple([Variable("n"), Variable("d")]))
    # n.add_output("B", "Transmit Packet", Expression("success_tr(" + str(Tuple([Variable("n"), Variable("d")])) + ")"))
    n.add_output("B", "Transmit Packet", Tuple([Variable("n"), Variable("d")]))


    n.add_place(Place("C", check=tInteger))
    n.add_place(Place("Transmit port", [""], tString))
    n.add_place(Place("NextRec", [1], tInteger))

    rec_pack = Transition("Receive Packet")
    # rec_pack.add_remote_output("Receiver", "Transmit port")
    n.add_transition(rec_pack)
    n.add_input("B", "Receive Packet", Tuple([Variable("n"), Variable("d")]))
    n.add_output("C", "Receive Packet", Expression("n+1"))
    n.add_input("Transmit port", "Receive Packet", Variable("data"))
    n.add_output("Transmit port", "Receive Packet", Expression("n==k and data+d or data"))
    n.add_input("NextRec", "Receive Packet", Variable("k"))
    n.add_output("NextRec", "Receive Packet", Expression("n==k and k+1 or k"))

    d = Place("D", check=tInteger)
    n.add_place(d)

    tr_ack = Transition("Transmit Ack")
    n.add_transition(tr_ack)
    n.add_output("D", "Transmit Ack", Variable("n"))
    n.add_input("C", "Transmit Ack", Variable("n"))

    rec_ack = Transition("Receive Ack")
    n.add_transition(rec_ack)
    n.add_input("D", "Receive Ack", Variable("n"))
    n.add_output("NextSend", "Receive Ack", Variable("n"))
    n.add_input("NextSend", "Receive Ack", Variable("k"))

    # n.add_remote_output('Transmit port', 'transm/Data Input')

    return n

def result_net(name):
    n = PetriNet(name)
    d = Place('Data Received', check=tString)
    n.add_place(d)

    return n

def transmit_net(name):
    n = PetriNet(name)
    i = Place('Data Input', check=tString)
    trans = Place('Data Transmit', check=tString)
    o = Place('Data Output', check=tString)
    lost = Place('Data Lost', check=tString)
    t = Transition('t', prob=0.6)
    l = Transition('l', prob=0.2)
    l2 = Transition('l2')
    tr = Transition('Transmit')
    t.add_neighbour_transition(l)
    l2.add_neighbour_transition(l)
    n.add_transition(l)
    n.add_transition(t)
    n.add_transition(l2)
    n.add_transition(tr)
    n.add_place(trans)
    n.add_place(o)
    n.add_place(i)
    n.add_place(lost)
    n.add_output('Data Output', tr.name, Variable("data"))
    n.add_output('Data Lost', l2.name, Variable('data'))
    n.add_output('Data Lost', l.name, Variable('data'))
    n.add_output('Data Transmit', 't', Variable('data'))
    n.add_input('Data Transmit', tr.name, Variable('data'))
    n.add_input('Data Input', t.name, Variable("data"))
    n.add_input('Data Input', l.name, Variable('data'))
    n.add_input('Data Input', l2.name, Variable("data"))
    n.add_remote_input(i, 'net/Transmit port')
    # n.add_remote_output(o, 'res/Data Received')

    return n

def execute(net_t=1):
    if net_t == 1:
        nets, tr, modes = factory(Variable('x'), Variable('x'))
        # nets.draw('in.png')
        tr.fire(modes[1])
        # nets.draw('out.png')
    elif net_t == 2:
        sim = PNSim()
        sim2 = PNSim()
        net = transport_proto('net')
        net1 = transport_proto('net1')
        transm = transmit_net('transm')
        res = result_net('res')
        # res.add_remote_input('Data Received', 'net/Transmit port')
        res.add_simulator(sim)
        net.add_simulator(sim)

        transm.add_simulator(sim2)
        net1.add_simulator(sim2)

        # net.add_remote_output('Transmit port', 'res/Data Received')
        # n1.place("Transmit port").set_output(n1, 'res/Data Received')
        # place = n.place()[0]
        sim.schedule_at([sim.execute_net, net.name], PNSim.NOW)

        # sim.schedule_at([sim.execute_net, transm], 3)
        # sim.schedule_at(6, [sim.execute_net, res])
        # sim.schedule_at([sim.execute_net, net], 9)

        sim.setup()
        nodes.append(sim)
        nodes.append(sim2)
        try:
            sim2.schedule_at([sim2.execute_net, net1.name], 4)
            sim2.setup()
            sim2.start()
            time.sleep(5)
            sim.start()
            for node in nodes:
                node.join()
        except Terminate:
            for node in nodes:
                node.kill = True
                print(node.mqtt.remote_requests)
            for node in nodes:
                if node.is_alive():
                    node.wake()
            print('done')
        print(sim._running_events)
        print(sim2._running_events)
        for name, net in sim._nets.items():
            net.draw(f'nets_png/{name}.png')


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    execute(2)

