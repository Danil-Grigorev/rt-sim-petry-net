#!/bin/python3.7

import snakes.nets
import snakes.plugins
from random import random
from math import isclose

class Prob():
    
    def __init__(self, transition, prob=None):
        
        self.type = 'probabilistic'
        self.transition = transition
        self.neighbours = {self.transition,}
        self.input_places = None

        self.prob = None
        if prob:
            self.set_probability(prob)

    def text_repr(self):
        if self.prob is None:
            raise ValueError(f'Probability was not set for {self.transition.name}')
        return f'P: {self.prob * 100}%'
    
    def add_neighbour(self, neighbour):
        if isinstance(neighbour, list):
            for n in neighbour:
                self.add_neighbour(n)
            return
        elif not isinstance(neighbour, snakes.nets.Transition):
            raise TypeError(
                f"Expected 'Transition' object, got {type(neighbour)}")
        if not neighbour.extension:
            neighbour.extension = Prob(neighbour)
        self.__copy_neighbours(neighbour)

    def set_probability(self, prob):
        if self.prob:
            raise AttributeError(f'Probability was already set on {self.prob}')
        if not isinstance(prob, (int, float)):
            raise TypeError('Expected a number for probability.')
        if not 0.0 <= prob <= 1.0:
            raise ValueError('Probability should be in 0-1')
        self.prob = prob

    def prepare(self):
        self.input_places = self.transition.input()
        self.__check_neighbours()
        self.__check_probabilities()

    def __check_neighbours(self):
        for tr in self.neighbours:
            self.__copy_neighbours(neighbour=tr)
            self.__check_places(neighbour=tr)
        if not self.neighbours:
            raise ValueError(
                f'Expected at least one neighbour for transition {self.transition.name}')
        
    def __copy_neighbours(self, neighbour):
        self.neighbours.add(neighbour)
        neighbour.extension.neighbours.update(self.neighbours)
        self.neighbours.update(neighbour.extension.neighbours)
        
    def __check_places(self, neighbour):
        if neighbour.input() != self.input_places:
            raise ValueError(
                f'Transition {neighbour.name} '
                f'has different set of places from {self.transition.name}')

    def __check_probabilities(self):
        calc_prob = 0.0
        unset_neighbours = []
        for nb in self.neighbours:
            if not nb.extension.prob:
                unset_neighbours.append(nb)
                continue
            calc_prob += nb.extension.prob
        if calc_prob > 1.0 or (isclose(calc_prob, 1.0, rel_tol=1e-3) and unset_neighbours):
            raise ValueError(
                f'Full probability {calc_prob} exeeds 1.0 for transitions: ['
                f'{", ".join([nb.name for nb in self.neighbours])}]'
            )
        elif not isclose(calc_prob, 1.0) and calc_prob < 1.0 and not unset_neighbours:
            raise ValueError(
                'Probability for transitions: ['
                f'{", ".join([nb.name for nb in self.neighbours])}] '
                f'{calc_prob} < 1.0'
            )
        if not unset_neighbours:
            return
        distributed_prob = (1.0 - calc_prob) / len(unset_neighbours)
        for nb in unset_neighbours:
            nb.extension.set_probability(distributed_prob)
        
    def check_and_fire(self, binding):
        prob = 0.0
        transitions = list(self.neighbours)
        print(transitions)
        for nb in transitions[:-1]:
            prob += nb.extension.prob
            if random() <= prob:
                nb.add_bindings(binding)
                return
        transitions[-1].add_bindings(binding)

class Timed():

    def __init__(self, transition, timeout):
        self.type = 'Timed'
        self.transition = transition
        self.simul = None
        self.scheduled = False
        self.timeout = timeout
        self.bindings = []
        self.ready = False
    
    def prepare(self):
        self.simul = self.transition.simul
    
    def text_repr(self):
        return f'T: {self.timeout}s'

    def plan(self):
        timeout = self.simul.cur_time() \
                - self.simul.start_time + self.timeout
        self.simul.schedule([self.unblock], timeout)

    def block(self):
        self.scheduled = True
        self.ready = False
            
    def unblock(self):
        self.scheduled = False
        self.ready = True
        for binding in self.bindings:
            self.transition.add_bindings(binding)
        if self.bindings:
            self.bindings = []
            self.simul.schedule(
                [self.simul.execute_net, self.transition.net], self.simul.NOW)
            # print(f'\tAdded net execution of {self.net.name} to {self.simul.scheduler.queue}')

    def check_and_fire(self, binding):
        if self.ready:
            self.transition.add_bindings(binding)
        elif not self.scheduled:
            self.block()
            self.plan()
            self.bindings.append(binding)
        


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
                tr._add_parent_net(self)
                tr._add_simulator(self.simul)
                tr.prepare()
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

        def draw(self, filename, engine="dot", debug=False,
                  graph_attr=None, cluster_attr=None,
                  place_attr=None, trans_attr=None, arc_attr=None):
            # ',net-with-colors.png',
            #    place_attr=draw_place, trans_attr=draw_transition
            
            module.PetriNet.draw(self, filename, engine="dot", debug=False,
                  graph_attr=None, cluster_attr=None,
                  place_attr=Place.draw_place, trans_attr=Transition.draw_transition, arc_attr=None)

    class Place(module.Place):
        SEPARATED = 1
        INPUT = 2
        OUTPUT = 3
        def __init__(self, name, tokens=[], check=None):
            self.state = Place.SEPARATED
            module.Place.__init__(self, name, tokens, check)
        
        @staticmethod
        def draw_place (place, attr) :
            pass
            # attr['label'] = place.name.upper()
            # attr['color'] = '#FF0000'

    class Transition(module.Transition):

        
        def __init__(self, name, guard=None, timeout=None, prob=None):
            if timeout and prob:
                raise AttributeError('Transition can be eather timed or probabilistic, not both')
            self.extension = None
            self.net = None
            self.simul = None
            module.Transition.__init__(self, name, guard)
            if timeout:
                self.extension = Timed(self, timeout)
            if prob:
                self.extension = Prob(self, prob)
        
        def _add_simulator(self, sim):
            self.simul = sim

        def _add_parent_net(self, net):
            self.net = net
        
        def prepare(self):
            if self.extension is not None:
                self.extension.prepare()
            
        def set_probability(self, prob):
            if not self.extension:
                self.extension = Prob(self)
            if self.extension and not isinstance(self.extension, Prob):
                raise AttributeError(
                    f'Transition "{self.name}" type is already set to "{self.type}"')
            self.extension.set_probability(prob)

        def add_neighbour_transition(self, neighbour):
            if self.extension is None:
                self.extension = Prob(self)
            elif not isinstance(self.extension, Prob):
                raise AttributeError(
                    f'Transition "{self.name}" already has a type')
            self.extension.add_neighbour(neighbour)
        
        def set_timeout(self, timeout):
            if not isinstance(timeout, (int, float)):
                raise TypeError(f'Timeout should be int or float, got {timeout}')
            if self.extension is None:
                self.extension = Timed(self, timeout)
            elif isinstance(self.extension, Timed):
                raise AttributeError(
                    'Timeout is already set for transition '
                    f'{self.name} on {self.extension.timeout}')
            else:
                raise AttributeError(
                    f'Transition {self.name} type is already set on '
                    f'"{self.extension.type}"')

        def add_bindings(self, binding):
            for place, label in self.output():
                place.add(label.flow(binding))

        def fire (self, binding) :
            if self.enabled(binding) :
                for place, label in self.input() :
                    place.remove(label.flow(binding))
                if self.extension:
                    # print('extension is firing')
                    self.extension.check_and_fire(binding)
                else:
                    self.add_bindings(binding)
            else :
                raise ValueError("transition not enabled for %s" % binding)

        @staticmethod
        def draw_transition(trans, attr):
            if trans.extension:
                attr['label'] = f"{trans.extension.text_repr()}\\n{attr['label']}"

    return PetriNet, Place, Transition


