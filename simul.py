#!/bin/python3.7
import time
import logging
import signal
import random
import os
import sys
from threading import Condition, Thread, RLock

from heapq import *
from mqtt_client import Mqtt_client
import snakes
import snakes.plugins
snakes.plugins.load(["gv", "let"], "snakes.nets", "plugins")
from snakes.nets import *
from plugins import *

h = logging.FileHandler('planner.log', 'w+')
h.setLevel(logging.DEBUG)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(threadName)s - %(message)s', handlers=[h])


class PNSim(Thread):
    NOW = -2
    INF = float('inf')
    barier = None
    wake_event = Condition()

    def __init__(self, *, broker="127.0.0.1", simul_id=None, detached=True, debug=True):
        """
        Simulation main class initializer.

        broker --   IP address of broker to use
        simul_id -- The name of the simulation instance. Is used for unique identification.
                    If not specified, will be generated from expression sim_run-<rand(0,10000)>.
        detached -- boolean value, which specify if the tokens from Petri Net remote ports
                    should be stored for future sending, or will just disappear, when the
                    target remote port to send is non existing yet, which is corresponds to True.
                    Default value is True.
        debug --    boolean, which specify, if every execution of Petri Net
                    will create a new drawing of it's state.
        """
        self._nets = {}
        self.end_time = PNSim.INF
        self.scheduler = Scheduler()
        self.cur_time = time.time
        self.start_time = PNSim.INF
        self._running_events = []
        self.mqtt = Mqtt_client(self, broker)
        self.kill = False
        self.detached = detached    # If is True, topic messages will not be stored
        self.id = self.setup_id(simul_id)
        self.debug = debug
        Thread.__init__(self)

    def setup_id(self, predefined_id=None):
        if not predefined_id:
            rand_id = f'sim_run-{random.randint(0, 10000)}'
        else:
            rand_id = predefined_id
        png_dir = os.path.dirname(__file__)
        png_dir = os.path.join(png_dir, 'net-drawings')
        if not os.path.exists(png_dir):
            os.mkdir(png_dir)
        sim_dir = os.path.join(png_dir, rand_id)
        if not os.path.exists(sim_dir):
            os.mkdir(sim_dir)
        starting_dir = os.path.join(sim_dir, 'starting')
        current_dir = os.path.join(sim_dir, 'current')
        if not os.path.exists(starting_dir):
            os.mkdir(starting_dir)
        if not os.path.exists(current_dir):
            os.mkdir(current_dir)
        return rand_id

    def setup(self, end_time=INF):
        assert isinstance(end_time, (int, float))
        self.mqtt.configure()
        self.start_time = time.time()
        if end_time == PNSim.INF:
            pass
        elif end_time <= 0:
            raise ValueError("Not positive running time value.")
        else:
            self.end_time = self.start_time + end_time
        self.scheduler.start(self.start_time)

    def run(self):
        ''' Next-event algorithm with real time extention '''
        if self.start_time == PNSim.INF:
            raise Exception('Simulation was not setup')
        logging.info('Starting simulation node')
        while not self.kill:
            while self.scheduler.next_planned():
                interrupted = self._wait_to_event_begin()
                if interrupted:   # New event arrived
                    logging.info(
                        f"New event arrived at {self.cur_time() - self.start_time}")
                    continue
                self._extract_and_execute()
            self._wait_to_finish_or_new_event()
        self.end_run()

    def end_run(self):
        logging.info(
            f'Simulation ended at {self.cur_time() - self.start_time}')
        if self.kill:
            self.mqtt.close()
            logging.info(f'Simulation ended')
            if self.mqtt.remote_requests:
                logging.info(
                    f'Remote requests left unserved: {self.mqtt.remote_requests}')
            print('Simulation interrupted')
        sys.exit()

    def _wait_to_event_begin(self):
        if self.kill:
            self.end_run()
        tm = self.scheduler.next_planned()
        logging.info('Checking event at {}'.format(
            ((tm - self.start_time) if tm != PNSim.NOW else 'NOW')))
        interrupted = False
        if tm == PNSim.NOW:
            return interrupted
        if self.end_time != PNSim.INF \
                and tm >= self.end_time:
            return
        if tm != PNSim.NOW and tm < self.cur_time():
            sys.stderr.write(
                "Fall back on schedule for {}s at time {}s\n".format(
                    tm - self.cur_time(), self.cur_time() - self.start_time))
        logging.info('Waiting for {}'.format(tm - self.cur_time()))
        with PNSim.wake_event:
            if tm == PNSim.INF:
                interrupted = PNSim.wake_event.wait()
            else:
                interrupted = PNSim.wake_event.wait(tm - self.cur_time())
        return interrupted

    def _extract_and_execute(self):
        if self.kill:
            self.end_run()
        tm, action = self.scheduler.pop_planned()
        logging.info(
            f'Extracting event '
            f'{(tm - self.start_time) if tm != PNSim.NOW else "NOW"} '
            f'- {action}')
        # Execute the action
        if action:
            function, args = action[0], action[1:]
            logging.info('Executing {} - {}'.format(
                (tm - self.start_time) if tm != PNSim.NOW else 'NOW',
                action))
            net_runner = Thread(target=function, args=args)
            net_runner.start()
            self._running_events.append(net_runner)

    def _wait_to_finish_or_new_event(self):
        self._running_events = list(
            filter(lambda x: x.is_alive(), self._running_events))
        if self._running_events:
            logging.info('Waiting for threads {}'.format(
                self._running_events))
        with PNSim.wake_event:
            if self.end_time == PNSim.INF:
                PNSim.wake_event.wait()
            else:
                PNSim.wake_event.wait(self.end_time - self.cur_time())

    def execute_net(self, net):
        """
        Main method for net execution, will execute all transition in deterministic
        order, until none of transitions will be enabled, then finish the execution.

        After finishing the execution will draw the current state into the 'current'
        directory for the selected simulation, and send all tokens from output ports.

        net -- Instance of Petri Net to execute
        """
        net = self._nets[str(net)]
        print(f'{self.id}: Executing net {net.name}')
        logging.info(
            f'Started execution "{net}" at {self.cur_time() - self.start_time}')
        presorted_tr = self.presort_transitions(net)
        finished_execution = False
        while not finished_execution:
            if self.kill:
                sys.exit()
            finished_execution = self.execute_groups(presorted_tr)
        if self.debug:
            self.draw_net(net, act=True)
        net.send_tokens() # Sending tokens from output ports
        self.wake()

    def draw_net(self, net, act=False):
        """
        Simple function to draw net images for visualization.

        The structure is following:
            <simulator path>/net-drawings/<simulation name>/starting|current/<net name>.png

        net -- Petri Net instance to be drawn.
        act -- by default is false, allows to draw an instance in 'current'
               directory, for debugging purposes.
        """
        try:
            if act:
                net.draw(f'net-drawings/{self.id}/current/{net.name}.png')
            else:
                net.draw(f'net-drawings/{self.id}/starting/{net.name}.png')
        except:
            pass

    def execute_groups(self, groups):
        """
        Exectuting presorted transitions.

        groups -- list of transitions to execute.
        """
        finished_execution = True
        for group in groups:
            for t in group:
                modes = t.modes()
                if not modes:
                    continue
                # Sorting modes to preserve the order in repeatable execution
                modes.sort(key=lambda x: x.items())
                finished_execution = False
                for m in modes:
                    if not t.enabled(m):
                        continue
                    print(f'Firing: <{t.name}> with {m}')
                    t.fire(m)
                    # Should return to give chance to other transitions
                    # with new bindings to be evaluated
                    return finished_execution
        return finished_execution

    def presort_transitions(self, net):
        """
        Sorting transitions to groups under their priority and hash.

        net -- PetriNet instance to evaluate.
        """
        tgroups = []
        t_list = net.transition()
        t_list.sort(key=lambda x: x.__hash__())

        prior_tr_sort = {}
        for t in t_list:
            pr = t.priority() # Extracts priority from transition
            if pr in prior_tr_sort.keys():
                prior_tr_sort[pr].append(t)
            else:
                prior_tr_sort[pr] = [t]

        for k in sorted(prior_tr_sort.keys()):
            tgroups.insert(0, prior_tr_sort[k])
        return tgroups

    def add_petri_net(self, net):
        """
        Method is registering selected Petri net to the
        simulation instance and the connected MQTT client.

        net -- Petri net instance
        """
        if net.name not in self._nets:
            self._nets[net.name] = net
            self.mqtt.nets[net.name] = net
        else:
            raise NameError("Net {} already exists".format(net.name))

    def schedule(self, event, tm=NOW, prior=0):
        """
        Event planning on time after current running time of simulation.

        event --    element or list of elements, where first element
                    is a pointer to function, and others are arguments
                    to pass.
                    Example: [execute_net, self, net.name]
                        planner will call execute_net function with args
                        self and net.name at planned moment.
        tm --       time value to plan event at. Default value is 'now'.
        prior --    priority of event. The elements with higher
                    priority will be sorted first.

        """
        if self.start_time == PNSim.INF:
            raise Exception("Simulation is not running")
        if not isinstance(event, list):
            event = [event]
        if tm == PNSim.NOW: # Do at once
            self.scheduler.plan(PNSim.NOW, event, prior)
        elif tm <= 0:
            raise ValueError('Scheduling at past')
        else:   # Wait some time
            self.scheduler.plan(self.start_time + tm, event, prior)
        self.wake()

    def update_time(self, event, tm=NOW, prior=0):
        self.scheduler.remove_planned(PNSim.INF, event, prior)
        self.schedule(event, tm, prior)

    def schedule_at(self, event, tm, prior=0):
        """
        Event planning on time from beginning of simulation.
        """
        if tm <= 0 and tm != PNSim.NOW:
            raise ValueError("Scheduling at past")
        if not isinstance(event, list):
            event = [event]
        if not callable(event[0]):
            raise TypeError('Event should be callable')
        self.scheduler.plan(tm, event, prior)
        if self.start_time != PNSim.INF:   # Simulation is running
            self.wake()

    def wake(self):
        with self.wake_event:
            self.wake_event.notify_all()
        if self.kill:
            self.end_run()

class Scheduler:

    def __init__(self):
        self.queue = []
        self.preplanned = []
        self.running = False
        self.lock = RLock()

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
        with self.lock:
            if self.running:
                heappush(self.queue, (timeval, -prior, executable))
            else:
                self.preplanned.append((timeval, executable, prior))

    def pop_planned(self):
        """
        Returns and pops next planned executable form scheduler.
        Returns None when heap is empty
        """
        with self.lock:
            if self.queue:
                timeval, _, executable = heappop(self.queue)
                return timeval, executable
            else:
                return None, None


    def next_planned(self):
        """
        Returns next planned executable in scheduler or None when executable heap is empty
        """
        with self.lock:
            if self.queue:
                return self.queue[0][0]
            else:
                return None

    def remove_planned(self, timeval, executable, prior=0):
        """
        Removes planned event

        timeval -- value of time for event
        executable -- list of function instance and it's arguments
        """
        with self.lock:
            self.queue.remove((timeval, prior, executable))
