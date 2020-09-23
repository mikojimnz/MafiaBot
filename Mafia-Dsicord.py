#!/usr/bin/pyton3

import datetime
import functools
import json
import os
import math
import mysql.connector
import mysql.connector.pooling
import pickle
import random
import re
import schedule
import signal
import sys
import time
import traceback

from mysql.connector import errorcode
from mysql.connector.cursor import MySQLCursorPrepared
from random import randrange
from time import sleep

exceptCnt = 0
state = None
curCycle = None

with open("settings.json") as jsonFile1:
    cfg = json.load(jsonFile1)

client = commands.Bot(command_prefix=cfg['discord']['cmdPrefix'])

@client.event
async def on_ready():
    pass

client.run(cfg['discord']['clientID'])
