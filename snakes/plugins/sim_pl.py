import snakes.nets
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

        def add_simulator(self, simul):
            self.simul = simul
            self.simul.add_petri_net(self)
            self.mqtt_cl = self.simul.mqtt

        def send_tokens(self):
            output_ports = [port[1:] for port in self.ports if port[0] is 'output']
            for place, topic in output_ports:
                tokens = []
                if not place.tokens:
                    continue
                tokens = self.prepare_tokens(place.tokens)
                self.mqtt_cl.topic_publish(topic, tokens)
                place.empty()

        def prepare_tokens(self, tokens):
            result = []
            for token in tokens:
                if isinstance(token, (tuple, list, set)):
                    result.append(
                        f'{token.__class__.__name__}:{self.prepare_tokens(token)}')
                else:
                    result.append(f'{token.__class__.__name__}:{token}')
            return result

        def prepare(self):
            if self.ready:
                return
            for tr in self.transition():
                tr._add_parent_net(self)
                tr._add_simulator(self.simul)
                tr.prepare()
            self.ready = True

        def add_remote_output(self, place, target):
            if isinstance(place, str):
                place = self.place(place)
            self.ports.add(('output', place, target))

        def add_remote_input(self, place, target):
            if isinstance(place, str):
                place = self.place(place)
            self.ports.add(('input', place, target))

        def draw(self, filename, engine="dot", debug=False,
                    graph_attr=None, cluster_attr=None,
                    place_attr=None, trans_attr=None, arc_attr=None):

            module.PetriNet.draw(self, filename, engine="dot", debug=False,
                    graph_attr=None, cluster_attr=None,
                    place_attr=Place.draw_place, trans_attr=Transition.draw_transition, arc_attr=None)

    class Transition(module.Transition):
        @staticmethod
        def draw_transition(trans, attr):
            if trans.extension:
                attr['label'] = f"{trans.extension.text_repr()}\\n{attr['label']}"

    class Place(module.Place):
        SEPARATED = 1
        INPUT = 2
        OUTPUT = 3
        def __init__(self, name, tokens=[], check=None):
            self.state = Place.SEPARATED
            self.connected = None
            module.Place.__init__(self, name, tokens, check)

        def set_place_type(self, p_type, conneced):
            if self.state == self.SEPARATED:
                self.state = p_type
                self.connected = conneced
            elif self.state != p_type:
                raise ValueError("Place type is already set")

        @staticmethod
        def draw_place (place, attr) :
            if place.state == Place.SEPARATED:
                return
            elif place.state == Place.INPUT:
                attr['color'] = '#00FF00'
                attr['label'] = f"Listening on: {place.connected}\\n{attr['label']}"
            elif place.state == Place.OUTPUT:
                attr['color'] = '#FF0000'
                attr['label'] = f"Sending to: {place.connected}\\n{attr['label']}"

    return PetriNet, Place
