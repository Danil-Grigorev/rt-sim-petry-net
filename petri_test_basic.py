#!/usr/bin/python3.7

import snakes
import snakes.plugins
from simul import PNSim
snakes.plugins.load(["gv", "mqtt_msg"], "snakes.nets", "plugins")
from snakes.nets import *
from plugins import *

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

    n.declare("import random")
    n.declare("succ_th=0.7")
    n.declare("success=True")

    n.declare("def success_tr(val):\n\
\tif success: return val\n\
\telse: return None")

    n.declare("def update_success(thres=succ_th): global success; success = (random.uniform(0,1) > thres); return True")

    n.declare("def copy(val): return val")

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

    snd_pack = Transition("Send Packet", Expression('update_success()'))
    n.add_transition(snd_pack)
    
    n.add_input("Packets to send", "Send Packet", Tuple([Variable("n"), Variable("d")]))
    n.add_output("Packets to send", "Send Packet", Tuple([Variable("n"), Variable("d")]))
    n.add_input("NextSend", "Send Packet", Variable("n"))
    n.add_output("NextSend", "Send Packet", Variable("n"))

    n.add_place(Place("B", check=tPair))
    n.add_place(Place("Loss", check=tPair))

    # trans_pack = Transition("Transmit Packet", Expression("update_success()"))
    trans_pack = Transition("Transmit Packet", Expression("success == True"))
    trans_loss = Transition("Packet Loss", Expression("success == False"))
    n.add_transition(trans_pack)
    n.add_transition(trans_loss)
    n.add_output("A", "Send Packet", Tuple([Variable("n"), Variable("d")]))
    n.add_input("A", "Transmit Packet", Tuple([Variable("n"), Variable("d")]))
    n.add_input("A", "Packet Loss", Tuple([Variable("n"), Variable("d")]))
    n.add_output("Loss", "Packet Loss", Tuple([Variable("n"), Variable("d")]))
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

    n.add_remote_output('Transmit port', 'transm/Data Input')

    return n

def result_net(name):
    n = PetriNet(name)
    d = Place('Data Received', check=tString)
    n.add_place(d)

    return n

def transmit_net(name):
    n = PetriNet(name)
    i = Place('Data Input', check=tString)
    o = Place('Data Output', check=tString)
    t = Transition('t')
    n.add_transition(t)
    n.add_place(o)
    n.add_place(i)
    n.add_output(o.name, t.name, Variable("data"))
    n.add_input(i.name, t.name, Variable("data"))
    n.add_remote_input(i, 'net/Transmit port')
    n.add_remote_output(o, 'res/Data Received')

    return n

def execute(net_t=1):
    if net_t == 1:
        nets, tr, modes = factory(Variable('x'), Variable('x'))
        # nets.draw('in.png')
        tr.fire(modes[1])
        # nets.draw('out.png')
    elif net_t == 2:
        sim = PNSim()
        net = transport_proto('net')
        net1 = transport_proto('net1')
        transm = transmit_net('transm')
        res = result_net('res')
        # res.add_remote_input('Data Received', 'net/Transmit port')
        res.add_simulator(sim)
        net.add_simulator(sim)
        net1.add_simulator(sim)
        # net.add_remote_output('Transmit port', 'res/Data Received')
        transm.add_simulator(sim)
        # n1.place("Transmit port").set_output(n1, 'res/Data Received')
        # place = n.place()[0]
        sim.schedule_at([sim.execute_net, net], PNSim.NOW)
        sim.schedule_at([sim.execute_net, net1], 4)
        # sim.schedule_at([sim.execute_net, transm], 3)
        # sim.schedule_at(6, [sim.execute_net, res])
        # sim.schedule_at([sim.execute_net, net], 9)

        sim.run()
        for name, net in sim._nets.items():
            net.draw('{}.png'.format(name))

        

if __name__ == "__main__":
    execute(2)

