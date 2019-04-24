#!/bin/python3.7

import snakes.nets
import snakes.plugins
from time import time
from random import random, seed
from math import isclose


class Prob():
    seed(time)

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
        for nb in transitions[:-1]:
            prob += nb.extension.prob
            if random() <= prob:
                nb.add_bindings(binding)
                return
        transitions[-1].add_bindings(binding)


@snakes.plugins.plugin("snakes.nets")
def extend(module):
    class Transition(module.Transition):

        def __init__(self, name, guard=None, **args):
            prob = args.pop('prob', None)
            self.extension = None
            self.net = None
            self.simul = None
            module.Transition.__init__(self, name, guard, **args)
            if prob != None:
                if self.extension is not None:
                    raise AttributeError(
                        f'Transition "{name}" type is already set to {self.extension.__dict__.keys()}')
                self.extension = Prob(self, prob)

        def _add_simulator(self, sim):
            self.simul = sim

        def _add_parent_net(self, net):
            self.net = net

        def prepare(self):
            in_out_places = self.input() + self.output()
            for _, label in in_out_places:
                if hasattr(label, "globals"):
                    label.globals.attach(self.net.globals)
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

    return Transition
