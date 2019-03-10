#!/bin/python2.7

import paho.mqtt.client as mqtt
import time


def on_message(client, userdata, message):
    print(client, userdata)
    print(message.topic + " - " + message.payload.decode("utf-8"))

broker = "127.0.0.1"
client = mqtt.Client()
client.on_message = on_message

client.connect(broker)
client.loop_start()
client.subscribe("nets/")
client.subscribe('nets/custom')
while True:
    text = raw_input("Print q for exit: ")
    if text == 'q':
        break
    client.publish('nets/', text)
    client.publish('nets', text)
    client.publish('nets/other', text)
client.loop_stop()
