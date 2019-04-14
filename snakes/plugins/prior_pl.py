#!/bin/python3.7

import snakes.nets
import snakes.plugins

class Priority():

    def __init__(self, transition, prior):
        self.type = 'priority'
        self.transition = transition
        self.check_prior(prior)
        self.prior = 100 - prior

    def prepare(self):
        return

    def check_prior(self, prior):
        if hasattr(self, 'extension') and self.transition.extension is not None:
            raise AttributeError(f'Transition already has type {self.transition.extension.type}')
        if not isinstance(prior, int) or 0 < prior > 100 :
            raise AttributeError('Priority should be an int in 0-100')

    def check_and_fire(self, binding):
        if hasattr(self.transition, 'add_bindings'):
            self.transition.add_bindings(binding)

    def text_repr(self):
        if self.prior == 0:
            return ''
        else:
            return f'Prior: {100 - self.prior}'

@snakes.plugins.plugin("snakes.nets")
def extend(module):
    class Transition(module.Transition):

        def __init__(self, name, guard=None, **args):
            prior = args.pop('prior', None)
            module.Transition.__init__(self, name, guard, **args)

            if prior != None:
                self.extension = Priority(self, prior)

        def priority(self):
            if self.extension and self.extension.type == 'priority':
                return self.extension.prior
            else:
                return 0

        @staticmethod
        def draw_transition(trans, attr):
            attr['label'] = f"{trans.extension.text_repr()}\\n{attr['label']}"

    return Transition


