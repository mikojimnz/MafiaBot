#!/usr/bin/pyton3

import json
import os
import mysql.connector
import mysql.connector.pooling
import praw
import signal
import sys
import time
import traceback

from mysql.connector import errorcode
from mysql.connector.cursor import MySQLCursorPrepared
from random import randrange
from time import sleep

def main():
    with open("settings.json") as jsonFile1:
        cfg = json.load(jsonFile1)

    reddit = praw.Reddit(cfg['praw'])
    sub = reddit.subreddit(cfg['sub'])
    db = mysql.connector.pooling.MySQLConnectionPool(pool_name=None, raise_on_warnings=True, connection_timeout=3600, **cfg['sql'])
    pool = db.get_connection()
    con = pool.cursor(prepared=True)
    cache = []

    con.execute(cfg['preStm']['main'][0])
    con.execute(cfg['preStm']['main'][1].format(time.time()))
    con.execute(cfg['preStm']['addDummy'])
    con.execute("COMMIT;")
    con.execute("SHOW PROCESSLIST")
    conStat = con.fetchall()

    print("Connected as {}".format(str(reddit.user.me())))
    print("Database Connections: {}".format(len(conStat)))
    print("______")

    while True:
        try:
            for comment in sub.stream.comments(skip_existing=True):
                if ((comment.submission.id == cfg['targetPost']) and (comment.id not in cache)):
                    cache.append(comment.id)
                    con.execute(cfg['preStm']['comment'], (comment.author.name,))
                    con.execute("COMMIT;")
                    print(comment.author.name)

        except mysql.connector.Error as err:
            print("EXCEPTION {}".format(err))
            con.close()
            os._exit(-1)
        except Exception as e:
            traceback.print_exc()
            sleep(10)

    con.close()
    db.close()

def exit_gracefully(signum, frame):
    signal.signal(signal.SIGINT, original_sigint)

    try:
        if input("\nDo you really want to quit? (y/n)> ").lower().startswith('y'):
            sys.exit(1)
    except KeyboardInterrupt:
        print("\nQuitting")
        sys.exit(1)

    signal.signal(signal.SIGINT, exit_gracefully)

if __name__ == "__main__":
    original_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, exit_gracefully)
    main()
