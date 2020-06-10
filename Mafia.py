#!/usr/bin/pyton3

import datetime
import json
import os
import math
import mysql.connector
import mysql.connector.pooling
import praw
import random
import re
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
    with open("save.json") as jsonFile2:
        sve = json.load(jsonFile2)

    exceptCnt = 0
    state = sve['state']
    curCycle = sve['curCycle']
    curPos = sve['curPos']
    reddit = praw.Reddit(cfg['praw'])
    sub = reddit.subreddit(cfg['sub'])
    db = mysql.connector.pooling.MySQLConnectionPool(pool_name=None, raise_on_warnings=True, connection_timeout=3600, **cfg['sql'])
    pool = db.get_connection()
    con = pool.cursor(prepared=True)
    cache = []

    con.execute(cfg['preStm']['main'][0])
    con.execute(cfg['preStm']['main'][1], (time.time(),))
    con.execute(cfg['preStm']['addDummy'])
    con.execute("COMMIT;")
    con.execute("SHOW PROCESSLIST")
    conStat = con.fetchall()

    print("Connected as {}".format(str(reddit.user.me())))
    print("Database Connections: {}".format(len(conStat)))
    print("state: {}".format(state))
    print("curCycle: {} (Cycle: {})".format(curCycle, curCycle + 1))
    print("curPos: {}".format(curPos))
    print("______")

    while True:
        try:
            for item in reddit.inbox.stream(pause_after=-1):
                if item is None:
                    break

                if (item.was_comment == True):
                    continue

                if ((re.search('^!join', item.body)) and (curCycle <= cfg['allowJoinUptTo'])):
                    curPos = addUser(item, sub, con, cfg, curPos)
                    save(state, curCycle, curPos)
                elif (re.search('^!leave', item.body)):
                    removeUser(item, sub, con, cfg, curCycle)
                elif ((re.search('^!vote', item.body)) and (state == 1)):
                    voteUser(item, reddit, con, cfg, curCycle)
                elif ((re.search('^!burn', item.body)) and (state == 1)):
                    burnUser(item, reddit, sub, con, cfg, curCycle)
                elif ((re.search('^!revive', item.body)) and (state == 1)):
                    reviveUser(item, reddit, sub, con, cfg, curCycle)
                elif ((re.search('^!digup', item.body)) and (state == 1)):
                    digupUser(item, con, cfg)
                elif ((re.search('^!locate', item.body)) and (state == 1)):
                    locateUser(item, con, cfg)
                elif ((re.search('^!request', item.body)) and (state == 1)):
                    requestUser(item, reddit, con, cfg)
                elif ((re.search('^!list', item.body))):
                    getList(item, con, cfg, state)
                elif ((re.search('^!stats', item.body)) and (state == 1)):
                    getStats(item, con, cfg, state, curCycle)
                elif (re.search('^!help', item.body)):
                    showHelp(item, cfg)
                elif (re.search('^!rules', item.body)):
                    showRules(item, cfg)
                elif (re.search('^!GAMESTATE', item.body)):
                    state = gameState(item, reddit, sub, con, cfg, curCycle)
                    save(state, curCycle, curPos)
                elif ((re.search('^!CYCLE', item.body)) and (state == 1)):
                    curCycle = cycle(item, reddit, sub, con, cfg, curCycle)
                    save(state, curCycle, curPos)
                elif (re.search('^!BROADCAST', item.body)):
                    announce(item, reddit, con, cfg)
                elif (re.search('^!RESTART', item.body)):
                    restart(item, reddit, sub, db, con, cfg)
                elif (re.search('^!RESET', item.body)):
                    reset(item, sub, db, con, cfg)
                elif (re.search('^!HALT', item.body)):
                    halt(item, reddit, db, con, cfg)
                else:
                    item.reply(cfg['reply']['err']['unkCmd'][0][0].format(cfg['reply']['err']['unkCmd'][1][state]))

                item.mark_read()

        except mysql.connector.Error as err:
            print("EXCEPTION {}".format(err))
            con.close()
            os._exit(-1)
        except Exception as e:
            traceback.print_exc()
            exceptCnt += 1
            print("Exception #{}\nSleeping for {} seconds".format(exceptCnt, (60 * exceptCnt)))
            sleep(60 * exceptCnt)

        if (state == 1):
            t = datetime.datetime.now()

            if (((t.hour % 12 == cfg['clock']['hour1'] - 1) or (t.hour % 12 == cfg['clock']['hour2'] - 1)) and (t.minute == 30) and (t.second <= 1)):
                comment = reddit.submission(id=cfg['targetPost']).reply(cfg['sticky']['min30'])
                print("Cycle: 30 min warning")
                sleep(2)
            elif (((t.hour % 12 == cfg['clock']['hour1'] - 1) or (t.hour % 12 == cfg['clock']['hour2'] - 1)) and (t.minute == 45) and (t.second <= 1)):
                comment = reddit.submission(id=cfg['targetPost']).reply(cfg['sticky']['min15'])
                print("Cycle: 15 min warning")
                sleep(2)
            elif (((t.hour % 12 == cfg['clock']['hour1'] - 1) or (t.hour % 12 == cfg['clock']['hour2'] - 1)) and (t.minute == 55) and (t.second <= 1)):
                comment = reddit.submission(id=cfg['targetPost']).reply(cfg['sticky']['min5'])
                print("Cycle: 5 min warning")
                sleep(2)
            elif (((t.hour % 12 == cfg['clock']['hour1']) or (t.hour % 12 == cfg['clock']['hour2'])) and (t.minute == 0) and (t.second <= 1)):
                item = type('', (), {})()
                item.author = type('', (), {})()
                item.author.name = "*SELF*"
                item.body = "!CYCLE"
                item.created_utc = time.time()
                curCycle = cycle(item, reddit, sub, con, cfg, curCycle)
                save(state, curCycle, curPos)
                print("Cycle: Auto Run")
                sleep(2)

    con.close()

def save(state, curCycle, curPos):
    with open("save.json", "r+") as jsonFile2:
        tmp = json.load(jsonFile2)
        tmp['state'] = state
        tmp['curCycle'] = curCycle
        tmp['curPos'] = curPos
        jsonFile2.seek(0)
        json.dump(tmp, jsonFile2)
        jsonFile2.truncate()

def gameState(item, reddit, sub, con, cfg, curCycle):
    pattern = re.search("^!GAMESTATE\s([0-9]{1,1})(\s-s)?", item.body)
    setState = pattern.group(1)
    silent = pattern.group(2)
    players = 0

    try:
        if (item.author.name not in cfg['adminUsr']):
            con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "ATTEMPTED ADMIN COMMAND: gameState"))
            con.execute("COMMIT;")
            return
        else:
            con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "Changed gameState to {}".format(setState)))
            con.execute(cfg['preStm']['getAll'])
            result = con.fetchall()
            players = len(result)

            for row in result:
                if ((setState == "0") and (silent == None)):
                    reddit.redditor(row[0]).message("The game has paused!", cfg['reply']['gamePause'])
                elif ((setState == "1") and (silent == None)):
                    reddit.redditor(row[0]).message("The game has started!", cfg['reply']['gameStart'].format(cfg['sub'], cfg['targetPost']))
                sleep(0.1)

            if ((setState == "0") and (silent == None)):
                comment = reddit.submission(id=cfg['targetPost']).reply(cfg['sticky']['pause'])
                comment.mod.distinguish(how='yes', sticky=True)
            elif ((setState == "1") and (silent == None)):
                comment = reddit.submission(id=cfg['targetPost']).reply(cfg['sticky']['start'].format(players))
                comment.mod.distinguish(how='yes', sticky=True)
            elif ((setState == "2") and (silent == None)):
                endGame(item, reddit, sub, con, cfg, curCycle)

            con.execute("COMMIT;")
            if (item.author.name != "*SELF*"): item.reply("**gamestate changed to {}**".format(setState))
            print("Moving to gamestate {}".format(setState))
            return int(setState)
    except mysql.connector.Error as err:
        print("EXCEPTION {}".format(err))
        con.close()
        os._exit(-1)

def addUser(item, sub, con, cfg, curPos):
    curPos = 0

    try:
        con.execute(cfg['preStm']['chkUsrState'],(item.author.name,))
        result = con.fetchall()

        if(len(result) > 0):
            con.execute(cfg['preStm']['addExistingUser'], (item.author.name,))
            item.reply(cfg['reply']['addUser'].format(item.author.name, result[0][0], result[0][1], cfg['sub'], cfg['targetPost']))
            sub.flair.set(item.author, text=cfg['flairs']['alive'].format(1), flair_template_id=cfg['flairID']['alive'])
            return
        else:
            if ((curPos >= len(cfg['roles'][0]))):
                curPos = 0

        random.seed(time.time())
        if ((curPos == 0) or (curPos == 1)):
            loc = cfg['location'][0][random.randint(0, len(cfg['location'][0]) - 1)]
        else:
            loc = cfg['location'][1][random.randint(0, len(cfg['location'][1]) - 1)]

        item.reply(cfg['reply']['addUser'].format(item.author.name, cfg['roles'][0][curPos], loc, cfg['sub'], cfg['targetPost']))
        sub.flair.set(item.author, text=cfg['flairs']['alive'].format(1), flair_template_id=cfg['flairID']['alive'])

        con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "Joined Game"))
        con.execute(cfg['preStm']['addUser'], (item.created_utc, item.author.name, cfg['roles'][0][curPos], loc))
        con.execute("COMMIT;")
        print("  > {} has joined".format(item.author.name))
        curPos += 1
        return curPos
    except mysql.connector.Error as err:
        print("EXCEPTION {}".format(err))
        con.close()
        os._exit(-1)

def removeUser(item, sub, con, cfg, curCycle):
    try:
        con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "Left Game"))
        con.execute(cfg['preStm']['leave'], (curCycle, item.author.name))
        con.execute("COMMIT;")

        item.reply(cfg['reply']['removeUser'])
        sub.flair.delete(item.author)
        print("  > {} has left".format(item.author.name))
    except mysql.connector.Error as err:
        print("EXCEPTION {}".format(err))
        con.close()
        os._exit(-1)

def voteUser(item, reddit, con, cfg, curCycle):
    pattern = re.search("^!vote\s(u/)?([A-Za-z0-9_]{1,20})", item.body)
    name = ""
    round = curCycle + 1
    day = int(math.ceil(round/2))
    mode = {
    0: "Day",
    1: "Night"
    }

    if pattern:
        name = pattern.group(2)
        try:
            con.execute(cfg['preStm']['chkUsr'], (item.author.name,))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(cfg['reply']['err']['spec'])
                return

            if ((cfg['allowAllVote'] == 0)):
                if ((str(r[0][1]) == "HANDLER") or (str(r[0][1]) == "ANALYST")):
                    item.reply(cfg['reply']['err']['role'])
                    return

            if ((cfg['allowVoteAnyTime'] == 0)):
                if ((((r[0][1] == "ASSASSIN") or (r[0][1] == "HANDLER")) and (curCycle % 2 == 0)) or (((r[0][1] == "OPERATIVE") or (r[0][1] == "ANALYST")) and (curCycle % 2 != 0))):
                    item.reply(cfg['reply']['err']['cycle'].format(mode[curCycle % 2]))
                    return

            con.execute(cfg['preStm']['chkCmt'], (item.author.name, cfg['cmtThreshold']))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(cfg['reply']['err']['noParticipate'])
                return

            con.execute(cfg['preStm']['digupUser'], (name,))
            r = con.fetchall()

            if ((len(r) <= 0) or (r[0][1]) == 0):
                item.reply(cfg['reply']['err']['notFound'])
                return

            con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "Vote: {}".format(name)))
            con.execute(cfg['preStm']['voteUser'], (item.author.name, name, name))
            con.execute("COMMIT;")

            item.reply(cfg['reply']['voteUser'])

            if ((str(r[0][1]) == "ASSASSIN") or (str(r[0][1]) == "OPERATIVE")):
                reddit.redditor(name).message("A hit has been put on you!", cfg['reply']['hitAlertEsc'].format(name, round))
            else:
                reddit.redditor(name).message("A hit has been put on you!", cfg['reply']['hitAlert'].format(name, round))

            print("  > {} has voted to kill {}".format(item.author.name, name))
        except mysql.connector.Error as err:
            print("EXCEPTION {}".format(err))
            con.close()
            os._exit(-1)
    else:
        item.reply(cfg['reply']['err']['nmFmt'])

def burnUser(item, reddit, sub, con, cfg, curCycle):
    pattern = re.search("^!burn", item.body)
    round = curCycle + 1
    day = int(math.ceil(round/2))
    selfRole = ""
    burned = ""
    burnedRole = ""
    side = 0


    if (curCycle <= cfg['allowBurnOn']):
        item.reply(cfg['reply']['err']['noBurnYet'])
        return

    try:
        con.execute(cfg['preStm']['chkUsr'], (item.author.name,))
        r = con.fetchall()

        if (len(r) <= 0):
            item.reply(cfg['reply']['err']['spec'])
            return

        con.execute(cfg['preStm']['chkBurn'], (item.author.name,))
        r = con.fetchall()

        if (len(r) <= 0):
            item.reply(cfg['reply']['err']['burnUsed'])
            return

        selfRole = r[0][1]

        if ((selfRole == "ASSASSIN") or (selfRole == "HANDLER")):
            side = 0
        else:
            side = 1

        con.execute(cfg['preStm']['burn'][side], (item.author.name,))
        r = con.fetchall()

        if (len(r) <= 0):
            item.reply(cfg['reply']['err']['noBurnLeft'])
            return

        random.seed(time.time())
        rand = random.randint(0, len(r) - 1)
        burned = r[rand][0]
        burnedRole = r[rand][1]

        if ((selfRole == "ASSASSIN") or (selfRole == "HANDLER")):
            side = 2
        else:
            side = 3

        con.execute(cfg['preStm']['burn'][side])
        r = con.fetchall()

        if (len(r) <= 0):
            item.reply(cfg['reply']['err']['noBurnLeft'])
            return

        target = r[random.randint(0, len(r) - 1)]

        con.execute(cfg['preStm']['burn'][4], (item.author.name,))
        con.execute(cfg['preStm']['burn'][5], (burned,))
        con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "{} burned {}".format(item.author.name, burned)))
        con.execute("COMMIT;")

        n = random.randint(0,len(cfg['deathMsg']) - 1)
        sub.flair.set(reddit.redditor(burned), text=cfg['flairs']['dead'].format(burnedRole, cfg['deathMsg'][n], day), flair_template_id=cfg['flairID']['dead'])
        reddit.redditor(burned).message("You have been burned!", cfg['reply']['burnedUser'].format(item.author.name, round))
        item.reply(cfg['reply']['burnUser'].format(target[0], target[1]))
        comment = reddit.submission(id=cfg['targetPost']).reply(cfg['sticky']['burnUser'].format(item.author.name, burned))
        print("  > {} has burned {}".format(item.author.name, burned))
    except mysql.connector.Error as err:
        print("EXCEPTION {}".format(err))
        con.close()
        os._exit(-1)

def reviveUser(item, reddit, sub, con, cfg, curCycle):
    pattern = re.search("^!revive\s(u/)?([A-Za-z0-9_]{1,20})", item.body)
    name = ""
    round = curCycle + 1
    day = int(math.ceil(round/2))

    if (cfg['allowRevive'] == 0):
        item.reply(cfg['reply']['err']['disallowRevive'])
        return

    if pattern:
        name = pattern.group(2)
        try:
            con.execute(cfg['preStm']['chkUsr'], (item.author.name,))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(cfg['reply']['err']['spec'])
                return

            con.execute(cfg['preStm']['revive'][0], (item.author.name,))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(cfg['reply']['err']['reviveUsed'])
                return

            con.execute(cfg['preStm']['revive'][1], (name,))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(cfg['reply']['err']['notFound'])
                return

            con.execute(cfg['preStm']['revive'][2], (item.author.name,))
            con.execute(cfg['preStm']['revive'][3], (name,))
            con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "{} revived {}".format(item.author.name, name)))
            con.execute("COMMIT;")

            sub.flair.set(reddit.redditor(name), text=cfg['flairs']['alive'].format(day), flair_template_id=cfg['flairID']['alive'])
            reddit.redditor(name).message("You have been revived!", cfg['reply']['revivedUser'].format(item.author.name))
            item.reply(cfg['reply']['reviveUser'].format(name))

            print("  > {} has revived {}".format(item.author.name, name))
        except mysql.connector.Error as err:
            print("EXCEPTION {}".format(err))
            con.close()
            os._exit(-1)
    else:
        item.reply(cfg['reply']['err']['nmFmt'])

def digupUser(item, con, cfg):
    pattern = re.search("^!digup\s(u/)?([A-Za-z0-9_]{1,20})", item.body)
    name = ""
    random.seed(time.time())
    cred = random.randint(25,75)
    role = 0

    if pattern:
        name = pattern.group(2)
        try:
            con.execute(cfg['preStm']['chkUsr'], (item.author.name,))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(cfg['reply']['err']['spec'])
                return
            elif ((str(r[0][1]) == "ASSASSIN") or (str(r[0][1]) == "OPERATIVE")):
                cred = random.randint(1,25)

            con.execute(cfg['preStm']['chkCmt'], (item.author.name, cfg['cmtThreshold']))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(cfg['reply']['err']['noParticipate'])
                return

            con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "Investigate: {}".format(name)))
            con.execute(cfg['preStm']['digupUser'], (name,))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(cfg['reply']['err']['notFound'])
                return

            con.execute("COMMIT;")

            if ((cred >= 1) and (cred < 25)):
                if (random.randint(0,7) == 0):
                    role = cfg['roles'][1][r[0][0]]
                else:
                    role = (cfg['roles'][1][r[0][0]] + random.randint(1,2)) % 4
            elif ((cred >= 25) and (cred < 50)):
                if (random.randint(0,4) == 0):
                    role = cfg['roles'][1][r[0][0]]
                else:
                    role = (cfg['roles'][1][r[0][0]] + random.randint(1,2)) % 4
            elif ((cred >= 50) and (cred < 75)):
                if (random.randint(0,2) == 0):
                    role = cfg['roles'][1][r[0][0]]
                else:
                    role = (cfg['roles'][1][r[0][0]] + random.randint(1,2)) % 4
            else:
                role = cfg['roles'][1][r[0][0]]

            item.reply(cfg['reply']['digupUser'].format(name, cfg['reply']['digupUserBody'][0][role], cfg['reply']['digupUserBody'][1][r[0][1]], str(cred)))
            print("  > {} has investgated {}".format(item.author.name, name))
        except mysql.connector.Error as err:
            print("EXCEPTION {}".format(err))
            con.close()
            os._exit(-1)
    else:
        item.reply(cfg['reply']['err']['nmFmt'])

def locateUser(item, con, cfg):
    pattern = re.search("^!locate\s(u/)?([A-Za-z0-9_]{1,20})", item.body)
    name = ""
    role = 0

    if pattern:
        name = pattern.group(2)
        try:
            con.execute(cfg['preStm']['chkUsr'], (item.author.name,))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(cfg['reply']['err']['spec'])
                return

            con.execute(cfg['preStm']['chkCmt'], (item.author.name,cfg['cmtThreshold']))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(cfg['reply']['err']['noParticipate'])
                return

            con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "Locate: {}".format(name)))
            con.execute(cfg['preStm']['locateUser'], (name,))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(cfg['reply']['err']['notFound'])
                return

            con.execute("COMMIT;")

            item.reply(cfg['reply']['locateUser'].format(name, r[0][0]))
            print("  > {} has located {}".format(item.author.name, name))
        except mysql.connector.Error as err:
            print("EXCEPTION {}".format(err))
            con.close()
            os._exit(-1)
    else:
        item.reply(cfg['reply']['err']['nmFmt'])

def requestUser(item, reddit, con, cfg):
    pattern = re.search("^!request\s(u/)?([A-Za-z0-9_]{1,20})", item.body)
    name = ""

    if pattern:
        name = pattern.group(2)
        try:
            con.execute(cfg['preStm']['chkUsr'], (item.author.name,))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(cfg['reply']['err']['spec'])
                return

            con.execute(cfg['preStm']['chkCmt'], (item.author.name, cfg['cmtThreshold']))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(cfg['reply']['err']['noParticipate'])
                return

            con.execute(cfg['preStm']['digupUser'], (name,))
            r = con.fetchall()

            if ((len(r) <= 0) or (r[0][1]) == 0):
                item.reply(cfg['reply']['err']['notFound'])
                return

            con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "{} Requested: {}".format(item.author.name, name)))
            con.execute("COMMIT;")

            item.reply(cfg['reply']['requestUser'])
            comment = reddit.submission(id=cfg['targetPost']).reply(cfg['sticky']['requestUser'].format(name))
            print("  > {} has requested info on {}".format(item.author.name, name))
        except mysql.connector.Error as err:
            print("EXCEPTION {}".format(err))
            con.close()
            os._exit(-1)
    else:
        item.reply(cfg['reply']['err']['nmFmt'])

def getList(item, con, cfg, state):
    dead = ""
    alive = ""
    deadNum = 0
    aliveNum = 0

    try:
        con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "Get List"))
        con.execute(cfg['preStm']['getList'][0])
        result = con.fetchall()

        for row in result:
            dead += "\n* u/{}: {}".format(row[0], row[1])
            deadNum += 1

        con.execute(cfg['preStm']['getList'][1])
        result = con.fetchall()

        for row in result:
            alive += "\n* u/{}".format(row[0])
            aliveNum += 1

        con.execute("COMMIT;")
        item.reply(cfg['reply']['getList'].format(deadNum + aliveNum, deadNum, dead, aliveNum, alive))
        print("  > {} requested players".format(item.author.name))
    except mysql.connector.Error as err:
        print("EXCEPTION {}".format(err))
        con.close()
        os._exit(-1)

def getStats(item, con, cfg, state, curCycle):
    round = curCycle + 1
    day = int(math.ceil((round)/2))
    role = ""
    user = 0
    alive = 0
    killed = 0
    good = 0
    bad = 0
    mode = {
    0: "Day",
    1: "Night"
    }

    try:
        con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "Get Stats"))
        con.execute(cfg['preStm']['digupUser'], (item.author.name,))
        result = con.fetchall()

        if (len(result) == 1):
            role = result[0][0]
            user = result[0][1]
        else:
            role = "spectator"

        con.execute(cfg['preStm']['cycle']['getAliveCnt'])
        result = con.fetchall()

        if (len(result) >= 2):
            killed = result[0][1] - 1
            alive = result[1][1]

        con.execute(cfg['preStm']['cycle']['getRoleCnt'])
        result = con.fetchall()

        if (len(result) == 4):
            bad = result[1][1] + result[2][1]
            good = result[0][1] + result[3][1]

        con.execute("COMMIT;")
        item.reply(cfg['reply']['getSts'][0][0].format(cfg['reply']['getSts'][1][state], mode[curCycle % 2], day, round, role, cfg['reply']['digupUserBody'][1][user], alive, good, bad, killed, alive + killed))
    except mysql.connector.Error as err:
        print("EXCEPTION {}".format(err))
        con.close()
        os._exit(-1)

def showHelp(item, cfg):
    item.reply(cfg['reply']['showHelp'])

def showRules(item, cfg):
    item.reply(cfg['reply']['showRules'])

def cycle(item, reddit, sub, con, cfg, curCycle):
    round = curCycle + 1
    nextRound = round + 1
    day = int(math.ceil(nextRound/2))
    alive = 0
    killed = 0
    good = 0
    bad = 0
    mode = {
    0: "Day",
    1: "Night"
    }

    random.seed(time.time())

    try:
        con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "curCycle incremented to {}".format(nextRound)))

        con.execute(cfg['preStm']['cycle']['resetInactive'])
        con.execute(cfg['preStm']['cycle']['incrementInactive'])
        con.execute(cfg['preStm']['cycle']['resetComment'])
        con.execute(cfg['preStm']['cycle']['getInactive'], (cfg['kickAfter'],))
        result = con.fetchall()
        for row in result:
            sub.flair.delete(reddit.redditor(row[0]))
            reddit.redditor(row[0]).message("You have been kicked!", cfg['reply']['cycle'][2])
            sleep(0.1)

        con.execute(cfg['preStm']['cycle']['removeInactive'])
        con.execute(cfg['preStm']['cycle']['getVotes'])
        result = con.fetchall()

        for row in result:
            con.execute(cfg['preStm']['chkUsr'], (row[0],))
            role = con.fetchall()
            con.execute(cfg['preStm']['cycle']['getVoteTarget'], (row[0],))
            target = con.fetchall()

            if ((len(role) >= 1) and (len(target) >= 1)):
                if (role[0][1] == "ANALYST") or (role[0][1] == "HANDLER"):
                    continue

                con.execute(cfg['preStm']['cycle']['getVoters'], (row[0],row[0]))
                list = con.fetchall()

                for user in list:
                    if (target[0][0] == user[0][0]):
                        print("success")
                        con.execute(cfg['preStm']['log'], (time.time(), target[0][0], "{} has escaped their hit".format(target[0][0])))
                        con.execute(cfg['preStm']['cycle']['voteEscaped'], (row[0],))
                        con.execute("COMMIT;")

                        reddit.redditor(target[0]).message("You have escaped!", cfg['reply']['cycle'][3])
                        print("  > {} escaped".format(target[0]))

        con.execute(cfg['preStm']['cycle']['killPlayer'], (curCycle, cfg['voteThreshold']))

        con.execute(cfg['preStm']['cycle']['getAliveCnt'])
        result = con.fetchall()

        if (len(result) >= 2):
            killed = result[0][1] - 1
            alive = result[1][1]

        print("\nAlive: {} | Killed {}".format(alive,killed))

        con.execute(cfg['preStm']['cycle']['getRoleCnt'])
        result = con.fetchall()

        if (len(result) == 4):
            bad = result[1][1] + result[2][1]
            good = result[0][1] + result[3][1]

        for row in result:
            print("{} {} still alive".format(row[1], row[0]))

        print("MI6 remaining: {}".format(good))
        print("The Twelve remaining: {}".format(bad))

        con.execute(cfg['preStm']['cycle']['getDead'], (cfg['voteThreshold'],))
        result = con.fetchall()
        for row in result:
            killedMe = ""
            con.execute(cfg['preStm']['cycle']['getKilledMe'], (row[0],))
            r = con.fetchall()

            for v in r:
                killedMe += "* u/{}\n".format(r[0][0])

            random.seed(time.time())
            n = random.randint(0,len(cfg['deathMsg']) - 1)
            sub.flair.set(reddit.redditor(row[0]), text=cfg['flairs']['dead'].format(row[1], cfg['deathMsg'][n],day), flair_template_id=cfg['flairID']['dead'])
            reddit.redditor(row[0]).message("You have been killed!", cfg['reply']['cycle'][0].format(cfg['deathMsg'][n], day, killedMe, alive, good, bad, killed, alive + killed))
            sleep(0.1)

        con.execute(cfg['preStm']['cycle']['getAlive'])
        result = con.fetchall()
        for row in result:
            sub.flair.set(reddit.redditor(row[0]), text=cfg['flairs']['alive'].format(day), flair_template_id=cfg['flairID']['alive'])
            sleep(0.1)

        con.execute("TRUNCATE TABLE VoteCall");
        con.execute("COMMIT;")

        comment = reddit.submission(id=cfg['targetPost']).reply(cfg['sticky']['cycle'].format(mode[round % 2], day, nextRound, alive, good, bad, killed, alive + killed))
        comment.mod.distinguish(how='yes', sticky=True)
        if (item.author.name != "*SELF*"): item.reply("**Moved to cycle {} (Round: {})**".format(round, nextRound))
        print("Moved to cycle {}\n".format(str(nextRound)))

        return round
    except mysql.connector.Error as err:
        print("EXCEPTION {}".format(err))
        con.close()
        os._exit(-1)

def endGame(item, reddit, sub, con, cfg, curCycle):
    round = curCycle + 1
    day = int(math.ceil(round/2))
    alive = -1
    killed = -1
    good = -1
    bad = -1
    winner = ""

    con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "Game Ended"))
    con.execute(cfg['preStm']['cycle']['resetInactive'])
    con.execute(cfg['preStm']['cycle']['incrementInactive'])
    con.execute(cfg['preStm']['cycle']['resetComment'])
    con.execute(cfg['preStm']['cycle']['getInactive'], (cfg['kickAfter'],))
    result = con.fetchall()
    for row in result:
        sub.flair.delete(reddit.redditor(row[0]))
        reddit.redditor(row[0]).message("You have been kicked!", cfg['reply']['cycle'][2])
        sleep(0.1)

    con.execute(cfg['preStm']['cycle']['getAliveCnt'])
    result = con.fetchall()

    if (len(result) >= 2):
        killed = result[0][1] - 1
        alive = result[1][1]


    print("\nAlive: {} | Killed {}".format(alive,killed))

    con.execute(cfg['preStm']['cycle']['getRoleCnt'])
    result = con.fetchall()

    if (len(result) == 4):
        bad = result[1][1] + result[2][1]
        good = result[0][1] + result[3][1]

    con.execute(cfg['preStm']['getDead'])
    result = con.fetchall()
    for row in result:
        reddit.redditor(row[0]).message("The game has ended!", cfg['reply']['gameEnd'].format(cfg['sub'], cfg['targetPost']))
        sleep(0.1)

    con.execute(cfg['preStm']['cycle']['getAlive'])
    result = con.fetchall()

    for row in result:
        reddit.redditor(row[0]).message("The game has ended!", cfg['reply']['gameEnd'])
        sub.flair.set(reddit.redditor(row[0]), text=cfg['flairs']['survived'].format(row[1], day), flair_template_id=cfg['flairID']['alive'])
        sleep(0.1)

    con.execute("COMMIT;")

    if (good > bad):
        winner = "MI6"
    else:
        winner = "The Twelve"

    comment = reddit.submission(id=cfg['targetPost']).reply(cfg['sticky']['end'].format(winner, alive, killed))
    comment.mod.distinguish(how='yes', sticky=True)
    print("Game Ended")

def broadcast(item, reddit, con, cfg):
    pattern = re.search("^!BROADCAST\s([\s\w\d!@#$%^&*()_+{}|:\"<>?\-=\[\]\;\',./’]+)", item.body)
    msg = pattern.group(1)

    try:
        if (item.author.name not in cfg['adminUsr']):
            con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "ATTEMPTED ADMIN COMMAND: announce"))
            con.execute("COMMIT;")
            return
        else:
            con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "Annouced Message"))
            con.execute(cfg['preStm']['getAll'])
            result = con.fetchall()

            for row in result:
                reddit.redditor(row[0]).message("Announcement", msg)
                sleep(0.1)

            con.execute("COMMIT;")
    except mysql.connector.Error as err:
        print("EXCEPTION {}".format(err))
        con.close()
        os._exit(-1)

def restart(item, reddit, sub, db, con, cfg):
    item.mark_read()

    try:
        if (item.author.name not in cfg['adminUsr']):
            con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "ATTEMPTED ADMIN COMMAND: restart"))
            con.execute("COMMIT;")
            return
        else:
            con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "REMOTE RESTART"))
            con.execute(cfg['preStm']['restart'])
            con.execute("SELECT `username` FROM Mafia")
            result = con.fetchall()
            curPos = 0

            for row in result:
                if (curPos >= len(cfg['roles'][0])):
                    curPos = 0

                random.seed(time.time())
                if ((curPos == 0) or (curPos == 1)):
                    loc = cfg['location'][0][random.randint(0, len(cfg['location'][0]) - 1)]
                else:
                    loc = cfg['location'][1][random.randint(0, len(cfg['location'][1]) - 1)]

                con.execute(cfg['preStm']['replaceUser'], (time.time(), row[0], cfg['roles'][0][curPos], loc))
                reddit.redditor(row[0]).message("A new game is starting", cfg['reply']['newGame'].format(row[0], cfg['roles'][0][curPos]))
                curPos += 1
                sub.flair.set(row[0], text=cfg['flairs']['alive'].format(1), flair_template_id=cfg['flairID']['alive'])
                sleep(0.1)

            con.execute("TRUNCATE TABLE VoteCall;");
            con.execute("COMMIT;")

            comment = reddit.submission(id=cfg['targetPost']).reply(cfg['sticky']['restart'])
            comment.mod.distinguish(how='yes', sticky=True)
            save(0, 0, 0)

            if (item.author.name != "*SELF*"): item.reply("**Resetting Game**")
            print("REMOTE RESTART RECEIVED")
            con.close()
            os._exit(1)
    except mysql.connector.Error as err:
        print("EXCEPTION {}".format(err))
        con.close()
        os._exit(-1)

def reset(item, reddit, sub, db, con, cfg):
    item.mark_read()

    try:
        if (item.author.name not in cfg['adminUsr']):
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
            comment.mod.distinguish(how='yes', sticky=True)
            save(0, 0, 0)

            if (item.author.name != "*SELF*"): item.reply("**Resetting Game**")
            print("REMOTE RESET RECEIVED")
            con.close()
            os._exit(1)
    except mysql.connector.Error as err:
        print("EXCEPTION {}".format(err))
        con.close()
        os._exit(-1)

def halt(item, reddit, db, con, cfg):
    item.mark_read()

    try:
        if (item.author.name not in cfg['adminUsr']):
            con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "ATTEMPTED ADMIN COMMAND: halt"))
            con.execute("COMMIT;")
            return
        else:
            con.execute(cfg['preStm']['log'], (item.created_utc, item.author.name, "REMOTE HALT"))
            con.execute("COMMIT;")

            comment = reddit.submission(id=cfg['targetPost']).reply(cfg['sticky']['halt'])
            comment.mod.distinguish(how='yes', sticky=True)

            if (item.author.name != "*SELF*"): item.reply("**Stopping Game**")
            print("REMOTE HALT RECEIVED")
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
        print("\nQuitting")
        sys.exit(1)

    signal.signal(signal.SIGINT, exit_gracefully)

if __name__ == "__main__":
    original_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, exit_gracefully)
    main()
