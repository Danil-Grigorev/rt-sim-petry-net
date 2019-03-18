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
                return
            self.mqtt_cl.configure(self.ports)
            for tr in self.transition():
                tr.add_parent_net(self)
                tr.add_simulator(self.simul)
            self.ready = True

        def add_remote_output(self, place, target):
            self.ports.add(('output', place, target))

        def add_remote_input(self, place, target):
            self.ports.add(('input', place, target))

        def plan_execute(self):
            if self.simul is None:
                raise RuntimeError('Not a simulation entity')
            # print(f'Planning execution for {self.name}')
            self.simul.schedule([self.simul.execute_net, self], self.simul.INF)

        def execute(self):
            if self.simul is None:
                raise RuntimeError('Not a simulation entity')
            # print(f'updating execution time for {self.name}')
            self.simul.update_time([self.simul.execute_net, self], self.simul.NOW)

    class Place(module.Place):
        SEPARATED = 1
        INPUT = 2
        OUTPUT = 3
        def __init__(self, name, tokens=[], check=None):
            self.state = Place.SEPARATED
            module.Place.__init__(self, name, tokens, check)

    class Transition(module.Transition):
        def __init__(self, name, guard=None, timeout=None):
            self.timeout = timeout
            self.simul = None
            self.scheduled = False
            self.ready = False
            self.bindings = []
            self.net = None
            module.Transition.__init__(self, name, guard)
        
        def add_simulator(self, sim):
            self.simul = sim

        def add_parent_net(self, net):
            self.net = net

        def plan(self):
            timeout = self.simul.cur_time() - self.simul.start_time + self.timeout
            # print(f'{self.simul.cur_time()} - {self.simul.start_time} + {self.timeout}')
            # print(f"Planning execution at {timeout}")
            self.simul.schedule([self.unblock], timeout)

        def block(self):
            self.scheduled = True
            self.ready = False
                
        def unblock(self):
            self.scheduled = False
            self.ready = True
            for binding in self.bindings:
                self.add_bindings(binding)
            if self.bindings:
                self.bindings = []
                self.simul.schedule(
                    [self.simul.execute_net, self.net], self.simul.NOW)
                # print(f'\tAdded net execution of {self.net.name} to {self.simul.scheduler.queue}')

        def add_bindings(self, binding):
            for place, label in self.output() :
                place.add(label.flow(binding))
        
        def fire (self, binding) :
            if self.enabled(binding) :
                for place, label in self.input() :
                    place.remove(label.flow(binding))
                if not self.timeout or self.ready:
                    self.add_bindings(binding)
                elif not self.scheduled:
                    self.block()
                    self.plan()
                    self.bindings.append(binding)
            else :
                raise ValueError("transition not enabled for %s" % binding)

    return PetriNet, Place, Transition


