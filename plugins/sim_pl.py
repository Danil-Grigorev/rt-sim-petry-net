import snakes.nets
import snakes.plugins

@snakes.plugins.plugin("snakes.nets")
def extend(module):
    class PetriNet(module.PetriNet):
        def __init__(self, name, simul=None):
            self.mqtt_cl = None
            self.simul = simul
            self.ready = False
            module.PetriNet.__init__(self, name)

        def add_simulator(self, simul):
            self.simul = simul
            self.simul.add_petri_net(self)
            self.mqtt_cl = self.simul.mqtt
            simul.draw_net(self)

        def send_tokens(self):
            output_ports = [
                place for place in self.place() if place.state == Place.OUTPUT]
            for place in output_ports:
                tokens = []
                if not place.tokens:
                    continue
                tokens = self.prepare_tokens(place.tokens)
                for topic in place.out_topics:
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
            place.set_place_type(place.OUTPUT)
            place.add_output_topic(target)

        def add_remote_input(self, place, target):
            if isinstance(place, str):
                place = self.place(place)
            place.set_place_type(place.INPUT)
            place.add_input_topic(target)

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
            self.inp_topics = []
            self.out_topics = []
            module.Place.__init__(self, name, tokens, check)

        def set_place_type(self, p_type):
            if self.state == self.SEPARATED:
                self.state = p_type
            elif self.state != p_type:
                print(self.name, self.state, p_type)
                raise ValueError("Place type is already set")

        def add_input_topic(self, in_topic):
            if in_topic not in self.inp_topics:
                self.inp_topics.append(in_topic)

        def add_output_topic(self, out_topic):
            if out_topic not in self.out_topics:
                self.out_topics.append(out_topic)

        @staticmethod
        def draw_place (place, attr) :
            if place.state == Place.SEPARATED:
                return
            elif place.state == Place.INPUT:
                attr['color'] = '#00FF00'
                attr['label'] = f"Listening on: {', '.join(place.inp_topics)}\\n{attr['label']}"
            elif place.state == Place.OUTPUT:
                attr['color'] = '#FF0000'
                attr['label'] = f"Sending to: {', '.join(place.out_topics)}\\n{attr['label']}"

    return PetriNet, Place
