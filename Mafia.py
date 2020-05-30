#!/usr/bin/pyton3

import json
import os
import math
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
from time import sleep

def main():
    with open("settings.json") as jsonfile:
        cfg = json.load(jsonfile)

    reddit = praw.Reddit(cfg['praw'])
    sub = reddit.subreddit(cfg['sub'])
    db = mysql.connector.pooling.MySQLConnectionPool(pool_name=None, raise_on_warnings=True, connection_timeout=3600, **cfg['sql'])
    pool = db.get_connection()
    con = pool.cursor(prepared=True)
    con.execute(cfg['preStm']['main'][0])
    con.execute(cfg['preStm']['main'][1].format(time.time()))
    con.execute("COMMIT;")
    con.execute("SHOW PROCESSLIST")
    conStat = con.fetchall()

    state = 0
    curCycle = 0
    curPos = 0
    stateReply = ["has not yet started.", "has already started."]

    print("Connected as {}".format(str(reddit.user.me())))
    print("Database Connections: ")
    for row in conStat:
        print(row[0])
    print("______")

    while True:
        for item in reddit.inbox.stream():
            if ((re.search('!join', item.body)) and (state == 0)):
                curPos = addUser(item, sub, con, cfg, curPos)
            elif (re.search('!leave', item.body)):
                removeUser(item, sub, con, cfg)
            elif ((re.search('!vote', item.body)) and (state == 1)):
                voteUser(item, sub, con, cfg, curCycle)
            elif ((re.search('!digup', item.body)) and (state == 1)):
                digupUser(item, sub, con, cfg)
            elif ((re.search('!stats', item.body)) and (state == 1)):
                getStats(item, con, cfg, state, curCycle)
            elif (re.search('!help', item.body)):
                showHelp(item, cfg)
            elif (re.search('!rules', item.body)):
                showRules(item, cfg)
            elif (re.search('!gamestate', item.body)):
                state = gameState(item, reddit, con, cfg)
            elif ((re.search('!cycle', item.body)) and (state == 1)):
                curCycle = cycle(item, reddit, sub, con, cfg, curCycle)
            elif (re.search('!ANNOUNCEMENT', item.body)):
                announce(item, reddit, con, cfg)
            elif (re.search('!RESET', item.body)):
                reset(item, sub, db, con, cfg)
            elif (re.search('!HAULT', item.body)):
                hault(item, db, con, cfg)
            else:
                item.reply(cfg['reply']['err']['unkCmd'].format(stateReply[state]))

            item.mark_read()

    con.close()
    db.close()

def gameState(item, reddit, con, cfg):
    pattern = re.search("!gamestate\s([0-9]{1,1})(\s-s)?", item.body)
    target = pattern.group(1)
    silent = pattern.group(2)
    players = 0
    commen = None

    try:
        if (item.author.name != "goldenninjadragon"):
            con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "ATTEMPTED ADMIN COMMAND: gameState"))
            con.execute("COMMIT;")
            return
        else:
            con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "Changed gameState to " + target))
            con.execute(cfg['preStm']['getAll'])
            result = con.fetchall()
            players = len(result)

            for row in result:
                if ((target == "0") and (silent == None)):
                    reddit.redditor(row[0]).message("The game has paused!", cfg['reply']['gamePause'])
                elif ((target == "1") and (silent == None)):
                    reddit.redditor(row[0]).message("The game has started!", cfg['reply']['gameStart'].format(cfg['sub'], cfg['targetPost']))
                elif ((target == "2") and (silent == None)):
                    reddit.redditor(row[0]).message("The game has ended!", cfg['reply']['gameEnd'])
                sleep(0.1)

            if ((target == "0") and (silent == None)):
                comment = reddit.submission(id=cfg['targetPost']).reply(cfg['sticky']['pause'])
                comment.mod.approve()
                comment.mod.distinguish(how='yes', sticky=True)
            elif ((target == "1") and (silent == None)):
                comment = reddit.submission(id=cfg['targetPost']).reply(cfg['sticky']['start'].format(players))
                comment.mod.approve()
                comment.mod.distinguish(how='yes', sticky=True)
            elif ((target == "2") and (silent == None)):
                comment = reddit.submission(id=cfg['targetPost']).reply(cfg['sticky']['end'])
                comment.mod.approve()
                comment.mod.distinguish(how='yes', sticky=True)

            con.execute("COMMIT;")
            item.reply("**gamestate changed to {}**".format(target))
            print("Moving to gamestate {}".format(target))
            return int(target)
    except mysql.connector.Error as err:
        print("EXCEPTION {}".format(err))
        con.close()
        os._exit(-1)

def addUser(item, sub, con, cfg, curPos):
    try:
        if (curPos >= len(cfg['roles'][0])):
            curPos = 0

        item.author.message(cfg['reply']['msgTitle'], cfg['reply']['addUser'].format(item.author.name, cfg['roles'][0][curPos], cfg['sub'], cfg['targetPost']))
        sub.flair.set(item.author, text=cfg['flairs']['alive'].format(1), flair_template_id=cfg['flairID']['alive'])

        con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "Joined Game"))
        con.execute(cfg['preStm']['addUser'], (item.created_utc, item.author.name, cfg['roles'][0][curPos]))
        con.execute("COMMIT;")
        print("  > {} has joined".format(item.author.name))
        curPos += 1
        return curPos
    except mysql.connector.Error as err:
        print("EXCEPTION {}".format(err))
        con.close()
        os._exit(-1)

def removeUser(item, sub, con, cfg):
    try:
        con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "Left Game"))
        con.execute(cfg['preStm']['leave'], (item.author.name,))
        con.execute("COMMIT;")

        item.reply(cfg['reply']['removeUser'])
        sub.flair.delete(item.author)
        print("  > {} has left".format(item.author.name))
    except mysql.connector.Error as err:
        print("EXCEPTION {}".format(err))
        con.close()
        os._exit(-1)

def voteUser(item, sub, con, cfg, curCycle):
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
            elif (((str(r[0][1]) == "ASSASSIN") and (curCycle % 2 != 0)) or ((str(r[0][1]) == "OPERATIVE") and (curCycle % 2 == 0))):
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

def digupUser(item, sub, con, cfg):
    pattern = re.search("!digup\s([A-Za-z0-9_]{1,20})", item.body)
    target = ""
    random.seed(time.time())
    cred = random.randint(1,75)
    role = 0
    roles = {
    "ASSASSIN": 0,
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
            elif ((str(r[0][1]) == "ASSASSIN") or (str(r[0][1]) == "OPERATIVE")):
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

def getStats(item, con, cfg, state, curCycle):
    target = curCycle + 1
    day = int(math.ceil(target/2))
    role = ""
    user = 0
    alive = -1
    killed = -1
    good = -1
    bad = -1
    stateReply = ["not active", "active", "over"]

    try:
        con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "Get Stats"))
        con.execute(cfg['preStm']['digupUser'], (item.author.name,))
        result = con.fetchall()

        if (len(result) == 1):
            role = result[0][0]
            user = result[0][1]
        else:
            role = "spectator"

        con.execute(cfg['preStm']['cycle'][1])
        result = con.fetchall()

        if (len(result[0]) == 2):
            alive = result[0][1]
            killed = result[0][0] - 1

        con.execute(cfg['preStm']['cycle'][2])
        result = con.fetchall()

        if (len(result) == 4):
            good += result[0][1] + result[3][1] + 1
            bad += result[1][1] + result[2][1] + 1

        con.execute("COMMIT;")
        item.reply(cfg['reply']['getSts'].format(stateReply[state], day, role, cfg['reply']['digupUserBody'][1][user], alive, good, bad, killed, alive + killed))
    except mysql.connector.Error as err:
        print("EXCEPTION {}".format(err))
        con.close()
        os._exit(-1)

def showHelp(item, cfg):
    item.reply(cfg['reply']['showHelp'])

def showRules(item, cfg):
    item.reply(cfg['reply']['showRules'])

def cycle(item, reddit, sub, con, cfg, curCycle):
    pattern = re.search("!cycle", item.body)
    target = curCycle + 1
    day = int(math.ceil(target/2))
    alive = -1
    killed = -1
    good = -1
    bad = -1
    mode = {
    0: "Night",
    1: "Day"
    }

    random.seed(time.time())

    try:
        if (item.author.name != "goldenninjadragon"):
            con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "ATTEMPTED ADMIN COMMAND: cycle"))
            con.execute("COMMIT;")
            return
        else:
            con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "curCycle incremented to " + str(target)))
            con.execute(cfg['preStm']['cycle'][0], (cfg['voteThreshold'],))
            con.execute(cfg['preStm']['cycle'][1])
            result = con.fetchall()

            if (len(result) == 2):
                alive = result[0][1]
                killed = result[1][1] - 1

            print("\nAlive: {} | Killed {}".format(alive,killed))

            con.execute(cfg['preStm']['cycle'][2])
            result = con.fetchall()

            if (len(result) == 4):
                good += result[0][1] + result[3][1] + 1
                bad += result[1][1] + result[2][1] + 1

            for row in result:
                print("{} {} still alive".format(row[1], row[0]))

            print("MI6 remaining: {}".format(good))
            print("The Twelve remaining: {}".format(bad))

            con.execute(cfg['preStm']['cycle'][3], (cfg['voteThreshold'],))
            result = con.fetchall()

            for row in result:
                n = random.randint(0,len(cfg['deathMsg']) - 1)
                sub.flair.set(reddit.redditor(row[0]), text=cfg['flairs']['dead'].format(row[1],cfg['deathMsg'][n],day), flair_template_id=cfg['flairID']['dead'])
                reddit.redditor(row[0]).message("You have been killed!", cfg['reply']['cycle'][0].format(cfg['deathMsg'][n], day, alive, good, bad, killed, alive + killed))
                sleep(0.1)

            con.execute(cfg['preStm']['cycle'][4])
            result = con.fetchall()

            for row in result:
                sub.flair.set(reddit.redditor(row[0]), text=cfg['flairs']['alive'].format(day), flair_template_id=cfg['flairID']['alive'])
                sleep(0.1)

            comment = reddit.submission(id=cfg['targetPost']).reply(cfg['sticky']['cycle'].format(mode[curCycle % 2], day, alive, good, bad, killed, alive + killed))
            comment.mod.approve()
            comment.mod.distinguish(how='yes', sticky=True)

            con.execute("TRUNCATE TABLE VoteCall");
            con.execute("COMMIT;")
            item.reply("**Moved to cycle {}**".format(str(target)))
            print("Moved to cycle {}\n".format(str(target)))

            return target
    except mysql.connector.Error as err:
        print("EXCEPTION {}".format(err))
        con.close()
        os._exit(-1)

def announce(item, reddit, con, cfg):
    pattern = re.search("!ANNOUNCEMENT\s([\s\w\d!@#$%^&*()_+{}|:\"<>?\-=\[\]\;\',./’]+)", item.body)
    target = pattern.group(1)

    try:
        if (item.author.name != "goldenninjadragon"):
            con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "ATTEMPTED ADMIN COMMAND: announce"))
            con.execute("COMMIT;")
            return
        else:
            con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "Annouced Message"))
            con.execute(cfg['preStm']['getAll'])
            result = con.fetchall()

            for row in result:
                reddit.redditor(row[0]).message("Annoucment", target)
                sleep(0.1)

            con.execute("COMMIT;")
    except mysql.connector.Error as err:
        print("EXCEPTION {}".format(err))
        con.close()
        os._exit(-1)

def reset(item, reddit, sub, db, con, cfg):
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
                sub.flair.delete(row[0])

            con.execute("TRUNCATE TABLE Mafia;");
            con.execute("TRUNCATE TABLE VoteCall;");
            con.execute("COMMIT;")

            comment = reddit.submission(id=cfg['targetPost']).reply(cfg['sticky']['reset'])
            comment.mod.approve()
            comment.mod.distinguish(how='yes', sticky=True)

            item.reply("**Resetting Game**")
            print("REMOTE RESET RECIEVED")
            con.close()
            os._exit(1)
    except mysql.connector.Error as err:
        print("EXCEPTION {}".format(err))
        con.close()
        os._exit(-1)


def hault(item, reddit, db, con, cfg):
    item.mark_read()

    try:
        if (item.author.name != "goldenninjadragon"):
            con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "ATTEMPTED ADMIN COMMAND: hault"))
            con.execute("COMMIT;")
            return
        else:
            con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "REMOTE HAULT"))
            con.execute("COMMIT;")

            comment = reddit.submission(id=cfg['targetPost']).reply(cfg['sticky']['hault'])
            comment.mod.approve()
            comment.mod.distinguish(how='yes', sticky=True)

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
