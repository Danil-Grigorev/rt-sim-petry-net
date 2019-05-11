#!/usr/bin/python3.7

import signal
import snakes
from snakes.nets import *   # Site, mista, prechody...
from simul import PNSim     # Simulacni knihovna
snakes.plugins.load(
    ["gv", "timed_pl", "sim_pl", "prob_pl", "prior_pl"],
    "snakes.nets",
    "plugins")  # Seznam rozsireni pro import
from plugins import *  # Redefinovane metody z rozsireni
