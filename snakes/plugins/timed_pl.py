#!/bin/python3.7

import snakes.nets
import snakes.plugins

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
        desc = f'Wait: {self.timeout}s'
        if self.bindings:
            desc += f'\n{self.bindings}'
        return desc

    def plan(self):
        timeout = self.simul.cur_time() \
                - self.simul.start_time + self.timeout
        self.simul.schedule([self.unblock], timeout)

    def unblock(self):
        self.scheduled = False
        self.ready = True
        self.transition.add_bindings(self.bindings.pop(0))
        self.simul.schedule(
            [self.simul.execute_net, self.transition.net], self.simul.NOW)
        # print(f'\tAdded net execution of {self.net.name} to {self.simul.scheduler.queue}')

    def check_and_fire(self, binding):
        self.plan()
        self.bindings.append(binding)


@snakes.plugins.plugin("snakes.nets")
def extend(module):
    class Transition(module.Transition):

        def __init__(self, name, guard=None, **args):
            timeout = args.pop('timeout', None)
            self.extension = None
            self.net = None
            self.simul = None
            module.Transition.__init__(self, name, guard, **args)
            if timeout:
                if self.extension is not None:
                    raise AttributeError(
                        f'Transition "{name}" type is already set to {self.extension}')
                self.extension = Timed(self, timeout)

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

    return Transition


