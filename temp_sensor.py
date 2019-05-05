#!/usr/bin/python3.7

from template import *


def room_sens(room_name, exp_temp):
    name = f'{room_name}-sensors'
    n = PetriNet(name)
    n.declare(f'name = "{name}"')

    table_up = Place('Table update', [], check=tFloat)
    exp_t = Place('Expected temperature', [exp_temp], check=tFloat)
    temp_ins = Place('Temperature inside', [], check=tFloat)
    val_st = Place('Valve state', [], check=tTuple)
    n.add_place(table_up)
    n.add_place(exp_t)
    n.add_place(temp_ins)
    n.add_place(val_st)

    h_dis = Transition('Heater disable', guard=Expression('Texp <= Tcurr'))
    h_dis.add_output(val_st, Tuple([Expression('name'), Value(False)]))
    h_dis.add_input(temp_ins, Variable('Tcurr'))
    h_dis.add_input(exp_t, Variable('Texp'))
    h_dis.add_output(exp_t, Variable('Texp'))
    n.add_transition(h_dis)

    h_en = Transition('Heater enable', guard=Expression('Texp > Tcurr'))
    h_en.add_output(val_st, Tuple([Expression('name'), Value(True)]))
    h_en.add_input(temp_ins, Variable('Tcurr'))
    h_en.add_input(exp_t, Variable('Texp'))
    h_en.add_output(exp_t, Variable('Texp'))
    n.add_transition(h_en)

    up_exp = Transition('Update expected', prior=1)
    up_exp.add_input(table_up, Variable('Tnew'))
    up_exp.add_input(exp_t, Variable('Told'))
    up_exp.add_output(exp_t, Variable('Tnew'))
    n.add_transition(up_exp)

    n.add_remote_input(
        temp_ins, f'{room_name}-temperature-updater/Inside update')
    n.add_remote_input(table_up, f'{room_name}-timetable/Temperature update')
    n.add_remote_output(val_st, 'boiler-logic/Sensory input')
    return n

def room_outside_exchange(room_name, q_lps, exch_time):
    name = f'{room_name}-outside-exchange'
    n = PetriNet(name)

    n.declare(f'name = "{name}"')
    n.declare(f'q_lps = float({q_lps}) # W/s')
    n.declare(f'exch_time = float({exch_time})')

    out_up = Place('Outside update', [], check=tFloat)
    ins_up = Place('Inside temp update', [], check=tFloat)
    to = Place('Temperature outside', [0.0], check=tFloat)
    ti = Place('Temperature inside', [0.0], check=tFloat)
    uout = Place('Update outside', [dot], check=tBlackToken)
    twarm = Place('Outside warmer', [], check=tBoolean)
    qexch = Place('Q exchange', [], check=tFloat)
    n.add_place(ins_up)
    n.add_place(uout)
    n.add_place(qexch)
    n.add_place(twarm)
    n.add_place(to)
    n.add_place(out_up)
    n.add_place(ti)

    temp_gain = Transition(
        'Temperature gain',
        guard=Expression('Twarm == True'),
        timeout=exch_time)
    temp_gain.add_output(uout, Value(dot))
    temp_gain.add_input(twarm, Variable('Twarm'))
    temp_gain.add_output(qexch, Expression('q_lps*exch_time'))
    n.add_transition(temp_gain)

    temp_loss = Transition(
        'Temperature loss',
        guard=Expression('Twarm == False'),
        timeout=exch_time)
    temp_loss.add_output(uout, Value(dot))
    temp_loss.add_input(twarm, Variable('Twarm'))
    temp_loss.add_output(qexch, Expression('-q_lps*exch_time'))
    n.add_transition(temp_loss)

    updated_out = Transition('Updated outside')
    updated_out.add_input(out_up, Variable('Tnew'))
    updated_out.add_input(to, Variable('Told'))
    updated_out.add_output(to, Variable('Tnew'))
    n.add_transition(updated_out)

    updated_in = Transition('Updated inside')
    updated_in.add_input(ins_up, Variable('Tnew'))
    updated_in.add_input(ti, Variable('Told'))
    updated_in.add_output(ti, Variable('Tnew'))
    n.add_transition(updated_in)

    comp_outside = Transition('Compare outside')
    comp_outside.add_input(uout, Variable('d'))
    comp_outside.add_input(to, Variable('Tout'))
    comp_outside.add_output(to, Variable('Tout'))
    comp_outside.add_input(ti, Variable('Tin'))
    comp_outside.add_output(ti, Variable('Tin'))
    comp_outside.add_output(twarm, Expression('Tin < Tout'))
    n.add_transition(comp_outside)

    n.add_remote_output(qexch, f'{room_name}-temperature-updater/Q change')
    n.add_remote_input(out_up, 'weather-generator/Measurement')

    return n


def room_temp_update(room_name, qpc, starting_temp):

    name = f'{room_name}-temperature-updater'
    n = PetriNet(name)

    n.declare(f'name = "{name}"')

    ti = Place('Temperature inside', [starting_temp], check=tFloat)
    in_up = Place('Inside update', [], check=tFloat)
    qch = Place('Q change', [], check=tFloat)
    qpc = Place('Q per C', [qpc], check=tFloat)
    deltat = Place('deltaT', [], check=tFloat)
    n.add_place(in_up)
    n.add_place(deltat)
    n.add_place(qpc)
    n.add_place(qch)
    n.add_place(ti)

    temp_ch = Transition('Temperature change')
    temp_ch.add_input(qch, Variable('Qch'))
    temp_ch.add_input(qpc, Variable('Q1c'))
    temp_ch.add_output(qpc, Variable('Q1c'))
    temp_ch.add_output(deltat, Expression('Qch/Q1c'))
    n.add_transition(temp_ch)

    upd_ins = Transition('Update inside')
    upd_ins.add_input(ti, Variable('T'))
    upd_ins.add_input(deltat, Variable('dT'))
    upd_ins.add_output(ti, Expression('T + dT'))
    upd_ins.add_output(in_up, Expression('T + dT'))
    n.add_transition(upd_ins)

    n.add_remote_output(
        in_up, f'{room_name}-outside-exchange/Inside temp update')

    return n


def room_heating(room_name, q_gps, heat_time):
    name = f'{room_name}-heating'
    n = PetriNet(name)

    n.declare(f'name = "{name}"')
    n.declare(f'q_gps = float({q_gps}) # W/s')
    n.declare(f'heat_time = float({heat_time})')

    vupd = Place('Valve update', [], check=tTuple)
    vstate = Place('Valve state', [False], check=tBoolean)
    h_upd = Place('Heater update', [], check=tBoolean)
    hstate = Place('Heater state', [False], check=tBoolean)
    qgain = Place('Q gain', [], check=tFloat)
    n.add_place(vupd)
    n.add_place(vstate)
    n.add_place(hstate)
    n.add_place(qgain)
    n.add_place(h_upd)

    upd = Transition('Update', prior=1)
    upd.add_input(h_upd, Variable('Hst_new'))
    upd.add_input(hstate, Variable('Hst_old'))
    upd.add_output(hstate, Variable('Hst_new'))
    n.add_transition(upd)

    heating = Transition('Heating', guard=Expression('Hst == True and Vstate == True'), timeout=heat_time)
    heating.add_input(hstate, Variable('Hst'))
    heating.add_output(hstate, Variable('Hst'))
    heating.add_input(vstate, Variable('Vstate'))
    heating.add_output(vstate, Variable('Vstate'))
    heating.add_output(qgain, Expression('q_gps*heat_time'))
    n.add_transition(heating)

    valve_upd = Transition('Update state', prior=1)
    valve_upd.add_input(vstate, Variable('Vst_old'))
    valve_upd.add_input(vupd, Tuple([Variable('name'), Variable('Vst_new')]))
    valve_upd.add_output(vstate, Variable('Vst_new'))
    n.add_transition(valve_upd)

    n.add_remote_output(qgain, f'{room_name}-temperature-updater/Q change')
    n.add_remote_input(h_upd, 'boiler-logic/Boiler state')
    n.add_remote_input(vupd, f'{room_name}-sensors/Valve state')

    return n


def execute(rooms=None):
    nets = []

    if rooms is None:
        rooms = {
            'kitchen': {
                'qpc': 17.5,
                'q_gps': 0.34,  # W/s
                'q_lps': 0.2,  # W/s
                'heat_time': 5,  # Timeout for heater output update
                'exch_time': 30, # Timeout for temp loss/gain update
                'exp_temp': 20.0,
                'starting_temp': 18.0
            },
            'dining_room': {
                'qpc': 24.0,
                'q_gps': 0.5,  # W/s
                'q_lps': 0.4,  # W/s
                'heat_time': 5,  # Timeout for heater output update
                'exch_time': 30,  # Timeout for temp loss/gain update
                'exp_temp': 19.0,
                'starting_temp': 18.0
            },
            'storeroom': {
                'qpc': 24.0,
                'q_gps': 0.5,  # W/s
                'q_lps': 0.4,  # W/s
                'heat_time': 5,  # Timeout for heater output update
                'exch_time': 30,  # Timeout for temp loss/gain update
                'exp_temp': 15.0,
                'starting_temp': 5.0
            }
        }
    for room in rooms:
        args = rooms[room]
        nets.append(room_heating(room, args['q_gps'], args['heat_time']))
        nets.append(room_temp_update(room, args['qpc'], args['starting_temp']))
        nets.append(room_outside_exchange(room, args['q_lps'], args['exch_time']))
        nets.append(room_sens(room, args['exp_temp']))

    execute_nets(nets, sim_id='room-simulation')


if __name__ == "__main__":
    execute()
