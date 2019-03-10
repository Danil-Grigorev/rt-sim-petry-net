#!/bin/python2.7
import time
import logging
from threading import Event, Thread

from heapq import *
from mqtt_client import Mqtt_client
import snakes
import snakes.plugins
snakes.plugins.load(["gv", "let"], "snakes.nets", "plugins")
from snakes.nets import *
from plugins import *

h = logging.FileHandler('out.log', 'w')
h.setLevel(logging.DEBUG)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(threadName)s - %(message)s', handlers=[h])

class PNSim():
    NOW = -2
    INF = float('inf')

    def __init__(self, broker="127.0.0.1"):
        self._nets = {}
        self._broker = broker
        self.end_time = PNSim.INF
        self.scheduler = Scheduler()
        self.cur_time = PNSim.INF
        self.start_time = PNSim.INF
        self._running_events = []
        self._wake_event = Event()

    def run(self, end_time=INF):
        ''' Next-event algorithm with real time extention '''
        assert isinstance(end_time, (int, float))
        self.__setup(end_time)
        logging.info('Starting simulation')
        running_sim = Thread(target=(self._run))
        running_sim.start()
        running_sim.join()
        logging.info('Simulation ended at {}'.format(self.cur_time() - self.start_time))
            
    def _run(self):
        logging.info('Simulation thread started')
        while self.scheduler.next_planned() or self._running_events:
            while self.scheduler.next_planned():
                tm = self.scheduler.next_planned()
                logging.info('Checking event at {}'.format(
                    ((tm - self.start_time) if tm != PNSim.NOW else 'NOW')))
                if tm != PNSim.NOW:
                    if self.end_time != PNSim.INF \
                            and tm >= self.end_time:
                        return
                    if tm != PNSim.NOW and tm < self.cur_time():
                        sys.stderr.write(
                            "Fall back on schedule for {}s at time {}s\n".format(
                            tm - self.cur_time(), self.cur_time() - self.start_time))
                    logging.info('Waiting for {}'.format(tm - self.cur_time()))
                    if tm == PNSim.INF:
                        event_set = self._wake_event.wait()
                    else:
                        event_set = self._wake_event.wait(tm - self.cur_time())
                    if event_set:   # New event arrived
                        logging.info("New event arrived at {}".format(self.cur_time() - self.start_time))
                        continue
                tm, action = self.scheduler.pop_planned()
                logging.info('Extracting event {} - {}'.format(
                    (tm - self.start_time) if tm != PNSim.NOW else 'NOW',
                    action))
                # Execute the action
                if action:
                    function, args = action[0], action[1:]
                    logging.info('Executing {} - {}'.format(
                        (tm - self.start_time) if tm != PNSim.NOW else 'NOW',
                        action))
                    net_runner = Thread(target=function, args=args)
                    net_runner.start()
                    self._running_events.append(net_runner)
            self._running_events = list(
                filter(lambda x: x.is_alive(), self._running_events))
            if self._running_events:
                logging.info('Waiting for threads {}'.format(self._running_events))
                if self.end_time == PNSim.INF:
                    self._wake_event.wait()
                else:
                    self._wake_event.wait(self.end_time - self.cur_time())
                

    def execute_net(self, net):
        if not isinstance(net, snakes.nets.PetriNet):
            net = self._nets[str(net)]
        net.draw(net.name + '-start.png')
        logging.info('Started execution "{}" at {}'.format(net, self.cur_time() - self.start_time))
        while not all([len(t.modes()) == 0 for t in net.transition()]):
            if self.end_time != PNSim.INF and self.cur_time() > self.end_time:
                break   # Simulation time ended
            for t in net.transition():
                modes = t.modes()
                if len(modes) > 0:
                    t.fire(modes[0])
        else:
            net.draw(net.name + '-end.png')
            net.send_tokens()
        self.wake()

    def add_petri_net(self, net):
        mqtt = Mqtt_client(net, self._broker)
        net.add_mqtt_client(mqtt)
        if net.name not in self._nets:
            self._nets[net.name] = net
        else:
            raise NameError("Net {} already exists".format(net.name))

    def __setup(self, end_time):
        self.__wait_net_ports()
        self.start_time = time.time()
        if end_time == PNSim.INF:
            pass
        elif end_time <= 0:
            raise ValueError("Not positive running time value.")
        else:
            self.end_time = self.start_time + end_time
        self.cur_time = time.time
        self.scheduler.start(self.start_time)

    def schedule(self, event, tm=NOW, prior=0):
        if self.start_time == PNSim.INF:
            raise Exception("Simulation is not running")
        if not isinstance(event, list):
            event = [event]
        if tm == PNSim.NOW: # Do at once
            self.scheduler.plan(PNSim.NOW, event, prior)
        elif tm <= 0:
            raise ValueError('Sheduling at past')
        else:   # Wait some time
            self.scheduler.plan(self.start_time + tm, event, prior)
        self.wake()

    def update_time(self, event, tm=NOW, prior=0):
        self.scheduler.remove_planned(PNSim.INF, event, prior)
        self.schedule(event, tm, prior)

    def schedule_at(self, event, tm, prior=0):
        if tm <= 0 and tm != PNSim.NOW:
            raise ValueError("Sheduling at past")
        if not isinstance(event, list):
            event = [event]
        if not callable(event[0]):
            raise TypeError('Event should be callable')
        self.scheduler.plan(tm, event, prior)
        if self.start_time != PNSim.INF:   # Simulation is running
            self.wake()

    def wake(self):
        self._wake_event.set()
        self._wake_event.clear()

    def __wait_net_ports(self):
        for net in self._nets.values():
            net.prepare()
        while not all([net.ready for net in self._nets.values()]):
            got_ready = self._wake_event.wait(10)
            print('Update', [(net, net.ready) for net in self._nets.values()])
            if not got_ready:
                raise RuntimeError('Brocker request timedout {}'.format(
                    [(net, net.ready) for net in self._nets.values()]))

class Scheduler:

    def __init__(self):
        self.queue = []
        self.preplanned = []
        self.running = False

    def start(self, timeval):
        self.running = True
        for prep in self.preplanned:
            t, ev, pr = prep
            if t != PNSim.NOW:
                t += timeval
            self.plan(t, ev, pr)
        self.preplanned = []

    def plan(self, timeval, executable, prior=0):
        """
        Inserts new planned executable in priority heap queue with attention to
        executable's priority.

        Queue is sorted in ascending way, by priority and time.
        Priority should be converted to negative value to preserve queue's
        sorting direction.
        """
        if self.running:
            heappush(self.queue, (timeval, -prior, executable))
        else:
            self.preplanned.append((timeval, executable, prior))

    def pop_planned(self):
        """ 
        Returns and pops next planned executable form scheduler.
        Returns None when heap is empty
        """
        if self.queue:
            timeval, _, executable = heappop(self.queue)
            return timeval, executable
        else:
            return None, None


    def next_planned(self):
        """
        Returns next planned executable in scheduler or None when executable heap is empty
        """
        if self.queue:
            return self.queue[0][0]
        else:
            return None

    def remove_planned(self, timeval, executable, prior=0):
        self.queue.remove((timeval, prior, executable))

        

