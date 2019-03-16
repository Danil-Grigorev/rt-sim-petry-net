#!/bin/python3.7

import snakes.plugins

@snakes.plugins.plugin("snakes.nets")
def extend(module):
    class PetriNet(module.PetriNet):
        def __init__(self, name, simul=None):
            self.mqtt_cl = None
            self.simul = simul
            self.ready = False
            self.ports = set()
            module.PetriNet.__init__(self, name)

        def add_mqtt_client(self, mqtt):
            if self.mqtt_cl is not None:
                return
            self.mqtt_cl = mqtt
            self.mqtt_cl.setup()

        def add_simulator(self, simul):
            self.simul = simul
            self.simul.add_petri_net(self)

        def send_tokens(self):
            self.mqtt_cl.send_tokens()

        def prepare(self):
            if self.ready:
                return True
            self.mqtt_cl.configure(self.ports)
            return False

        def add_remote_output(self, place, target):
            self.ports.add(('output', place, target))

        def add_remote_input(self, place, target):
            self.ports.add(('input', place, target))

        def plan_execute(self):
            if self.simul is None:
                raise RuntimeError('Not a simulation entity')
            print(f'Planning execution for {self.name}')
            self.simul.schedule([self.simul.execute_net, self.name], self.simul.INF)

        def execute(self):
            if self.simul is None:
                raise RuntimeError('Not a simulation entity')
            print(f'updating execution time for {self.name}')
            self.simul.update_time([self.simul.execute_net, self.name], self.simul.NOW)

    class Place(module.Place):
        SEPARATED = 1
        INPUT = 2
        OUTPUT = 3
        def __init__(self, name, tokens=[], check=None):
            self.state = Place.SEPARATED
            module.Place.__init__(self, name, tokens, check)

    class Transition(module.Transition):
        def __init__(self, name, guard=None, timeout=None, simul=None):
            self.timeout = timeout
            self.simul = None
            self.scheduled = False
            self.ready = False
            module.Transition.__init__(self, name, guard)
        
        def add_simulator(self, sim):
            self.simul = sim

        def plan(self, net):
            if self.timeout and self.scheduled:
                self.simul.schedule([self.unblock, net], self.timeout)

        def block(self):
            if self.timeout and not self.scheduled:
                self.scheduled = True
                self.ready = False
                
        def unblock(self, net):
            if self.timeout and self.scheduled:
                self.scheduled = False
                self.ready = True
                self.simul.schedule(
                    [self.simul.execute_net, net], self.simul.NOW)

        def execute(self, net):
            result = module.Transition.modes(self)
            if not self.timeout or self.ready:
                self.fire(result[0])
            elif not self.scheduled:
                self.block()
                self.plan(net)

    return PetriNet, Place


