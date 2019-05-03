#!/usr/bin/python3.7
from template import *


def boiler_logic(name):
    n = PetriNet(name)

    sin = Place('Sensory input', [], check=tAll)
    tabl = Place('Table', [], check=tTuple)
    atabl = Place('Active Table', [], check=tString)
    poll = Place('Poll state', [], check=tBlackToken)
    boien = Place('Boiler enabled', [False], check=tBoolean)
    bost = Place('Boiler state', [], check=tBoolean)
    n.add_place(bost)
    n.add_place(boien)
    n.add_place(poll)
    n.add_place(atabl)
    n.add_place(tabl)
    n.add_place(sin)

    utable = Transition('Update table')
    utable.add_input(sin, Tuple((Variable('name'), Variable('enabled'))))
    utable.add_output(tabl, Tuple((Variable('name'), Variable('enabled'))))
    n.add_transition(utable)

    ustate = Transition('Update state', guard=Expression('name == existing_name'), prior=1)
    ustate.add_input(sin, Tuple((Variable('name'), Variable('enabled'))))
    ustate.add_input(tabl, Tuple((Variable('existing_name'), Variable('x'))))
    ustate.add_output(tabl, Tuple((Variable('name'), Variable('enabled'))))
    n.add_transition(ustate)

    exact = Transition('Extract active', guard=Expression('enabled == False'))
    exact.add_input(tabl, Tuple((Variable('name'), Variable('enabled'))))
    exact.add_input(atabl, Variable('name'))
    exact.add_output(tabl, Tuple((Variable('name'), Value('processed'))))
    exact.add_output(poll, Value(dot))
    n.add_transition(exact)

    inact = Transition('Insert active', guard=Expression('enabled == True'))
    inact.add_input(tabl, Tuple((Variable('name'), Variable('enabled'))))
    inact.add_output(atabl, Variable('name'))
    inact.add_output(tabl, Tuple((Variable('name'), Value('processed'))))
    inact.add_output(poll, Value(dot))
    n.add_transition(inact)

    upact = Transition('Update active', guard=Expression('enabled == True'), prior=1)
    upact.add_input(tabl, Tuple((Variable('name'), Variable('enabled'))))
    upact.add_input(atabl, Variable('name'))
    upact.add_output(tabl, Tuple((Variable('name'), Value('processed'))))
    upact.add_output(atabl, Variable('name'))
    n.add_transition(upact)

    enboil = Transition('Enable boiler', prior=1)
    enboil.add_input(atabl, Variable('name'))
    enboil.add_input(poll, Variable('d'))
    enboil.add_input(boien, Variable('old_state'))
    enboil.add_output(boien, Value(True))
    enboil.add_output(atabl, Variable('name'))
    enboil.add_output(bost, Value(True))
    n.add_transition(enboil)

    disboil = Transition('Disable boiler')
    disboil.add_input(poll, Variable('d'))
    disboil.add_input(boien, Variable('old_state'))
    disboil.add_output(boien, Value(False))
    disboil.add_output(bost, Value(False))
    n.add_transition(disboil)

    n.draw(f'nets_png/{name}.png')

    return n

def execute():
    boiler_log = boiler_logic('boiler_logic')
    execute_nets(boiler_log, sim_id='boiler-logic')

if __name__ == "__main__":
    execute()
