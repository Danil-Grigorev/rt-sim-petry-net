#!/bin/python3.7

import paho.mqtt.client as mqtt
from threading import RLock

def simulationFailure(simul, msg):
    simul.kill = True
    print(msg)
    simul.wake()

class Mqtt_client():

    def __init__(self, simul, brok_addr='127.0.0.1'):
        self.input_ports = {}
        self.output_ports = {}
        self.broker = brok_addr
        self.simul = simul
        self.nets = {}
        self.remote_nets = set()
        self.remote_requests = {}
        self.req_lock = RLock()
        self.pending_requests = []
        self.pending_req_cnt = 0
        self.client = None
        self.setup_client()

    def on_message(self, client, userdata, message):
        # print('***', self.simul.id, message.topic, message.payload.decode('utf-8'))
        data = self.parse_msg(message)
        if data['topic'] == 'control':
            self.serve_control(data)
        elif data['topic'] == 'private':
            self.serve_private(data)
        else:
            self.serve_port(data)

    def close(self):
        if self.client:
            self.client.loop_stop()

    def add_subscription(self, topic):
        if not self.client:
            raise Exception("Client was not configured")
        if isinstance(topic, (list, set)) and len(topic) == 2:
            topic_str = '{net}/{place}'.format(net=topic[0], place=topic[1])
        elif not isinstance(topic, str):
            raise TypeError(
                "Not an valuable topic format, must be str/list/set")
        else:
            topic_str = topic
        self.client.subscribe(topic_str, qos=2) # Subscribe with best qos

    def serve_control(self, message):
        '''
        Provides backend API processing for port setup
        '''
        if message['type'] == 'R':
            if message['target_net'] not in self.nets.keys():
                return
            net = self.nets[message['target_net']]
            net_places = {p.name: p for p in net.place()}
            if message['target_place'] not in net_places.keys():
                self.control_publish(
                    f"F, {message['payload']} - " +
                    f'Error: place "{message["target_place"]}"" is not found in net "{net.name}"')
            try:
                if message['action'] == 'set_input':
                    place = net_places[message['target_place']]
                    self.configure_internal_input_port(
                        net,
                        place)
                    place.set_place_type(place.INPUT)
                elif message['action'] == 'set_output':
                    place = net_places[message['target_place']]
                    self.configure_internal_output_port(
                        place,
                        message['source_topic'])
                    place.set_place_type(place.OUTPUT)
                else:
                    raise Exception(f'Unknown message action {message}')
            except:
                self.control_publish(
                    f"F, {message['payload']} - " +
                    "Error while serving message")
                return
            else:
                self.control_publish(f"S, {message['payload']}")
        elif message['type'] == 'U':
            if message['action'] == 'update_nets':
                if message['client_id'] == str(self.client._client_id):
                    return
            # Notify source to update it's list of remote nets
            self.remote_nets.update(message['nets'])
            new_net_list = f"U, update_nets, {message['client_id']}, {'&'.join(self.nets.keys())}"
            self.private_publish(message['client_id'], new_net_list)
            for net in message['nets']:
                if not net in self.remote_requests.keys():
                    continue
                self.remote_requests_pop(net)
        elif message['type'] == 'F':
            simulationFailure(
                self.simul, f"Failed to setup: {message['payload']}")
            self.close()
        elif message['type'] == 'S':
            if message['content'] not in self.pending_requests:
                return
            self.pending_requests.remove(message['content'])
            self.pending_req_cnt -= 1
            if self.pending_req_cnt == 0:
                self.simul.wake()

    def serve_port(self, message):
        net, place = message['topic'].split('/')
        if net not in self.nets.keys():
            return
        # print(f"Serving port {place.name} - {message['payload']}")
        place = self.input_ports[place]
        tokens = message['payload'].split('&')
        self.parse_tokens(place, tokens)
        self.simul.execute_net(net) # TODO: move to planned

    def parse_tokens(self, place, tokens):
        for tp, val in map(lambda x: x.split(':', 1), tokens):
            tk = self.parse_subtokens(tp, val)
            place.add(tk)

    def parse_subtokens(self, tp, value):
        tp = eval(tp) # Type casting
        if tp == tuple:
            parsed_tokens = []
            value = eval(value) # Converting string list to list
            for tp_v, val in map(lambda x: x.split(':'), value):
                tk = self.parse_subtokens(tp_v, val)
                parsed_tokens.append(tk)
            return tuple([tp(parsed_tokens)])
        elif tp == bool:
            return value == 'True'
        else:
            return tp(value)

    def serve_private(self, message):
        if message['type'] == 'U':
            if message['action'] == 'update_nets':
                self.remote_nets.update(message['nets'])
                for net in message['nets']:
                    if not net in self.remote_requests.keys():
                        continue
                    self.remote_requests_pop(net)

    def input_port_setup(self, net, trg_place, from_topic):
        print(net, trg_place, from_topic)
        if isinstance(from_topic, list):
            from_topic = '/'.join(from_topic)
        self.configure_internal_input_port(net, trg_place)
        self.configure_external_output_port(net, trg_place, from_topic)

    def configure_external_output_port(self, net, trg_place, from_topic):
        trg_topic = '{}/{}'.format(net.name, trg_place.name)
        net, place = from_topic.split('/')
        if not net in self.nets.keys():
            self.serve_output(from_topic, trg_topic, net)
            return
        net = self.nets[net]
        place = net.place(place)
        self.configure_internal_output_port(place, trg_topic)

    def configure_internal_input_port(self, net, place):
        if not place.name in self.input_ports.keys():
            self.input_ports[place.name] = place
        input_port_topic = '{}/{}'.format(net.name, place.name)
        self.add_subscription(input_port_topic)

    def output_port_setup(self, trg_place, to_topic):
        print('setting as output', trg_place.name)
        if isinstance(to_topic, list):
            to_topic = '/'.join(to_topic)
        self.configure_internal_output_port(trg_place, to_topic)
        self.configure_external_input_port(to_topic)

    def configure_external_input_port(self, target_port_topic):
        net, place = target_port_topic.split('/')
        if net not in self.nets.keys():
            self.serve_input(target_port_topic, net)
            return
        net = self.nets[net]
        place = net.place(place)
        self.configure_internal_input_port(net, place)

    def configure_internal_output_port(self, trg_place, to_topic):
        if trg_place not in self.output_ports.keys():
            self.output_ports[trg_place] = [to_topic]
        else:
            self.output_ports[trg_place].append(to_topic)

    def setup_client(self):
        self.client = mqtt.Client()
        self.client.on_message = self.on_message
        self.client.connect(self.broker)
        self.client.loop_start()
        self.client.subscribe('control', 2)

    def parse_msg(self, message):
        '''
        Parses message and returns a dictionary of it's values

        Control message syntax looks like:
            "TYPE ACTION PAYLOAD"
            TYPE -- message type, [RSFA]
                    R means request, S means success, F means failure,
            ACTION -- actions with selected place gathered from topic
            PAYLOAD --  actual message payload, source place name, etc.
        '''
        msg = {}
        p = message.payload.decode('utf-8')
        msg['payload'] = p
        msg['topic'] = message.topic
        if msg['topic'] == 'control':
            # msg['target_place'] = msg['topic'].split('/'[-1])
            msg['type'], msg['content'] = p.split(', ', 1)
            # print(self.net.name, 'received', p)
            if msg['type'] == 'R':
                msg['action'], target_topic, msg['source_topic'] = msg['content'].split(', ')
                msg['target_net'], msg['target_place'] = target_topic.split('/')
            elif msg['type'] == 'U':
                msg['action'], msg['client_id'], nets = msg['content'].split(', ')
                msg['nets'] = set(nets.split('&'))
            elif msg['type'] == 'S':
                _, msg['action'], msg['target_topic'], _ = msg['content'].split(', ')
            elif msg['type'] != 'F':
                simulationFailure(
                    self.simul,
                    f'Unknown message type for control message: {msg["type"]}')
                self.close()
        elif 'private' in msg['topic']:
            msg['topic'] = 'private'
            msg['type'], msg['content'] = p.split(', ', 1)
            if msg['type'] == 'U':
                msg['action'], msg['client_id'], nets = msg['content'].split(', ')
                msg['nets'] = set(nets.split('&'))
            else:
                simulationFailure(
                    self.simul,
                    f'Unknown message type for private message: {msg["type"]}')
                self.close()
        return msg

    def serve_input(self, target_port_topic, net):
        message = 'R, set_input, {}, /'.format(target_port_topic)
        if net in self.remote_nets:
            self.control_publish(message)
        else:
            self.update_remote_requests(net, message, 'control')

    def serve_output(self, target_port_topic, src_topic, net):
        message = 'R, set_output, {}, {}'.format(target_port_topic, src_topic)
        if net in self.remote_nets:
            self.control_publish(message)
        else:
            self.update_remote_requests(net, message, 'control')

    def update_remote_requests(self, net, message, topic):
        if topic != 'control' and self.simul.detached:
            return  # Skip the storage part
        message = [topic, message]
        if net in self.remote_requests.keys():
            self.remote_requests[net].append(message)
        else:
            self.remote_requests[net] = [message]

    def remote_requests_pop(self, net):
        remote_requests = self.remote_requests.pop(net)
        for msg in remote_requests:
            topic, message = msg
            if topic == 'control':
                self.control_publish(message)
            else:
                self.client.publish(topic, message)

    def control_publish(self, message):
        if message[0] == 'R':
            # with self.req_lock:
            self.pending_requests.append(message)
            self.pending_req_cnt += 1  # Waiting for ack and success message
        self.client.publish('control', message, 2)

    def private_publish(self, target, message):
        self.client.publish(f'private/{target}', message, 2)

    def topic_publish(self, topic, tokens):
        net, place = topic.split('/')
        if net in self.nets.keys(): # Net is in curent simulator
            net = self.nets[net]
            place = net.place(place)
            self.parse_tokens(place, tokens)
            self.simul.schedule([self.simul.execute_net, net], self.simul.NOW)
        elif net in self.remote_nets: # Net is in other simulator
            self.client.publish(topic, '&'.join(tokens), 2)
        else: # Net is not yet registered
            self.update_remote_requests(net, '&'.join(tokens), topic)
        # self.simul.schedule([self.topic_publish, topic], self.simul.INF)

    def configure(self):
        self.client.user_data_set(self.nets.keys())
        self.client._client_id = hash(str(self.nets.keys()))
        # Subscribe to private messages to the MQTT client, mostly of type Update
        self.client.subscribe(f'private/{self.client._client_id}', 2)
        for net in self.nets.values():
            for place in net.place():
                if place.state == place.SEPARATED:
                    continue
                elif place.state == place.INPUT:
                    for input_topic in place.inp_topics:
                        self.input_port_setup(net, place, input_topic)
                elif place.state == place.OUTPUT:
                    for output_topic in place.out_topics:
                        self.output_port_setup(place, output_topic)
        self.wait_net_ports()
        self.notify_others()

    def notify_others(self):
        net_list = '&'.join(self.nets.keys())
        net_list = f'U, update_nets, {self.client._client_id}, {net_list}'
        self.client.publish('control', net_list, 2)

    def wait_net_ports(self):
        for net in self.nets.values():
            net.prepare()
        if self.pending_req_cnt == 0:
            return
        with self.simul.wake_event:
            self.simul.wake_event.wait()
