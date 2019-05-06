#!/usr/bin/python3
import inspect
from template import *

nets = []

def temp_placement(Tmin, Tmax, k):
    """
        Sample function for Petri net global declaration.
        Creates a temperature value between Tmin and Tmax values
        by mapping on cos function.

        k -- point on the graph
        Tmin -- minimum expected temperature during the day
        Tmax -- maximum expected temperature
    """
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
    day_len = 24*60*60
    T = day_len/samples  # Perioda zmen teploty
    # Citac pro generator
    k = samples * 16 / 24  # Day starts at 16:00 - warmest time
    T = T / speedup # Applying simulation speed control

    n.declare('from math import cos, pi')
    n.declare('import time, random')
    n.declare('from datetime import timedelta')
    n.declare('random.seed(time.time)')
    n.declare('from random import random as r')
    n.declare(f'f = {samples}')
    n.declare(inspect.getsource(temp_placement))
    temp_pl = Place('Temp_placement', [(low, high)], check=tTuple)
    gen = Place('Generator', [int(k)], check=tInteger)
    gen_k = Place('Generator_k', [], check=tInteger)
    tm = Place('Current time', [''], check=tString)
    tupd = Place('Time update', [], check=tFloat)
    traw = Place('Temperature_raw', [], check=tFloat)
    meas = Place('Measurement', [0.], check=tFloat)
    n.add_place(tupd)
    n.add_place(tm)
    n.add_place(gen)
    n.add_place(temp_pl)
    n.add_place(gen_k)
    n.add_place(traw)
    n.add_place(meas)

    takt = Transition('takt', timeout=T)
    takt.add_input(gen, Variable('k'))
    takt.add_output(gen, Expression('(1 + k) % f'))
    takt.add_output(gen_k, Variable('k'))
    takt.add_output(tm, Expression(f'str(timedelta(seconds=(k * {T * speedup})))')) # Updating current time
    takt.add_input(tm, Variable('Tm_old'))
    takt.add_output(tupd, Expression(f'k * {T * speedup}')) # Senting time to port
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

    return n

def room_timetable(room_name, timetable):
    """
    room_name -- Name of room, timetable made for
    timetable should look like this:
        [
            (hour, minute, temperature),
            ...
        ]
    """
    n = PetriNet(f'{room_name}-timetable')

    time_up = Place('Time update', [], check=tFloat) # Input
    exp_temp = Place('Expected temperature', [0.0], check=tFloat)
    new_exp = Place('Expected update', [], check=tFloat)
    temp_up = Place('Temperature update', [], check=tFloat) # Output
    n.add_place(time_up)
    n.add_place(temp_up)
    n.add_place(new_exp)
    n.add_place(exp_temp)

    n.add_remote_input(time_up, 'weather-generator/Time update')
    n.add_remote_output(temp_up, f'{room_name}-sensors/Table update')

    skip_tmp = Transition('Skip change', guard=Expression('Tnew == Told'), prior=1)
    skip_tmp.add_input(new_exp, Variable('Tnew'))
    skip_tmp.add_input(exp_temp, Variable('Told'))
    skip_tmp.add_output(exp_temp, Variable('Told'))
    n.add_transition(skip_tmp)

    update_tmp = Transition('Update temperature')
    update_tmp.add_input(new_exp, Variable('Tnew'))
    update_tmp.add_input(exp_temp, Variable('Told'))
    update_tmp.add_output(exp_temp, Variable('Tnew'))
    update_tmp.add_output(temp_up, Variable('Tnew'))
    n.add_transition(update_tmp)

    timetable.sort(key=lambda x: x[1]) # Sort by minutes
    timetable.sort(key=lambda x: x[0]) # Sort by hours
    if len(timetable) == 1: # Only one time specified
        hour, minute, temp = timetable[0]

        tr = Transition(f'Enable-all-day')
        tr.add_input(time_up, Variable('time_now'))
        tr.add_output(new_exp, Value(temp))
        n.add_transition(tr)
        return n

    for hour, minute, temp in timetable:
        p = Place(f'Time-{hour}:{minute}', [hour * 3600 + minute * 60])
        n.add_place(p)
    for item in range(len(timetable) - 1):
        add_net_entry(n,
            en_prev=timetable[item],
            en_next=timetable[item+1])  # Reading next table entry
    add_net_entry(n, en_next=timetable[0], temp=timetable[-1][2])
    add_net_entry(n, en_prev=timetable[-1])
    return n

def add_net_entry(n, en_prev=None, en_next=None, temp=None):
    time_up = n.place('Time update')
    new_exp = n.place('Expected update')
    assert en_next is not None or en_prev is not None
    if en_prev is None:
        assert temp is not None
        hour_n, min_n, _ = en_next # Reading first table entry
        p_next = n.place(f'Time-{hour_n}:{min_n}')

        calc_time = Expression(
            f'time_now <= time_next')
        tr = Transition(f'Enable: Before {hour_n}:{min_n}', guard=calc_time)
        tr.add_input(time_up, Variable('time_now'))
        tr.add_input(p_next, Variable('time_next'))
        tr.add_output(p_next, Variable('time_next'))
        tr.add_output(new_exp, Value(temp))
        n.add_transition(tr)
    elif en_next is None:
        hour_pr, min_pr, temp = en_prev # Reading last table entry
        p_next = n.place(f'Time-{hour_pr}:{min_pr}')

        calc_time = Expression(
            f'time_now > time_prev')
        tr = Transition(f'Enable: After {hour_pr}:{min_pr}', guard=calc_time)
        tr.add_input(time_up, Variable('time_now'))
        tr.add_input(p_next, Variable('time_prev'))
        tr.add_output(p_next, Variable('time_prev'))
        tr.add_output(new_exp, Value(temp))
        n.add_transition(tr)
    else:
        hour_pr, min_pr, temp = en_prev  # Reading last table entry
        hour_n, min_n, _ = en_next # Reading next table entry
        p_next = n.place(f'Time-{hour_n}:{min_n}')
        p_prev = n.place(f'Time-{hour_pr}:{min_pr}')
        # Time should be between time values of both table entries
        calc_time = Expression(
            f'time_prev < time_now <= time_next')
        tr = Transition(
            f'Enable: {hour_pr}:{min_pr}--{hour_n}:{min_n}', guard=calc_time)
        tr.add_input(time_up, Variable('time_now'))
        tr.add_input(p_prev, Variable('time_prev'))
        tr.add_output(p_prev, Variable('time_prev'))
        tr.add_input(p_next, Variable('time_next'))
        tr.add_output(p_next, Variable('time_next'))
        tr.add_output(new_exp, Value(temp))
        n.add_transition(tr)


def execute():
    timetable = {
        'kitchen': [
            (23, 00, 19.0),
            (6, 00, 22.0),
            (10, 00, 20.0),
            (19, 00, 21.0)
        ],
        'dining_room': [
            (23, 00, 18.0),
            (6, 30, 22.0),
            (10, 00, 19.0),
            (17, 00, 21.0)
        ]
    }
    temp_gen = temp_generator(
        'weather-generator', low=5, high=18, samples=100, speedup=100)
    nets.append(temp_gen)
    for room in timetable:
        nets.append(room_timetable(room, timetable[room]))
    execute_nets(nets, sim_id='Surroundings-simulation')

if __name__ == '__main__':
    execute()
