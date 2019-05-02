#!/usr/bin/python3.7

from template import *
import random


def temp_sensor(name, expected):

    n = PetriNet(name)

    n.declare('import random')

    rand_id = random.randint(0, 10000)
    q_per_cels = 17.5
    exch_time = 30 # Timeout for temp loss/gain update
    heat_time = 5 # Timeout for heater output update
    Qgps = 0.34 # W/s
    Qlps = 0.2 # W/s
    n.declare(f'name = "{name}-{rand_id}"')
    n.declare(f'Qgps = float({Qgps}) # W/s')
    n.declare(f'Qlps = float({Qlps}) # W/s')
    n.declare(f'exch_time = float({exch_time})')
    n.declare(f'heat_time = float({heat_time})')

    temp_new = 12.
    temp_start = 0.

    it = Place('Input temp', [temp_new], check=tFloat)
    to = Place('Temperature outside', [temp_start], check=tFloat)
    ti = Place('Temperature inside', [temp_start], check=tFloat)
    tupdate = Place('Temperature updated', [], check=tFloat)
    texp = Place('Temperature expected', [expected], check=tFloat)
    hen = Place('Enable_heater', [], check=tTuple)
    hstate = Place('Heater state', [], check=tBoolean)
    heat_gen = Place('Heaters', [], check=tBlackToken)
    uout = Place('Update outside', [dot], check=tBlackToken)
    texgen = Place('Exchange gener', [dot], check=tBlackToken)
    twarm = Place('Outside warmer', [], check=tBoolean)
    qexch = Place('Q exchange', [], check=tFloat)
    qgain = Place('Q gain', [], check=tFloat)
    q1c = Place('Q per C', [q_per_cels], check=tFloat)
    deltat = Place('deltaT', [], check=tFloat)
    n.add_place(hstate)
    n.add_place(uout)
    n.add_place(qgain)
    n.add_place(heat_gen)
    n.add_place(tupdate)
    n.add_place(deltat)
    n.add_place(q1c)
    n.add_place(qexch)
    n.add_place(twarm)
    n.add_place(texgen)
    n.add_place(to)
    n.add_place(it)
    n.add_place(ti)
    n.add_place(hen)
    n.add_place(texp)

    temp_gain = Transition(
        'Temperature gain',
        guard=Expression('Twarm == True'),
        timeout=exch_time)
    temp_gain.add_output(uout, Value(dot))
    temp_gain.add_input(texgen, Variable('d'))
    temp_gain.add_output(texgen, Variable('d'))
    temp_gain.add_input(twarm, Variable('Twarm'))
    temp_gain.add_output(qexch, Expression('Qlps*exch_time'))
    n.add_transition(temp_gain)

    temp_loss = Transition(
        'Temperature loss',
        guard=Expression('Twarm == False'),
        timeout=exch_time)
    temp_loss.add_output(uout, Value(dot))
    temp_loss.add_input(texgen, Variable('d'))
    temp_loss.add_output(texgen, Variable('d'))
    temp_loss.add_input(twarm, Variable('Twarm'))
    temp_loss.add_output(qexch, Expression('-Qlps*exch_time'))
    n.add_transition(temp_loss)

    updated_out = Transition('Updated outside')
    updated_out.add_input(it, Variable('t'))
    updated_out.add_input(to, Variable('tlast'))
    updated_out.add_output(to, Variable('t'))
    n.add_transition(updated_out)

    hswitch = Transition('Heater switch', timeout=heat_time)
    hswitch.add_output(hstate, Expression('Tcurr < Texp'))
    hswitch.add_input(ti, Variable('Tcurr'))
    hswitch.add_output(ti, Variable('Tcurr'))
    hswitch.add_input(texp, Variable('Texp'))
    hswitch.add_output(texp, Variable('Texp'))
    hswitch.add_output(hen, Tuple((Expression('name'), Expression('Tcurr < Texp'))))
    n.add_transition(hswitch)

    temp_exchange = Transition('Temperature exchange')
    temp_exchange.add_input(q1c, Variable('Q1c'))
    temp_exchange.add_output(q1c, Variable('Q1c'))
    temp_exchange.add_input(qexch, Variable('Qex'))
    temp_exchange.add_output(deltat, Expression('Qex/Q1c'))
    n.add_transition(temp_exchange)

    heater_gain = Transition('Heater gain')
    heater_gain.add_input(qgain, Variable('Qg'))
    heater_gain.add_input(q1c, Variable('q1c'))
    heater_gain.add_output(q1c, Variable('q1c'))
    heater_gain.add_output(deltat, Expression('Qg/q1c'))
    n.add_transition(heater_gain)

    temp_update = Transition('Temperature update')
    temp_update.add_input(deltat, Variable('deltaT'))
    temp_update.add_output(tupdate, Expression('Tins+deltaT'))
    temp_update.add_input(ti, Variable('Tins'))
    temp_update.add_output(ti, Expression('Tins+deltaT'))
    n.add_transition(temp_update)

    comp_outside = Transition('Compare outside')
    comp_outside.add_input(uout, Variable('d'))
    comp_outside.add_input(to, Variable('Tout'))
    comp_outside.add_output(to, Variable('Tout'))
    comp_outside.add_input(ti, Variable('Tin'))
    comp_outside.add_output(ti, Variable('Tin'))
    comp_outside.add_output(twarm, Expression('Tin < Tout'))
    n.add_transition(comp_outside)

    heating = Transition('Heating', timeout=heat_time)
    heating.add_input(heat_gen, Variable('d'))
    heating.add_output(qgain, Expression('Qgps*heat_time'))
    n.add_transition(heating)

    heater_enable = Transition(
        'Start heater',
        guard=Expression('Hen == True'))
    heater_enable.add_input(hstate, Variable('Hen'))
    heater_enable.add_output(heat_gen, Value(dot))
    n.add_transition(heater_enable)

    stop_dump = Transition(
        'Dump stop',
        guard=Expression('Hen == False')
    )
    stop_dump.add_input(hstate, Variable('Hen'))
    n.add_transition(stop_dump)


    n.add_remote_input(it, 'temp_gen/Measurement')
    n.add_remote_output(hen, 'boiler_logic/Sensory_input')
    n.add_remote_output(tupdate, 'TODO/TODO')

    n.draw(f'nets_png/{name}.png')

    return n


def execute():
    sens = temp_sensor('temp_sens', 21.0)
    execute_nets(sens)


if __name__ == "__main__":
    execute()
