#!/usr/bin/pyton3

import json
import os
import mysql.connector
import mysql.connector.pooling
import praw
import random
import re
import time
import signal
import sys

from mysql.connector import errorcode
from mysql.connector.cursor import MySQLCursorPrepared
from random import randrange

def main():
    with open("settings.json") as jsonfile:
        cfg = json.load(jsonfile)

    reddit = praw.Reddit(cfg['praw'])
    ke = reddit.subreddit(cfg['sub'])
    db = mysql.connector.pooling.MySQLConnectionPool(pool_name=None, raise_on_warnings=True, connection_timeout=3600, **cfg['sql'])
    pool = db.get_connection()
    con = pool.cursor(prepared=True)
    con.execute(cfg['preStm']['main'][0])
    con.execute(cfg['preStm']['main'][1].format(time.time()))
    con.execute("COMMIT;")
    con.execute("SHOW PROCESSLIST")
    conStat = con.fetchall()

    gameState = 0
    curCycle = 0
    stateReply = ["has not yet started.", "has already started."]

    print("Connected as {}".format(str(reddit.user.me())))
    print("Database Connections: ")
    for row in conStat:
        print(row[0])
    print("______")

    while True:
        for item in reddit.inbox.stream():
            if ((re.search('!join', item.body)) and (gameState == 0)):
                addUser(item, ke, con, cfg)
            elif ((re.search('!leave', item.body)) and (gameState == 0)):
                removeUser(item, ke, con, cfg)
            elif ((re.search('!vote', item.body)) and (gameState == 1)):
                voteUser(item, ke, con, cfg, curCycle)
            elif ((re.search('!digup', item.body)) and (gameState == 1)):
                digupUser(item, ke, con, cfg)
            elif (re.search('!gamestate', item.body)):
                gameState = gamestate(item, con, cfg)
            elif (re.search('!cycle', item.body)):
                curCycle = cycle(item, con, cfg, curCycle)
            elif (re.search('!RESET', item.body)):
                reset(item, ke, db, con, cfg)
            elif (re.search('!HAULT', item.body)):
                hault(item, db, con, cfg)
            else:
                item.reply(cfg['reply']['err']['unkCmd'].format(stateReply[gameState]))

            item.mark_read()

    con.close()
    db.close()

def gamestate(item, con, cfg):
    pattern = re.search("!gamestate\s([0-9]{1,1})", item.body)
    target = pattern.group(1)

    try:
        if (item.author.name != "goldenninjadragon"):
            con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "ATTEMPTED ADMIN COMMAND: gameState"))
            con.execute("COMMIT;")
            return
        else:
            con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "Changed gameState to " + target))
            con.execute("COMMIT;")

            item.reply("**gamestate changed to {}**".format(target))
            print("Moving to gamestate {}".format(target))

            return int(target)
    except mysql.connector.Error as err:
        print("EXCEPTION {}".format(err))
        con.close()
        os._exit(-1)

def addUser(item, ke, con, cfg):
    random.seed(item.author.name)
    curPos = random.randint(0,3)

    try:
        con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "Joined Game"))
        con.execute(cfg['preStm']['addUser'], (item.created_utc, item.author.name, cfg['roles'][0][curPos]))
        con.execute("COMMIT;")

        item.author.message(cfg['reply']['msgTitle'], cfg['reply']['addUser'].format(item.author.name, cfg['roles'][0][curPos]))

        ke.flair.set(item.author, text=cfg['flairs']['alive'])

        curPos += 1
        if (curPos >= len(cfg['roles'])):
            curPos = 0
        print("  > {} has joined".format(item.author.name))
    except mysql.connector.Error as err:
        print("EXCEPTION {}".format(err))
        con.close()
        os._exit(-1)

def removeUser(item, ke, con, cfg):
    try:
        con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "Left Game"))
        con.execute(cfg['preStm']['leave'], (item.author.name,))
        con.execute("COMMIT;")

        item.reply(cfg['reply']['removeUser'])
        ke.flair.delete(item.author)
        print("  > {} has left".format(item.author.name))
    except mysql.connector.Error as err:
        print("EXCEPTION {}".format(err))
        con.close()
        os._exit(-1)

def voteUser(item, ke, con, cfg, curCycle):
    pattern = re.search("!vote\s([A-Za-z0-9_]{1,20})", item.body)
    target = ""

    if pattern:
        target = pattern.group(1)
        try:
            con.execute(cfg['preStm']['chkUsr'], (item.author.name,))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(cfg['reply']['err']['spec'])
                return
            elif ((str(r[0][1]) == "HANDLER") or (str(r[0][1]) == "ANALYST")):
                item.reply(cfg['reply']['err']['role'])
                return
            elif (((str(r[0][1]) == "ASSASIN") and (curCycle % 2 != 0)) or ((str(r[0][1]) == "OPERATIVE") and (curCycle % 2 == 0))):
                item.reply(cfg['reply']['err']['cycle'])
                return

            con.execute(cfg['preStm']['digupUser'], (target,))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(cfg['reply']['err']['notFound'])
                return

            con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "Vote: {}".format(target)))
            con.execute(cfg['preStm']['voteUser'], (item.author.name, target, target))
            con.execute("COMMIT;")
            item.reply(cfg['reply']['voteUser'])
            print("  > {} has voted to kill {}".format(item.author.name, target))
        except mysql.connector.Error as err:
            print("EXCEPTION {}".format(err))
            con.close()
            os._exit(-1)
    else:
        item.reply(cfg['reply']['err']['nmFmt'])

def digupUser(item, ke, con, cfg):
    pattern = re.search("!digup\s([A-Za-z0-9_]{1,20})", item.body)
    target = ""
    random.seed(time.time())
    cred = random.randint(1,75)
    role = 0
    roles = {
    "ASSASIN": 0,
    "HANDLER": 1,
    "OPERATIVE": 2,
    "ANALYST": 3
    }

    if pattern:
        target = pattern.group(1)
        try:
            con.execute(cfg['preStm']['chkUsr'], (item.author.name,))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(cfg['reply']['err']['spec'])
                return
            elif ((str(r[0][1]) == "ASSASIN") or (str(r[0][1]) == "OPERATIVE")):
                item.reply(cfg['reply']['err']['role'])
                return

            con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "Investigate: {}".format(target)))
            con.execute(cfg['preStm']['digupUser'], (target,))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(cfg['reply']['err']['notFound'])
                return

            con.execute("COMMIT;")

            if ((cred >= 1) and (cred < 25)):
                if (random.randint(0,7) == 0):
                    role = roles[r[0][0]]
                else:
                    role = (roles[r[0][0]] + random.randint(1,2)) % 4
            elif ((cred >= 25) and (cred < 50)):
                if (random.randint(0,4) == 0):
                    role = roles[r[0][0]]
                else:
                    role = (roles[r[0][0]] + random.randint(1,2)) % 4
            elif ((cred >= 50) and (cred < 75)):
                if (random.randint(0,2) == 0):
                    role = roles[r[0][0]]
                else:
                    role = (roles[r[0][0]] + random.randint(1,2)) % 4
            else:
                role = roles[r[0][0]]

            item.reply(cfg['reply']['digupUser'].format(target, cfg['reply']['digupUserBody'][0][role], cfg['reply']['digupUserBody'][1][r[0][1]], str(cred)))
            print("  > {} has investgated {}".format(item.author.name, target))
        except mysql.connector.Error as err:
            print("EXCEPTION {}".format(err))
            con.close()
            os._exit(-1)
    else:
        item.reply(cfg['reply']['err']['nmFmt'])

def cycle(item, con, cfg, curCycle):
    pattern = re.search("!cycle", item.body)
    target = curCycle + 1

    try:
        if (item.author.name != "goldenninjadragon"):
            con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "ATTEMPTED ADMIN COMMAND: cycle"))
            con.execute("COMMIT;")
            return
        else:
            con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "curCycle incremented to " + str(target)))
            con.execute("COMMIT;")

            item.reply("**Moved to cycle {}**".format(str(target)))
            print("Moved to cycle {}".format(str(target)))

            return target
    except mysql.connector.Error as err:
        print("EXCEPTION {}".format(err))
        con.close()
        os._exit(-1)

def reset(item, ke, db, con, cfg):
    item.mark_read()

    try:
        if (item.author.name != "goldenninjadragon"):
            con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "ATTEMPTED ADMIN COMMAND: reset"))
            con.execute("COMMIT;")
            return
        else:
            con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "REMOTE RESET"))
            con.execute("SELECT `username` FROM Mafia")
            result = con.fetchall()

            for row in result:
                ke.flair.delete(row[0])

            con.execute("TRUNCATE TABLE Mafia;");
            con.execute("TRUNCATE TABLE VoteCall;");
            con.execute("COMMIT;")

            item.reply("**Resetting Game**")
            print("REMOTE RESET RECIEVED")
            con.close()
            os._exit(1)
    except mysql.connector.Error as err:
        print("EXCEPTION {}".format(err))
        con.close()
        os._exit(-1)


def hault(item, db, con, cfg):
    item.mark_read()

    try:
        if (item.author.name != "goldenninjadragon"):
            con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "ATTEMPTED ADMIN COMMAND: hault"))
            con.execute("COMMIT;")
            return
        else:
            con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "REMOTE HAULT"))
            con.execute("COMMIT;")

            item.reply("**Stopping Game**")
            print("REMOTE HAULT RECIEVED")
            con.close()
            os._exit(1)
    except mysql.connector.Error as err:
        print("EXCEPTION {}".format(err))
        con.close()
        os._exit(-1)

def exit_gracefully(signum, frame):
    signal.signal(signal.SIGINT, original_sigint)

    try:
        if input("\nDo you really want to quit? (y/n)> ").lower().startswith('y'):
            sys.exit(1)
    except KeyboardInterrupt:
        print("Ok ok, quitting")
        sys.exit(1)

    signal.signal(signal.SIGINT, exit_gracefully)

if __name__ == "__main__":
    original_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, exit_gracefully)
    main()
