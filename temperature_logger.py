#!/bin/python2.7

import paho.mqtt.client as mqtt
import sys
import time
import signal


room_specific = {
    '{room_name}-temperature-updater/Inside update': 'logger/{room_name}-inside_temperature',
}

rooms = ['kitchen', 'dining_room', 'storeroom']

log = {}

def parse_tokens(tokens):
    tokens = tokens.split('&')
    token_list = []
    for tp, val in map(lambda x: x.split(':', 1), tokens):
        print(tp, val)
        tk = parse_subtokens(tp, val)
        token_list.append(tk)
    return token_list

def parse_subtokens(tp, value):
    tp = eval(tp)  # Type casting
    if tp == tuple:
        parsed_tokens = []
        value = eval(value)  # Converting string list to list
        for tp_v, val in map(lambda x: x.split(':'), value):
            tk = parse_subtokens(tp_v, val)
            parsed_tokens.append(tk)
        return tuple([tp(parsed_tokens)])
    elif tp == bool:
        return value == 'True'
    else:
        return tp(value)



def on_message(client, userdata, message):
    tokens = message.payload.decode("utf-8")
    tokens = parse_tokens(tokens)

    log_name = message.topic.split('/')[1]

    log[log_name] = tokens
    print(log)

def setup_mqtt(brok_addr="127.0.0.1"):
    client = mqtt.Client()
    client._client_id = "logger"
    client.on_message = on_message

    client.connect(brok_addr)
    client.loop_start()
    for room in rooms:
        for topic in room_specific:
            client.subscribe(room_specific[topic].format(room_name=room), qos=2)

    # Sending registration message
    client.publish('control', f'U, update_nets, {client._client_id}, logger', qos=2)

    # Setting ports to log into application
    for room in rooms:
        for topic in room_specific:
            room_port = topic.format(room_name=room)
            client.publish('control',
                           f'R, set_output, {room_port}, logger/{room}-inside_temperature', qos=2)
    return client


def main():
    client = setup_mqtt()
    try:
        while True:
            time.sleep(1)
    except:
        pass

    # Unregistering client
    client.publish(
        'control', f'U, remove_nets, {client._client_id}, logger', qos=2)
    client.loop_stop()


if __name__ == "__main__":

    main()
