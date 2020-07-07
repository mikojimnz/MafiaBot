#!/usr/bin/pyton3

import datetime
import functools
import json
import os
import math
import mysql.connector
import mysql.connector.pooling
import praw
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

def main():
    with open('statements.json') as jsonFile1:
        stm = json.load(jsonFile1)
    with open('save.json') as jsonFile2:
        sve = json.load(jsonFile2)
    with open('settings.json') as jsonFile3:
        cfg = json.load(jsonFile3)

    exceptCnt = 0
    state = sve['state']
    curCycle = sve['curCycle']
    curPos = sve['curPos']

    reddit = praw.Reddit(cfg['praw'])
    sub = reddit.subreddit(cfg['sub'])
    commentStream = sub.stream.comments(skip_existing=True,pause_after=-1)
    inboxStream = reddit.inbox.stream(pause_after=-1)

    db = mysql.connector.pooling.MySQLConnectionPool(pool_name=None, raise_on_warnings=True, connection_timeout=3600, **cfg['sql'])
    pool = db.get_connection()
    con = pool.cursor(prepared=True)

    cache = []
    lastCmd = ''

    def log_commit(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                pattern = re.search(r'^![\w]{1,}\s([\w\d_]{1,20})', item.body)
                readable = time.strftime('%m/%d/%Y %H:%M:%S',  time.gmtime(item.created_utc))
                action = ''

                if (result == -1):
                    action += 'FAILED '

                if pattern:
                    action += f'{func.__name__} - {pattern.group(1)}'
                else:
                    action += f'{func.__name__}'

                con.execute(stm['preStm']['log'], (item.created_utc, item.author.name, action))
                con.execute('COMMIT;')
                print(f'[{readable}] {item.author.name}: {action}')
            except mysql.connector.Error as e:
                print(f'SQL EXCEPTION @ {func.__name__} : {args} - {kwargs}\n{e}')
                con.close()
                os._exit(-1)
            return result
        return wrapper

    @log_commit
    def schdWarn(min):
        reddit.submission(id=cfg['targetPost']).reply(stm['sticky']['schdWarn'].format(min))

    @log_commit
    def autoCycle():
        item = type('', (), {})()
        item.author = type('', (), {})()
        item.author.name = '*SELF*'
        item.body = '!CYCLE'
        item.created_utc = time.time()
        cycle(item)
        save(state, curCycle, curPos)

    def scheduleJobs():
        schedule.every().day.at(f'{str(cfg["clock"]["hour1"] - 1).zfill(2)}:30').do(schdWarn,min=30)
        schedule.every().day.at(f'{str(cfg["clock"]["hour1"] - 1).zfill(2)}:45').do(schdWarn,min=15)
        schedule.every().day.at(f'{str(cfg["clock"]["hour1"] - 1).zfill(2)}:55').do(schdWarn,min=5)
        schedule.every().day.at(f'{str(cfg["clock"]["hour1"]).zfill(2)}:00').do(autoCycle)

        schedule.every().day.at(f'{str(cfg["clock"]["hour2"] - 1).zfill(2)}:30').do(schdWarn,min=30)
        schedule.every().day.at(f'{str(cfg["clock"]["hour2"] - 1).zfill(2)}:45').do(schdWarn,min=15)
        schedule.every().day.at(f'{str(cfg["clock"]["hour2"] - 1).zfill(2)}:55').do(schdWarn,min=5)
        schedule.every().day.at(f'{str(cfg["clock"]["hour2"]).zfill(2)}:00').do(autoCycle)

        schedule.every().day.at(f'{str(cfg["clock"]["hour1"] - 1 + 12).zfill(2)}:30').do(schdWarn,min=30)
        schedule.every().day.at(f'{str(cfg["clock"]["hour1"] - 1 + 12).zfill(2)}:45').do(schdWarn,min=15)
        schedule.every().day.at(f'{str(cfg["clock"]["hour1"] - 1 + 12).zfill(2)}:55').do(schdWarn,min=5)
        schedule.every().day.at(f'{str(cfg["clock"]["hour1"] + 12).zfill(2)}:00').do(autoCycle)

        schedule.every().day.at(f'{str(cfg["clock"]["hour2"] - 1 + 12).zfill(2)}:30').do(schdWarn,min=30)
        schedule.every().day.at(f'{str(cfg["clock"]["hour2"] - 1 + 12).zfill(2)}:45').do(schdWarn,min=15)
        schedule.every().day.at(f'{str(cfg["clock"]["hour2"] - 1 + 12).zfill(2)}:55').do(schdWarn,min=5)
        schedule.every().day.at(f'{str(cfg["clock"]["hour2"] + 12).zfill(2)}:00').do(autoCycle)

    @log_commit
    def gameState(state):
        pattern = re.search(r'^!GAMESTATE\s([0-9]{1,1})(\s-s)?', item.body)
        setState = pattern.group(1)
        silent = pattern.group(2)
        players = 0

        if (item.author.name not in cfg['adminUsr']):
            con.execute(stm['preStm']['log'], (item.created_utc, item.author.name, 'ATTEMPTED ADMIN COMMAND: gameState'))
            return -1
        else:
            con.execute(stm['preStm']['getAll'])
            result = con.fetchall()
            players = len(result)

            for row in result:
                if ((setState == '0') and (silent == None) and (cfg['allowBotBroadcast'] == 1)):
                    reddit.redditor(row[0]).message('The game has paused!', stm['reply']['gamePause'])
                elif ((setState == '1') and (silent == None) and (cfg['allowBotBroadcast'] == 1)):
                    reddit.redditor(row[0]).message('The game has started!', stm['reply']['gameStart'].format(cfg['sub'], cfg['targetPost']))
                sleep(0.2)

            if ((setState == '0') and (silent == None)):
                comment = reddit.submission(id=cfg['targetPost']).reply(stm['sticky']['pause'])
                comment.mod.distinguish(how='yes', sticky=True)
            elif ((setState == '1') and (silent == None)):
                comment = reddit.submission(id=cfg['targetPost']).reply(stm['sticky']['start'].format(players))
                comment.mod.distinguish(how='yes', sticky=True)
            elif ((setState == '2') and (silent == None)):
                endGame()

            if (item.author.name != '*SELF*'): item.reply(f'**gamestate changed to {setState}**')
            save(setState, curCycle, curPos)
            return setState

    @log_commit
    def addUser(curPos):
        con.execute(stm['preStm']['chkUsrState'],(item.author.name,))
        result = con.fetchall()

        if(len(result) > 0):
            con.execute(stm['preStm']['addExistingUser'], (cfg['maxRequests'], item.author.name))
            item.reply(stm['reply']['addUser'].format(item.author.name, result[0][0].title(), result[0][1], cfg['sub'], cfg['targetPost']))
            sub.flair.set(item.author, text=stm['flairs']['alive'].format(1), flair_template_id=cfg['flairID']['alive'])
            reddit.submission(id=cfg['targetPost']).reply(f'u/{item.author.name} has rejoined.')
            return curPos
        else:
            if ((curPos >= len(stm['roles'][0]))):
                curPos = 0

        random.seed(time.time())
        if ((curPos == 0) or (curPos == 1)):
            loc = stm['location'][0][random.randint(0, len(stm['location'][0]) - 1)]
        else:
            loc = stm['location'][1][random.randint(0, len(stm['location'][1]) - 1)]

        item.reply(stm['reply']['addUser'].format(item.author.name, stm['roles'][0][curPos], loc, cfg['sub'], cfg['targetPost']))
        sub.flair.set(item.author, text=stm['flairs']['alive'].format(1), flair_template_id=cfg['flairID']['alive'])
        reddit.submission(id=cfg['targetPost']).reply(f'u/{item.author.name} has joined.')

        con.execute(stm['preStm']['addUser'], (item.created_utc, item.author.name, stm['roles'][0][curPos], loc, cfg['maxRequests'], cfg['maxRequests']))
        curPos += 1
        save(state, curCycle, curPos)
        return curPos

    @log_commit
    def removeUser():
        con.execute(stm['preStm']['leave'], (curCycle, item.author.name))
        item.reply(stm['reply']['removeUser'])
        sub.flair.delete(item.author)
        reddit.submission(id=cfg['targetPost']).reply(f'u/{item.author.name} has left.')

    @log_commit
    def voteUser():
        pattern = re.search(r'^!vote\s(u/)?([A-Za-z0-9_]{1,20})', item.body)
        name = ''
        round = curCycle + 1
        day = int(math.ceil(round/2))
        mode = {
        0: 'Day',
        1: 'Night'
        }

        if pattern:
            name = pattern.group(2)
            con.execute(stm['preStm']['chkUsr'], (item.author.name,))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(stm['reply']['err']['spec'])
                return -1

            if ((cfg['allowAllVote'] == 0)):
                if ((str(r[0][1]) == 'HANDLER') or (str(r[0][1]) == 'ANALYST')):
                    item.reply(stm['reply']['err']['role'])
                    return -1

            if ((cfg['allowVoteAnyTime'] == 0)):
                if ((((r[0][1] == 'ASSASSIN') or (r[0][1] == 'HANDLER')) and (curCycle % 2 == 0)) or (((r[0][1] == 'OPERATIVE') or (r[0][1] == 'ANALYST')) and (curCycle % 2 != 0))):
                    item.reply(stm['reply']['err']['cycle'].format(mode[curCycle % 2]))
                    return -1

            con.execute(stm['preStm']['chkCmt'], (item.author.name, cfg['cmtThreshold']))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(stm['reply']['err']['noParticipate'])
                return -1

            con.execute(stm['preStm']['digupUser'], (name,))
            r = con.fetchall()

            if ((len(r) <= 0) or (r[0][1]) == 0):
                item.reply(stm['reply']['err']['notFound'])
                return -1

            con.execute(stm['preStm']['voteUser'], (item.author.name, name, name))
            success = con.rowcount
            item.reply(stm['reply']['voteUser'])

            if (((str(r[0][1]) == 'ASSASSIN') or (str(r[0][1]) == 'OPERATIVE')) and (success > 0)):
                reddit.redditor(name).message('A hit has been put on you!', stm['reply']['hitAlertEsc'].format(name, round))
            elif (success > 0):
                reddit.redditor(name).message('A hit has been put on you!', stm['reply']['hitAlert'].format(name, round))
        else:
            item.reply(stm['reply']['err']['nmFmt'])

    @log_commit
    def burnUser():
        pattern = re.search(r'^!burn', item.body)
        round = curCycle + 1
        day = int(math.ceil(round/2))
        selfRole = ''
        burned = ''
        burnedRole = ''
        side = 0

        if (curCycle <= cfg['allowBurnOn']):
            item.reply(stm['reply']['err']['noBurnYet'])
            return -1

        con.execute(stm['preStm']['chkUsr'], (item.author.name,))
        r = con.fetchall()

        if (len(r) <= 0):
            item.reply(stm['reply']['err']['spec'])
            return -1

        con.execute(stm['preStm']['chkCmt'], (item.author.name, cfg['cmtThreshold']))
        r = con.fetchall()

        if (len(r) <= 0):
            item.reply(stm['reply']['err']['noParticipate'])
            return -1

        con.execute(stm['preStm']['chkBurn'], (item.author.name,))
        r = con.fetchall()

        if (len(r) <= 0):
            item.reply(stm['reply']['err']['burnUsed'])
            return -1

        selfRole = r[0][1]

        if ((selfRole == 'ASSASSIN') or (selfRole == 'HANDLER')):
            side = 0
        else:
            side = 1

        con.execute(stm['preStm']['burn'][side], (item.author.name,))
        r = con.fetchall()

        if (len(r) <= 0):
            item.reply(stm['reply']['err']['noBurnLeft'])
            return -1

        random.seed(time.time())
        rand = random.randint(0, len(r) - 1)
        burned = r[rand][0]
        burnedRole = r[rand][1]

        if ((selfRole == 'ASSASSIN') or (selfRole == 'HANDLER')):
            side = 2
        else:
            side = 3

        con.execute(stm['preStm']['burn'][side])
        r = con.fetchall()

        if (len(r) <= 0):
            item.reply(stm['reply']['err']['noBurnLeft'])
            return -1

        target = r[random.randint(0, len(r) - 1)]

        con.execute(stm['preStm']['burn'][4], (item.author.name,))
        con.execute(stm['preStm']['burn'][5], (burned,))

        n = random.randint(0,len(stm['deathMsg']) - 1)
        sub.flair.set(reddit.redditor(burned), text=stm['flairs']['dead'].format(burnedRole, stm['deathMsg'][n], day), flair_template_id=cfg['flairID']['dead'])
        reddit.redditor(burned).message('You have been burned!', stm['reply']['burnedUser'].format(item.author.name, round))
        item.reply(stm['reply']['burnUser'].format(target[0], target[1]))
        comment = reddit.submission(id=cfg['targetPost']).reply(stm['sticky']['burnUser'].format(item.author.name, burned))

    @log_commit
    def reviveUser():
        pattern = re.search(r'^!revive\s(u/)?([A-Za-z0-9_]{1,20})', item.body)
        name = ''
        round = curCycle + 1
        day = int(math.ceil(round/2))

        if (cfg['allowRevive'] == 0):
            item.reply(stm['reply']['err']['disallowRevive'])
            return -1

        if pattern:
            name = pattern.group(2)
            con.execute(stm['preStm']['chkUsr'], (item.author.name,))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(stm['reply']['err']['spec'])
                return -1

            con.execute(stm['preStm']['chkCmt'], (item.author.name, cfg['cmtThreshold']))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(stm['reply']['err']['noParticipate'])
                return -1

            con.execute(stm['preStm']['revive'][0], (item.author.name,))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(stm['reply']['err']['reviveUsed'])
                return -1

            con.execute(stm['preStm']['revive'][1], (name,))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(stm['reply']['err']['notFound'])
                return -1

            con.execute(stm['preStm']['revive'][2], (item.author.name,))
            con.execute(stm['preStm']['revive'][3], (name,))
            sub.flair.set(reddit.redditor(name), text=stm['flairs']['alive'].format(day), flair_template_id=cfg['flairID']['alive'])
            reddit.redditor(name).message('You have been revived!', stm['reply']['revivedUser'].format(item.author.name))
            item.reply(stm['reply']['reviveUser'].format(name))
            reddit.submission(id=cfg['targetPost']).reply(stm['sticky']['revive'])
        else:
            item.reply(stm['reply']['err']['nmFmt'])

    @log_commit
    def digupUser():
        pattern = re.search(r'^!digup\s(u/)?([A-Za-z0-9_]{1,20})', item.body)
        name = ''
        random.seed(time.time())
        cred = random.randint(25,75)
        role = 0

        if pattern:
            name = pattern.group(2)
            con.execute(stm['preStm']['chkUsr'], (item.author.name,))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(stm['reply']['err']['spec'])
                return -1
            elif ((str(r[0][1]) == 'ASSASSIN') or (str(r[0][1]) == 'OPERATIVE')):
                cred = random.randint(1,25)

            con.execute(stm['preStm']['chkCmt'], (item.author.name, cfg['cmtThreshold']))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(stm['reply']['err']['noParticipate'])
                return -1

            con.execute(stm['preStm']['digupUser'], (name,))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(stm['reply']['err']['notFound'])
                return -1

            if ((cred >= 1) and (cred < 25)):
                if (random.randint(0,7) == 0):
                    role = stm['roles'][1][r[0][0]]
                else:
                    role = (stm['roles'][1][r[0][0]] + random.randint(1,2)) % 4
            elif ((cred >= 25) and (cred < 50)):
                if (random.randint(0,4) == 0):
                    role = stm['roles'][1][r[0][0]]
                else:
                    role = (stm['roles'][1][r[0][0]] + random.randint(1,2)) % 4
            elif ((cred >= 50) and (cred < 75)):
                if (random.randint(0,2) == 0):
                    role = stm['roles'][1][r[0][0]]
                else:
                    role = (stm['roles'][1][r[0][0]] + random.randint(1,2)) % 4
            else:
                role = stm['roles'][1][r[0][0]]

            item.reply(stm['reply']['digupUser'].format(name, stm['reply']['digupUserBody'][0][role], stm['reply']['digupUserBody'][1][r[0][1]], str(cred)))
        else:
            item.reply(stm['reply']['err']['nmFmt'])

    @log_commit
    def locateUser():
        pattern = re.search(r'^!locate\s(u/)?([A-Za-z0-9_]{1,20})', item.body)
        name = ''
        role = 0

        if pattern:
            name = pattern.group(2)
            con.execute(stm['preStm']['chkUsr'], (item.author.name,))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(stm['reply']['err']['spec'])
                return -1

            con.execute(stm['preStm']['chkCmt'], (item.author.name,cfg['cmtThreshold']))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(stm['reply']['err']['noParticipate'])
                return -1

            con.execute(stm['preStm']['locateUser'], (name,))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(stm['reply']['err']['notFound'])
                return -1

            item.reply(stm['reply']['locateUser'].format(name, r[0][0]))
        else:
            item.reply(stm['reply']['err']['nmFmt'])

    @log_commit
    def requestUser():
        pattern = re.search(r'^!request\s(u/)?([A-Za-z0-9_]{1,20})', item.body)
        name = ''

        if pattern:
            name = pattern.group(2)
            con.execute(stm['preStm']['chkUsr'], (item.author.name,))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(stm['reply']['err']['spec'])
                return -1

            con.execute(stm['preStm']['chkCmt'], (item.author.name, cfg['cmtThreshold']))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(stm['reply']['err']['noParticipate'])
                return -1

            con.execute(stm['preStm']['request'][0], (item.author.name,))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply(stm['reply']['err']['noRequestLeft'])
                return -1

            con.execute(stm['preStm']['digupUser'], (name,))
            r = con.fetchall()

            if ((len(r) <= 0) or (r[0][1]) == 0):
                item.reply(stm['reply']['err']['notFound'])
                return -1

            con.execute(stm['preStm']['request'][1], (item.author.name,))
            item.reply(stm['reply']['requestUser'])
            comment = reddit.submission(id=cfg['targetPost']).reply(stm['sticky']['requestUser'].format(name, item.author.name))
        else:
            item.reply(stm['reply']['err']['nmFmt'])

    @log_commit
    def getList():
        dead = ''
        alive = ''
        deadNum = 0
        aliveNum = 0

        con.execute(stm['preStm']['getList'][0])
        result = con.fetchall()

        for row in result:
            if (cfg['allowRevive'] == 1):
                dead += f'\n* u/{row[0].title()}: ???'
            else:
                dead += f'\n* u/{row[0].title()}: {row[1]}'

            deadNum += 1

        con.execute(stm['preStm']['getList'][1])
        result = con.fetchall()

        for row in result:
            alive += f'\n* u/{row[0]}'
            aliveNum += 1

        item.reply(stm['reply']['getList'].format(deadNum + aliveNum, deadNum, dead, aliveNum, alive))

    @log_commit
    def getStats():
        round = curCycle + 1
        day = int(math.ceil((round)/2))
        role = ''
        user = 0
        alive = 0
        killed = 0
        good = 0
        bad = 0
        mode = {
        0: 'Day',
        1: 'Night'
        }

        con.execute(stm['preStm']['digupUser'], (item.author.name,))
        result = con.fetchall()

        if (len(result) == 1):
            role = result[0][0]
            user = result[0][1]
        else:
            role = 'spectator'

        con.execute(stm['preStm']['cycle']['getAliveCnt'])
        result = con.fetchall()
        alive = result[0][0]
        killed = result[0][1]

        if (state > 0):
            con.execute(stm['preStm']['cycle']['getRoleCnt'])
            result = con.fetchall()
            bad = result[0][0]
            good = result[0][1]

        item.reply(stm['reply']['getSts'][0][0].format(stm['reply']['getSts'][1][state], \
            mode[curCycle % 2], day, round, role.title(), stm['reply']['digupUserBody'][1][user], \
            alive, good, bad, killed, alive + killed, stm['reply']['getSts'][2][cfg['allowAllVote']], \
            stm['reply']['getSts'][2][cfg['allowVoteAnyTime']], stm['reply']['getSts'][2][cfg['allowRevive']], \
            cfg['allowBurnOn'], cfg['voteThreshold'], cfg['voteOneAfter'], \
            cfg['maxRequests'], cfg['kickAfter']))

    @log_commit
    def showHelp():
        item.reply(stm['reply']['showHelp'])

    @log_commit
    def showRules():
        item.reply(stm['reply']['showRules'])

    @log_commit
    def cycle(curCycle):
        round = curCycle + 1
        nextRound = round + 1
        day = int(math.ceil(nextRound/2))
        alive = 0
        killed = 0
        good = 0
        bad = 0
        mode = {
        0: 'Day',
        1: 'Night'
        }
        threshold = 1

        random.seed(time.time())

        if (curCycle > cfg['voteOneAfter']):
            threshold = 1
        else:
            threshold = cfg['voteThreshold']

        con.execute(stm['preStm']['cycle']['resetInactive'])
        con.execute(stm['preStm']['cycle']['incrementInactive'])
        con.execute(stm['preStm']['cycle']['resetComment'])
        con.execute(stm['preStm']['cycle']['getInactive'], (cfg['kickAfter'],))
        result = con.fetchall()
        for row in result:
            con.execute(stm['preStm']['log'], (time.time(), row[0], 'Inactive Kick'))
            sub.flair.delete(reddit.redditor(row[0]))
            reddit.redditor(row[0]).message('You have been kicked!', stm['reply']['cycle'][2])
            sleep(0.2)

        con.execute(stm['preStm']['cycle']['removeInactive'], (cfg['kickAfter'],))
        con.execute(stm['preStm']['cycle']['getVotes'])
        result = con.fetchall()

        for row in result:
            con.execute(stm['preStm']['chkUsr'], (row[0],))
            role = con.fetchall()
            con.execute(stm['preStm']['cycle']['getVoteTarget'], (row[0],))
            target = con.fetchall()

            if ((len(role) >= 1) and (len(target) >= 1)):
                if (role[0][1] == 'ANALYST') or (role[0][1] == 'HANDLER'):
                    continue

                con.execute(stm['preStm']['cycle']['getVoters'], (row[0],row[0]))
                list = con.fetchall()

                for user in list:
                    if (target[0][0] == user[0][0]):
                        print('success')
                        con.execute(stm['preStm']['log'], (time.time(), target[0][0], f'{target[0][0]} Escaped'))
                        con.execute(stm['preStm']['cycle']['voteEscaped'], (row[0],))
                        reddit.redditor(target[0]).message('You have escaped!', stm['reply']['cycle'][3])
                        print(f'  > {target[0]} escaped')

        con.execute(stm['preStm']['cycle']['killPlayer'], (curCycle, threshold))
        con.execute(stm['preStm']['cycle']['getAliveCnt'])
        result = con.fetchall()
        alive  = result[0][0]
        killed = result[0][1]

        print(f'\nAlive: {alive} | Killed {killed}')

        con.execute(stm['preStm']['cycle']['getRoleCnt'])
        result = con.fetchall()
        bad = result[0][0]
        good = result[0][1]

        print(f'MI6 remaining: {good}')
        print(f'The Twelve remaining: {bad}')

        con.execute(stm['preStm']['cycle']['getDead'], (threshold,))
        result = con.fetchall()
        for row in result:
            killedMe = ''

            if (cfg['allowVoteAnyTime'] == 1):
                con.execute(stm['preStm']['cycle']['getKilledMe'], (row[0],))
                r = con.fetchall()

                for v in r:
                    killedMe += f'* u/{v[0]}\n'
            else:
                killedMe = 'Hidden for this game mode.'

            random.seed(time.time())
            n = random.randint(0,len(stm['deathMsg']) - 1)

            if (cfg['allowRevive'] == 1):
                sub.flair.set(reddit.redditor(row[0]), text=stm['flairs']['dead'].format('???', stm['deathMsg'][n],day), flair_template_id=cfg['flairID']['dead'])
            else:
                sub.flair.set(reddit.redditor(row[0]), text=stm['flairs']['dead'].format(row[1].title(), stm['deathMsg'][n],day), flair_template_id=cfg['flairID']['dead'])

            reddit.redditor(row[0]).message('You have been killed!', stm['reply']['cycle'][0].format(stm['deathMsg'][n], day, killedMe, alive, good, bad, killed, alive + killed))
            con.execute(stm['preStm']['log'], (time.time(), row[0], 'Killed'))
            print(f'  > {target[0]} killed')
            sleep(0.2)

        con.execute(stm['preStm']['cycle']['getAlive'])
        result = con.fetchall()
        for row in result:
            sub.flair.set(reddit.redditor(row[0]), text=stm['flairs']['alive'].format(day), flair_template_id=cfg['flairID']['alive'])
            sleep(0.2)

        con.execute('TRUNCATE TABLE VoteCall');
        comment = reddit.submission(id=cfg['targetPost']).reply(stm['sticky']['cycle'].format(mode[round % 2], day, nextRound, alive, good, bad, killed, alive + killed))
        comment.mod.distinguish(how='yes', sticky=True)
        
        if (item.author.name != '*SELF*'): item.reply(f'**Moved to cycle {round} (Round: {nextRound})**')
        curCycle = round
        save(state, curCycle, curPos)
        return curCycle

    @log_commit
    def endGame():
        round = curCycle + 1
        day = int(math.ceil(round/2))
        alive = -1
        killed = -1
        good = -1
        bad = -1
        winner = ''

        con.execute(stm['preStm']['cycle']['resetInactive'])
        con.execute(stm['preStm']['cycle']['incrementInactive'])
        con.execute(stm['preStm']['cycle']['resetComment'])
        con.execute(stm['preStm']['cycle']['getInactive'], (cfg['kickAfter'],))
        result = con.fetchall()
        for row in result:
            sub.flair.delete(reddit.redditor(row[0]))
            reddit.redditor(row[0]).message('You have been kicked!', stm['reply']['cycle'][2])
            sleep(0.2)

        con.execute(stm['preStm']['cycle']['getAliveCnt'])
        result = con.fetchall()
        alive  = result[0][0]
        killed = result[0][1]

        print(f'\nAlive: {alive} | Killed {killed}')

        con.execute(stm['preStm']['getWinner'])
        result = con.fetchall()
        good = result[0][0]
        bad = result[0][1]

        con.execute(stm['preStm']['getDead'])
        result = con.fetchall()

        if (cfg['allowBotBroadcast'] == 1):
            for row in result:
                reddit.redditor(row[0]).message('The game has ended!', stm['reply']['gameEnd'].format(cfg['sub'], cfg['targetPost']))
                sleep(0.2)

        con.execute(stm['preStm']['cycle']['getAlive'])
        result = con.fetchall()

        for row in result:
            if (cfg['allowBotBroadcast'] == 1):
                reddit.redditor(row[0]).message('The game has ended!', stm['reply']['gameEnd'])

            sub.flair.set(reddit.redditor(row[0]), text=stm['flairs']['survived'].format(row[1], day), flair_template_id=cfg['flairID']['alive'])
            sleep(0.2)

        if (good == bad):
            winner = 'NOBODY'
        elif (good > bad):
            winner = 'MI6'
        else:
            winner = 'The Twelve'

        comment = reddit.submission(id=cfg['targetPost']).reply(stm['sticky']['end'].format(winner, alive, killed))
        comment.mod.distinguish(how='yes', sticky=True)

    @log_commit
    def broadcast():
        if (cfg['allowBotBroadcast'] == 0):
            item.reply('Broadcast Disabled')
            return

        pattern = re.search(r'^!BROADCAST\s([\s\w\d!@#$%^&*()_+{}|:\'<>?\-=\[\]\;\',./’]+)', item.body)
        msg = pattern.group(1)

        if (item.author.name not in cfg['adminUsr']):
            con.execute(stm['preStm']['log'], (item.created_utc, item.author.name, 'ATTEMPTED ADMIN COMMAND: broadcast'))
            return
        else:
            con.execute(stm['preStm']['getAll'])
            result = con.fetchall()

            for row in result:
                reddit.redditor(row[0]).message('Announcement', msg)
                sleep(0.2)

    @log_commit
    def restart():
        item.mark_read()

        if (item.author.name not in cfg['adminUsr']):
            con.execute(stm['preStm']['log'], (item.created_utc, item.author.name, 'ATTEMPTED ADMIN COMMAND: restart'))
            return
        else:
            con.execute(stm['preStm']['restart'], (cfg['maxRequests'],))
            con.execute('SELECT `username` FROM Mafia')
            result = con.fetchall()
            random.shuffle(result)
            curPos = 2

            for row in result:
                if (curPos >= len(stm['roles'][0])):
                    curPos = 0

                random.seed(time.time())
                if ((curPos == 0) or (curPos == 1)):
                    loc = stm['location'][0][random.randint(0, len(stm['location'][0]) - 1)]
                else:
                    loc = stm['location'][1][random.randint(0, len(stm['location'][1]) - 1)]

                con.execute(stm['preStm']['replaceUser'], (time.time(), row[0], stm['roles'][0][curPos], loc))

                if (cfg['allowBotBroadcast'] == 1):
                    reddit.redditor(row[0]).message('A new game is starting', stm['reply']['newGame'].format(row[0], stm['roles'][0][curPos].title()))

                curPos += 1
                sub.flair.set(row[0], text=stm['flairs']['alive'].format(1), flair_template_id=cfg['flairID']['alive'])
                sleep(0.2)

            con.execute('TRUNCATE TABLE VoteCall;');
            con.execute(stm['preStm']['log'], (item.created_utc, item.author.name, 'restart'))
            con.execute('COMMIT;')
            comment = reddit.submission(id=cfg['targetPost']).reply(stm['sticky']['restart'])
            comment.mod.distinguish(how='yes', sticky=True)
            save(0, 0, 0)

            if (item.author.name != '*SELF*'): item.reply('**Resetting Game**')
            print('REMOTE RESTART RECEIVED')
            con.close()
            os._exit(1)

    @log_commit
    def reset():
        item.mark_read()

        if (item.author.name not in cfg['adminUsr']):
            con.execute(stm['preStm']['log'], (item.created_utc, item.author.name, 'ATTEMPTED ADMIN COMMAND: reset'))
            return
        else:
            con.execute('SELECT `username` FROM Mafia')
            result = con.fetchall()

            for row in result:
                sub.flair.delete(row[0])

            con.execute('TRUNCATE TABLE Mafia;');
            con.execute('TRUNCATE TABLE VoteCall;');
            con.execute(stm['preStm']['log'], (item.created_utc, item.author.name, 'reset'))
            con.execute('COMMIT;')
            comment = reddit.submission(id=cfg['targetPost']).reply(stm['sticky']['reset'])
            comment.mod.distinguish(how='yes', sticky=True)
            save(0, 0, 0)

            if (item.author.name != '*SELF*'): item.reply('**Resetting Game**')
            print('REMOTE RESET RECEIVED')
            con.close()
            os._exit(1)

    @log_commit
    def halt():
        item.mark_read()

        if (item.author.name not in cfg['adminUsr']):
            con.execute(stm['preStm']['log'], (item.created_utc, item.author.name, 'ATTEMPTED ADMIN COMMAND: halt'))
            return
        else:
            comment = reddit.submission(id=cfg['targetPost']).reply(stm['sticky']['halt'])
            comment.mod.distinguish(how='yes', sticky=True)
            con.execute(stm['preStm']['log'], (item.created_utc, item.author.name, 'halt'))
            con.execute('COMMIT;')
            if (item.author.name != '*SELF*'): item.reply('**Stopping Game**')
            print('REMOTE HALT RECEIVED')
            con.close()
            os._exit(1)

    con.execute(stm['preStm']['main'][0])
    con.execute(stm['preStm']['main'][1], (time.time(),))
    con.execute(stm['preStm']['addDummy'])
    con.execute('COMMIT;')
    con.execute('SHOW PROCESSLIST')
    conStat = con.fetchall()

    print(f'Connected as {str(reddit.user.me())}')
    print(f'Database Connections: {len(conStat)}')
    print(f'state: {state}')
    print(f'curCycle: {curCycle} (Cycle: {curCycle + 1})')
    print(f'curPos: {curPos}')
    print('______')

    scheduleJobs()

    while True:
        if (state == 1):
            schedule.run_pending()

        try:
            for comment in commentStream:
                if comment is None:
                    break

                if ((comment.submission.id == cfg['targetPost']) and (comment.id not in cache)):
                    if (len(cache) > 1000):
                        cache = []

                    if(re.search(r'^!(join|leave|vote|digup|rules|help|stats)', comment.body)):
                        comment.reply(stm['reply']['err']['notPM'])

                    cache.append(comment.id)
                    con.execute(stm['preStm']['comment'], (comment.author.name,))
                    con.execute('COMMIT;')

            for item in inboxStream:
                if item is None:
                    break

                if (item.was_comment == True):
                    continue

                if (item.body.strip() == lastCmd):
                    try:
                        con.execute('RESET QUERY CACHE;')
                    except:
                        pass

                if ((re.search(r'^!join', item.body)) and (curCycle <= cfg['allowJoinUptTo'])):
                    curPos = addUser(curPos)
                elif (re.search(r'^!leave', item.body)):
                    removeUser()
                elif ((re.search(r'^!vote', item.body)) and (state == 1)):
                    voteUser()
                elif ((re.search(r'^!burn$', item.body)) and (state == 1)):
                    burnUser()
                elif ((re.search(r'^!revive', item.body)) and (state == 1)):
                    reviveUser()
                elif ((re.search(r'^!digup', item.body)) and (state == 1)):
                    digupUser()
                elif ((re.search(r'^!locate', item.body)) and (state == 1)):
                    locateUser()
                elif ((re.search(r'^!request', item.body)) and (state == 1)):
                    requestUser()
                elif ((re.search(r'^!list', item.body))):
                    getList()
                elif (re.search(r'^!stats', item.body)):
                    getStats()
                elif (re.search(r'^!help', item.body)):
                    showHelp()
                elif (re.search(r'^!rules', item.body)):
                    showRules()
                elif (re.search(r'^!GAMESTATE', item.body)):
                    state = gameState(state)
                elif ((re.search(r'^!CYCLE', item.body)) and (state == 1)):
                    cycle = cycle(curCycle)
                elif (re.search(r'^!BROADCAST', item.body)):
                    broadcast()
                elif (re.search(r'^!RESTART', item.body)):
                    restart()
                elif (re.search(r'^!RESET', item.body)):
                    reset()
                elif (re.search(r'^!HALT', item.body)):
                    halt()
                else:
                    item.reply(stm['reply']['err']['unkCmd'][0][0].format(stm['reply']['err']['unkCmd'][1][state]))

                item.mark_read()
                lastCmd = item.body.strip()

        except Exception as e:
            traceback.print_exc()
            exceptCnt += 1
            print(f'Exception #{exceptCnt}\nSleeping for {60 * exceptCnt} seconds')
            sleep(60 * exceptCnt)

    con.close()

def save(state, curCycle, curPos):
    with open('save.json', 'r+') as jsonFile2:
        tmp = json.load(jsonFile2)
        tmp['state'] = int(state)
        tmp['curCycle'] = int(curCycle)
        tmp['curPos'] = int(curPos)
        jsonFile2.seek(0)
        json.dump(tmp, jsonFile2)
        jsonFile2.truncate()

def exit_gracefully(signum, frame):
    signal.signal(signal.SIGINT, original_sigint)

    try:
        if input('\nDo you really want to quit? (y/n)> ').lower().startswith('y'):
            sys.exit(1)
    except KeyboardInterrupt:
        print('\nQuitting')
        sys.exit(1)

    signal.signal(signal.SIGINT, exit_gracefully)

if __name__ == '__main__':
    original_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, exit_gracefully)
    main()
