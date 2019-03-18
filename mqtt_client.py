#!/bin/python2.7

import paho.mqtt.client as mqtt

class Mqtt_client():
    
    def __init__(self, net, brock_addr='127.0.0.1'):
        self._input_ports = {} 
        self._output_ports = {}
        self._brocker = brock_addr
        self.net = net
        self._client = None
        self._pending_requests = []
        self._pending_req_cnt = 0

    def on_message(self, client, userdata, message):
        # print('***', self.net.name, message.topic, message.payload.decode('utf-8'))
        data = self.__parse_msg(message)
        if data['topic'] == 'control':
            self.__serve_control(data)
        else:
            self.__serve_port(data)
            
    def close(self):
        if self._client:
            self._client.loop_stop()
    
    def add_subscription(self, topic):
        if not self._client:
            raise Exception("Client was not configured")
        if isinstance(topic, (list, set)) and len(topic) == 2:
            topic_str = '{net}/{place}'.format(net=topic[0], place=topic[1])
        elif not isinstance(topic, str):
            raise TypeError(
                "Not an valuable topic format, must be str/list/set")
        else:
            topic_str = topic
        # print(self.net.name, "is subscribed to", topic_str)
        self._client.subscribe(topic_str, 2)

    def __input_port_setup(self, trg_place, from_topic):
        if not isinstance(from_topic, str):
            from_topic = '/'.join(from_topic)
        self.__configure_internal_input_port(trg_place)
        self.__configure_external_ouput_port(trg_place, from_topic)

    def __configure_external_ouput_port(self, trg_place, from_topic):
        src_topic = '{}/{}'.format(self.net.name, trg_place.name)
        self.__serve_output(from_topic, src_topic)

    def __configure_internal_input_port(self, place): # DONE
        self.__set_place_type(place, place.INPUT)
        self._input_ports[place.name] = place
        input_port_topic = '{}/{}'.format(self.net.name, place.name)
        self.add_subscription(input_port_topic)
        # print(f'{self.net.name}/{place.name} is an input')

    def __output_port_setup(self, trg_place, to_topic):
        if not isinstance(to_topic, str):
            to_topic = '/'.join(to_topic)
        self.__configure_internal_output_port(trg_place, to_topic)
        self.__configure_external_input_port(to_topic)
        
    def __configure_external_input_port(self, target_port_topic):
        self.__serve_input(target_port_topic)

    def __configure_internal_output_port(self, trg_place, to_topic):
        self.__set_place_type(trg_place, trg_place.OUTPUT)
        self._output_ports[trg_place] = to_topic
        # print(f'{self.net.name}/{trg_place.name} is an output to {to_topic}')

    def __set_place_type(self, place, p_type):
        if place.state == place.SEPARATED:
            place.state == p_type
        elif place.state != p_type:
            raise Exception("Place type is already set")
        
    def setup(self):
        self.__setup_client()

    def __setup_client(self):
        self._client = mqtt.Client(self.net.name)
        self._client.on_message = self.on_message
        self._client.connect(self._brocker)
        self._client.user_data_set(self.net.name)
        self._client.loop_start()
        self._client.subscribe('control', 2)

    def __parse_msg(self, message):
        '''
        Parses message and returns a dictionary of it's values
            
        Control message syntax looks like:
            "TYPE ACTION PAYLOAD"
            TYPE -- message type, [RSFA]
                    R means request, S means success, F means failure,
                    A is ack for the last request
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
            elif msg['type'] not in ('A', 'F', 'S'):
                raise Exception('Unknown message type')
        return msg
            

    def __serve_control(self, message):
        '''
        Provides backend API processing for port setup
        '''
        if message['type'] == 'R':
            if message['target_net'] != self.net.name:
                return
            net_places = {p.name: p for p in self.net.place()}
            if message['target_place'] not in net_places.keys():
                self.__control_publish('F, {}'.format(message['payload']))
                return
            self.__control_publish('A, {}'.format(message['payload']))
            if message['action'] == 'set_input':
                try:
                    self.__configure_internal_input_port(
                        net_places[message['target_place']])
                except:
                    self.__control_publish(f"F, {message['payload']}")
                    return
            elif message['action'] == 'set_output':
                try:
                    self.__configure_internal_output_port(
                        net_places[message['target_place']],
                        source_topic)
                except:
                    self.__control_publish(f"F, {message['payload']}")
                    return
            else:
                raise Exception(f'Unknown message action {message}')
            self.__control_publish(f"S, {message['payload']}")
        elif message['type'] == 'A':
            # print('Received A', payload)
            if message['content'] in self._pending_requests:
                self._pending_req_cnt -= 1
        elif message['type'] == 'F':
            raise Exception("Failed to setup {}".format(message['payload']))
        elif message['type'] == 'S':
            if message['content'] not in self._pending_requests:
                return
            self._pending_req_cnt -= 1
            self._pending_requests.remove(message['content'])
            if self._pending_req_cnt == 0:
                self.net.ready = True
                self.net.simul.barier.wait()

    def __serve_port(self, message):
        net, place = message['topic'].split('/')
        if net != self.net.name:
            return
        place = self._input_ports[place]

        # print(f"Serving port {place.name} - {message['payload']}")
        payload = message['payload'].split('&')
        tokens = []
        for tp, val in map(lambda x: x.split(':'), payload):
            tp = eval(tp)   # Type casting
            tokens.append(tp(val))
        place.add(tokens)
        self.net.execute()
    
    def __serve_input(self, target_port_topic):
        self.__control_publish('R, set_input, {}, /'.format(target_port_topic))
        
    def __serve_output(self, target_port_topic, src_topic):
        self.__control_publish('R, set_output, {}, {}'.format(target_port_topic, src_topic))

    def __control_publish(self, message):
        if message[0] == 'R':
            self._pending_requests.append(message)
            self._pending_req_cnt += 2  # Waiting for ack and success message
        self._client.publish('control', message, 2)
    
    def __topic_publish(self, topic, tokens):
        # print(f'publishing {topic} - {"&".join(tokens)}')
        self._client.publish(topic, '&'.join(tokens), 2)
        net = topic.split('/')[0]
        net = self.net.simul._nets[net]
        net.plan_execute()

    def configure(self, planned):
        if not planned:
            self.net.ready = True
        for as_port, place, topic in planned:
            if isinstance(place, str):
                place = self.net.place(place)
            if as_port == 'input':
                self.__input_port_setup(place, topic)
            else:   # configure as output
                self.__output_port_setup(place, topic)

    def send_tokens(self):
        for place, topic in self._output_ports.items():
            tokens = []
            for token in place.tokens:
                tokens.append('{}:{}'.format(
                    token.__class__.__name__, str(token)))
            if tokens:
                self.__topic_publish(topic, tokens)
                place.empty()


                
