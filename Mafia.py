#!/usr/bin/pyton3

import datetime
import functools
import json
import os
import math
import mysql.connector
import mysql.connector.pooling
import pickle
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
    with open('init/statements.json') as jsonFile1:
        stm = json.load(jsonFile1)
    with open('data/save.json') as jsonFile2:
        sve = json.load(jsonFile2)
    with open('init/settings.json') as jsonFile3:
        cfg = json.load(jsonFile3)

    exceptCnt = 0
    state = sve['state']
    curCycle = sve['curCycle']

    reddit = praw.Reddit(cfg['reddit']['praw'])
    sub = reddit.subreddit(cfg['reddit']['sub'])
    commentStream = sub.stream.comments(skip_existing=True,pause_after=-1)
    inboxStream = reddit.inbox.stream(pause_after=-1)

    db = mysql.connector.pooling.MySQLConnectionPool(pool_name=None, raise_on_warnings=True, connection_timeout=3600, **cfg['sql'])
    pool = db.get_connection()
    con = pool.cursor(prepared=True)

    idCache = []
    itemCache = {}
    lastCmd = ''

    def log_commit(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            username = '*SELF*'
            command = '!CYCLE'
            utc = time.time();

            try:
                if (item != None):
                    username = item.author.name
                    command = item.body
                    utc = item.created_utc

                result = func(*args, **kwargs)
                pattern = re.search(r'^![\w]{1,}\s([\w\d_\-\s]+)', command)
                readable = time.strftime('%m/%d/%Y %H:%M:%S',  time.gmtime(utc))
                action = ''

                if (result == -1):
                    action += 'FAILED '

                if pattern:
                    action += f'{func.__name__} - {pattern.group(1)}'
                else:
                    action += f'{func.__name__}'

                con.execute(stm['preStm']['log'], (utc, username, action))
                con.execute('COMMIT;')
                print(f'[{readable}] {username}: {action}')
            except mysql.connector.Error as e:
                print(f'SQL EXCEPTION @ {func.__name__} : {args} - {kwargs}\n{e}')
                con.close()
                os._exit(-1)
            return result
        return wrapper

    def game_command(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            pattern = re.search(r'^!([a-z]{4,})\s(?:u/)?([\w\d_\-]+)\s?$', item.body)
            search = ''

            if (state == 0):
                item.reply(stm['err']['notStarted'])
                return -1


            if (func.__name__ != 'burnUser'):
                if pattern:
                    search = pattern.group(2)
                else:
                    item.reply(stm['err']['impFmt'])
                    return -1

            try:
                con.execute(stm['preStm']['chkUsr'], (item.author.name,))
                r = con.fetchall()

                if (len(r) <= 0):
                    item.reply(stm['err']['spec'])
                    return -1

                con.execute(stm['preStm']['chkCmt'], (item.author.name, cfg['commands']['useThreshold']))
                r = con.fetchall()

                if (len(r) <= 0):
                    item.reply(stm['err']['noParticipate'])
                    return -1

                if ((func.__name__ != 'unlockTier') and (func.__name__ != 'burnUser')):
                    con.execute(stm['preStm']['digupUser'], (search,))
                    r = con.fetchall()

                    if (len(r) <= 0):
                        item.reply(stm['err']['notFound'])
                        return -1

                result = func(*args, **kwargs)

            except mysql.connector.Error as e:
                print(f'SQL EXCEPTION @ {func.__name__} : {args} - {kwargs}\n{e}')
                con.close()
                os._exit(-1)
            return result
        return wrapper

    def schdWarn(min=00):
        reddit.submission(id=cfg['reddit']['targetPost']).reply(stm['comment']['actions']['schdWarn'].format(min))
        print(f'Cycle Warning {min}')

    def autoCycle():
        with open('data/save.json') as jsonFile2:
            sve = json.load(jsonFile2)
        curCycle = sve['curCycle']
        cycle(curCycle)
        print(f'Auto Cycle {curCycle}')

    def scheduleJobs():
        schedule.every().day.at(f'{str(cfg["clock"]["hour1"] - 1).zfill(2)}:30').do(schdWarn,min=30)
        schedule.every().day.at(f'{str(cfg["clock"]["hour1"] - 1).zfill(2)}:45').do(schdWarn,min=15)
        schedule.every().day.at(f'{str(cfg["clock"]["hour1"] - 1).zfill(2)}:55').do(schdWarn,min=5)
        schedule.every().day.at(f'{str(cfg["clock"]["hour1"]).zfill(2)}:00').do(autoCycle, curCycle)

        schedule.every().day.at(f'{str(cfg["clock"]["hour2"] - 1).zfill(2)}:30').do(schdWarn,min=30)
        schedule.every().day.at(f'{str(cfg["clock"]["hour2"] - 1).zfill(2)}:45').do(schdWarn,min=15)
        schedule.every().day.at(f'{str(cfg["clock"]["hour2"] - 1).zfill(2)}:55').do(schdWarn,min=5)
        schedule.every().day.at(f'{str(cfg["clock"]["hour2"]).zfill(2)}:00').do(autoCycle, curCycle)

        schedule.every().day.at(f'{str(cfg["clock"]["hour1"] - 1 + 12).zfill(2)}:30').do(schdWarn,min=30)
        schedule.every().day.at(f'{str(cfg["clock"]["hour1"] - 1 + 12).zfill(2)}:45').do(schdWarn,min=15)
        schedule.every().day.at(f'{str(cfg["clock"]["hour1"] - 1 + 12).zfill(2)}:55').do(schdWarn,min=5)
        schedule.every().day.at(f'{str(cfg["clock"]["hour1"] + 12).zfill(2)}:00').do(autoCycle, curCycle)

        schedule.every().day.at(f'{str(cfg["clock"]["hour2"] - 1 + 12).zfill(2)}:30').do(schdWarn,min=30)
        schedule.every().day.at(f'{str(cfg["clock"]["hour2"] - 1 + 12).zfill(2)}:45').do(schdWarn,min=15)
        schedule.every().day.at(f'{str(cfg["clock"]["hour2"] - 1 + 12).zfill(2)}:55').do(schdWarn,min=5)
        schedule.every().day.at(f'{str(cfg["clock"]["hour2"] + 12).zfill(2)}:00').do(autoCycle, curCycle)
        print("Jobs Scheduled")

    @log_commit
    def gameState(state):
        pattern = re.search(r'^!GAMESTATE\s([0-9]{1,1})(\s-[sS])?', item.body)
        setState = int(pattern.group(1))
        silent = pattern.group(2)

        if (item.author.name not in cfg['adminUsr']):
            con.execute(stm['preStm']['log'], (item.created_utc, item.author.name, 'ATTEMPTED ADMIN COMMAND: gameState'))
            return -1
        else:
            if ((setState == 0) and (silent == None)):
                comment = reddit.submission(id=cfg['reddit']['targetPost']).reply(stm['sticky']['pause'])
                comment.mod.distinguish(how='yes', sticky=True)
            elif ((setState == 1) and (silent == None)):
                gameStart()
            elif ((setState == 2) and (silent == None)):
                gameEnd()

            if (item.author.name != '*SELF*'): item.reply(f'**gamestate changed to {setState}**')
            save(setState, curCycle)
            return setState

    @log_commit
    def addUser():
        if (state == 1):
            item.reply(stm['err']['alreadyStarted'])
            return -1

        con.execute(stm['preStm']['chkUsrState'],(item.author.name,))
        r = con.fetchall()

        if(len(r) > 0):
            con.execute(stm['preStm']['addExistingUser'], (cfg['commands']['maxRequests'], item.author.name))
            reddit.submission(id=cfg['reddit']['targetPost']).reply(stm['comment']['actions']['addExistingUser'].format(item.author.name))
        else:
            con.execute(stm['preStm']['addUser'], (item.created_utc, item.author.name))
            reddit.submission(id=cfg['reddit']['targetPost']).reply(stm['comment']['actions']['addUser'].format(item.author.name))

        sub.flair.set(item.author, text=stm['flairs']['alive'].format(1), flair_template_id=cfg['flairID']['alive'])
        item.reply(stm['reply']['addUser'].format(item.author.name))
        setItems(item.author.name, item)

    @log_commit
    def removeUser():
        con.execute(stm['preStm']['removeUser'], (curCycle, item.author.name))
        reddit.submission(id=cfg['reddit']['targetPost']).reply(stm['comment']['actions']['removeUser'].format(item.author.name))
        sub.flair.delete(item.author)
        setItems(item.author.name, None)

    @log_commit
    @game_command
    def voteUser():
        con.execute(stm['preStm']['unlock'][0], (item.author.name,))
        r = con.fetchall()

        if (r[0][0] < cfg['commands']['unlockVote']):
            item.reply(stm['err']['notUnlocked'])
            return -1

    @log_commit
    @game_command
    def burnUser():
        con.execute(stm['preStm']['unlock'][0], (item.author.name,))
        r = con.fetchall()

        if (r[0][0] < cfg['commands']['unlockBurn']):
            item.reply(stm['err']['notUnlocked'])
            return -1

    @log_commit
    @game_command
    def reviveUser():
        con.execute(stm['preStm']['unlock'][0], (item.author.name,))
        r = con.fetchall()

        if (r[0][0] < cfg['commands']['unlockRevive']):
            item.reply(stm['err']['notUnlocked'])
            return -1

    @log_commit
    @game_command
    def digupUser():
        con.execute(stm['preStm']['unlock'][0], (item.author.name,))
        r = con.fetchall()

        if (r[0][0] == 0):
            pass
        elif (r[0][0] == 1):
            pass
        elif (r[0][0] == 2):
            pass
        elif (r[0][0] == 3):
            pass

    @log_commit
    @game_command
    def locateUser():
        con.execute(stm['preStm']['unlock'][0], (item.author.name,))
        r = con.fetchall()

        if (r[0][0] < cfg['commands']['unlockLocate']):
            item.reply(stm['err']['notUnlocked'])
            return -1

    @log_commit
    @game_command
    def requestUser():
        con.execute(stm['preStm']['unlock'][0], (item.author.name,))
        r = con.fetchall()

        if (r[0][0] <= cfg['commands']['unlockRequest']):
            item.reply(stm['err']['notUnlocked'])
            return -1

    @log_commit
    @game_command
    def unlockTier():
        pattern = re.search(r'^![a-z]{4,}\s(?:u/)?([\w\d\-]+)\s?$', item.body)
        code = ''

        if pattern:
            code = pattern.group(1)
        else:
            item.reply(stm['err']['impFmt'])
            return -1

        con.execute(stm['preStm']['unlock'][0], (item.author.name,))
        r = con.fetchall()
        tier = r[0][0]
        team = r[0][1]

        if (tier > len(cfg['codes']) - 1):
            item.reply(stm['err']['maxTier'])
            return -1

        if (cfg['codes'][tier] == code):
            con.execute(stm['preStm']['unlock'][1], (item.author.name,))
            item.reply(stm['reply']['promote'].format(stm['teams'][1][team][tier + 1]))
            reddit.submission(id=cfg['reddit']['targetPost']).reply(stm['comment']['actions']['promote'].format(tier + 2))
        else:
            item.reply(stm['err']['wrongCode'])
            return -1

    @log_commit
    def getList():
        dead = ''
        alive = ''
        deadNum = 0
        aliveNum = 0

        con.execute(stm['preStm']['getList'][0])
        r = con.fetchall()

        for row in r:
            dead += f'\n* u/{row[0]}'
            deadNum += 1

        con.execute(stm['preStm']['getList'][1])
        r = con.fetchall()

        for row in r:
            alive += f'\n* u/{row[0]}'
            aliveNum += 1

        item.reply(stm['reply']['getList'].format(deadNum + aliveNum, deadNum, dead, aliveNum, alive))

    @log_commit
    def getStats():
        team = 'The Spectators'
        tier = 'Spectator'
        loc = 'Nowhere'
        status = 'not playing'
        alive = 0
        killed = 0
        good = 0
        bad = 0

        con.execute(stm['preStm']['chkUsrState'], (item.author.name,))
        r = con.fetchall()

        if (len(r) == 1):
            team = stm['teams'][0][r[0][0]]
            tier = stm['teams'][1][r[0][0]][r[0][1]]
            loc = r[0][2]
            status = stm['alive'][r[0][3]]

        con.execute(stm['preStm']['cycle']['getAliveCnt'])
        result = con.fetchall()
        alive = result[0][0]
        killed = result[0][1]

        con.execute(stm['preStm']['cycle']['getTeamCnt'])
        result = con.fetchall()
        bad = result[0][0]
        good = result[0][1]

        item.reply(stm['reply']['getSts'][0][0].format(stm['reply']['getSts'][1][state], \
         curCycle + 1, tier, team, loc, status, alive, good, bad, killed, alive + killed, \
         cfg['commands']['burnAfter'], cfg['commands']['voteThreshold'], \
         cfg['commands']['voteOneAfter'], cfg['commands']['maxRequests'], cfg['kickAfter']))

    @log_commit
    def showHelp():
        item.reply(stm['reply']['showHelp'])

    @log_commit
    def showRules():
        item.reply(stm['reply']['showRules'])

    @log_commit
    def gameStart():
        con.execute(stm['preStm']['getPlaying'])
        r = con.fetchall()
        players = len(r)
        curPos = 0

        random.seed(time.time())
        random.shuffle(r)

        for row in r:
            team = curPos % 2

            random.seed(time.time())
            loc = stm['location'][team][random.randint(0, len(stm['location'][team]) - 1)]
            con.execute(stm['preStm']['joinTeam'], (team, loc, row[0]))
            getItems(row[0]).reply(stm['reply']['gameStart'].format(stm['teams'][0][team], loc, players, cfg['reddit']['sub'], cfg['reddit']['targetPost']))
            rateLimit(reddit)
            curPos += 1
            sleep(0.2)

        comment = reddit.submission(id=cfg['reddit']['targetPost']).reply(stm['sticky']['start'].format(players))
        comment.mod.distinguish(how='yes', sticky=True)

    @log_commit
    def gameEnd():
        round = curCycle + 1
        con.execute(stm['preStm']['cycle']['resetInactive'])
        con.execute(stm['preStm']['cycle']['incrementInactive'])
        con.execute(stm['preStm']['cycle']['resetComment'])
        con.execute(stm['preStm']['cycle']['getInactive'], (cfg['kickAfter'],))
        r = con.fetchall()

        for row in r:
            sub.flair.delete(reddit.redditor(row[0]))
            reddit.redditor(row[0]).message('You have been kicked!', stm['reply']['cycle'][2])
            sleep(0.2)

        con.execute(stm['preStm']['cycle']['getAliveCnt'])
        r = con.fetchall()
        alive  = r[0][0]
        killed = r[0][1]

        print(f'\nAlive: {alive} | Killed {killed}')

        if (cfg['commands']['allowBotBroadcast'] == 1):
            con.execute(stm['preStm']['getDead'])
            r = con.fetchall()

            for row in r:
                getItems(row[0]).reply(stm['reply']['gameEnd'].format(cfg['reddit']['sub'], cfg['reddit']['targetPost']))
                rateLimit(reddit)
                sleep(0.2)

        con.execute(stm['preStm']['cycle']['getAlive'])
        r = con.fetchall()

        for row in r:
            if (cfg['commands']['allowBotBroadcast'] == 1):
                getItems(row[0]).reply(stm['reply']['gameEnd'].format(cfg['reddit']['sub'], cfg['reddit']['targetPost']))
                rateLimit(reddit)

            sub.flair.set(reddit.redditor(row[0]), text=stm['flairs']['survived'].format(stm['teams'][0][row[1]], round), flair_template_id=cfg['flairID']['alive'])
            sleep(0.2)

        con.execute(stm['preStm']['getWinner'])
        r = con.fetchall()
        bad = r[0][0]
        good = r[0][1]

        if (good == bad):
            winner = 'NOBODY'
        elif (good > bad):
            winner = 'MI6'
        else:
            winner = 'The Twelve'

        comment = reddit.submission(id=cfg['reddit']['targetPost']).reply(stm['sticky']['end'].format(winner, alive, killed))
        comment.mod.distinguish(how='yes', sticky=True)

    @log_commit
    def cycle(curCycle):
        if (state == 0):
            item.reply(stm['err']['notStarted'])
            return -1

        if (item.author.name not in cfg['adminUsr']):
            con.execute(stm['preStm']['log'], (item.created_utc, item.author.name, 'ATTEMPTED ADMIN COMMAND: cycle'))
            return -1

        curCycle = round
        save(state, curCycle)
        return curCycle

    @log_commit
    def broadcast():
        pattern = re.search(r'^!BROADCAST\s([\s\w\d!@#$%^&*()_+{}|:\'<>?\-=\[\]\;\',./’]+)', item.body)
        msg = pattern.group(1)

        if (item.author.name not in cfg['adminUsr']):
            con.execute(stm['preStm']['log'], (item.created_utc, item.author.name, 'ATTEMPTED ADMIN COMMAND: broadcast'))
            return -1

        if (cfg['commands']['allowBotBroadcast'] == 0):
            item.reply('Broadcast Disabled')
            return

        con.execute(stm['preStm']['getAll'])
        r = con.fetchall()
        for row in r:
            getItems(row[0]).reply(msg)
            rateLimit(reddit)
            sleep(0.2)

    @log_commit
    def restart():
        item.mark_read()

        if (item.author.name not in cfg['adminUsr']):
            con.execute(stm['preStm']['log'], (item.created_utc, item.author.name, 'ATTEMPTED ADMIN COMMAND: restart'))
            return -1

        con.execute(stm['preStm']['restart'])
        con.execute('TRUNCATE TABLE VoteCall;');
        con.execute('COMMIT;')
        comment = reddit.submission(id=cfg['reddit']['targetPost']).reply(stm['sticky']['restart'])
        comment.mod.distinguish(how='yes', sticky=True)
        save(0, 0)

        if (item.author.name != '*SELF*'): item.reply('**Restarting Game**')
        print('REMOTE RESTART RECEIVED')
        con.close()
        os._exit(1)

    @log_commit
    def reset():
        item.mark_read()

        if (item.author.name not in cfg['adminUsr']):
            con.execute(stm['preStm']['log'], (item.created_utc, item.author.name, 'ATTEMPTED ADMIN COMMAND: reset'))
            return -1

        con.execute('SELECT `username` FROM Mafia')
        r = con.fetchall()

        for row in r:
            sub.flair.delete(row[0])

        con.execute('TRUNCATE TABLE Mafia;');
        con.execute('TRUNCATE TABLE VoteCall;');
        con.execute(stm['preStm']['log'], (item.created_utc, item.author.name, 'reset'))
        con.execute('COMMIT;')
        comment = reddit.submission(id=cfg['reddit']['targetPost']).reply(stm['sticky']['reset'])
        comment.mod.distinguish(how='yes', sticky=True)
        save(0, 0)

        try:
            os.remove('data/items.pickle')
        except:
            pass

        if (item.author.name != '*SELF*'): item.reply('**Resetting Game**')
        print('REMOTE RESET RECEIVED')
        con.close()
        os._exit(1)

    @log_commit
    def halt():
        item.mark_read()

        if (item.author.name not in cfg['adminUsr']):
            con.execute(stm['preStm']['log'], (item.created_utc, item.author.name, 'ATTEMPTED ADMIN COMMAND: halt'))
            return -1

        comment = reddit.submission(id=cfg['reddit']['targetPost']).reply(stm['sticky']['halt'])
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

    scheduleJobs()

    print(f'Connected as {str(reddit.user.me())}')
    print(f'Database Connections: {len(conStat)}')
    print(f'state: {state}')
    print(f'curCycle: {curCycle} (Cycle: {curCycle + 1})')
    print('______')

    while True:
        if (state == 1):
            schedule.run_pending()

        try:
            for comment in commentStream:
                if comment is None:
                    break

                if ((comment.submission.id == cfg['reddit']['targetPost']) and (comment.id not in idCache)):
                    if (len(idCache) > 1000):
                        idCache = []

                    if(re.search(r'^!(join|leave|vote|digup|rules|help|stats)', comment.body)):
                        comment.reply(stm['err']['notPM'])

                    idCache.append(comment.id)
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

                if (re.search(r'^!join', item.body)):
                    addUser()
                elif (re.search(r'^!leave', item.body)):
                    removeUser()
                elif (re.search(r'^!vote', item.body)):
                    voteUser()
                elif (re.search(r'^!burn$', item.body)):
                    burnUser()
                elif (re.search(r'^!revive', item.body)):
                    reviveUser()
                elif (re.search(r'^!digup', item.body)):
                    digupUser()
                elif (re.search(r'^!locate', item.body)):
                    locateUser()
                elif (re.search(r'^!request', item.body)):
                    requestUser()
                elif (re.search(r'^!unlock', item.body)):
                    unlockTier()
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
                elif (re.search(r'^!CYCLE', item.body)):
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
                    item.reply(stm['err']['unkCmd'])

                item.mark_read()
                lastCmd = item.body.strip()

        except Exception as e:
            traceback.print_exc()
            exceptCnt += 1
            print(f'Exception #{exceptCnt}\nSleeping for {60 * exceptCnt} seconds')
            sleep(60 * exceptCnt)

    con.close()

def rateLimit(reddit):
    limits = json.loads(str(reddit.auth.limits).replace("'", "\""))

    if (limits['remaining'] < 10):
        reset = (limits["reset_timestamp"] + 10) - time.time()
        print(f'Sleeping for: {reset} seconds')
        print(time.strftime('%m/%d/%Y %H:%M:%S',  time.gmtime(limits["reset_timestamp"])))
        comment = reddit.submission(id=cfg['reddit']['targetPost']).reply(stm['sticky']['rateLimit'].format(reset))
        comment.mod.distinguish(how='yes', sticky=True)
        sleep(reset)

def save(state, curCycle):
    with open('data/save.json', 'r+') as jsonFile2:
        tmp = json.load(jsonFile2)
        tmp['state'] = int(state)
        tmp['curCycle'] = int(curCycle)
        jsonFile2.seek(0)
        json.dump(tmp, jsonFile2)
        jsonFile2.truncate()

def setItems(k, v):
    try:
        with open('data/items.pickle', 'rb') as itemsFile:
            tmp = pickle.load(itemsFile)

            if v == None:
                tmp.pop(k, None)
            else:
                tmp[k] = v

            pickle.dump(tmp, itemsFile)
    except Exception as e:
        tmp = {}

        if v == None:
            tmp.pop(k, None)
        else:
            tmp[k] = v

        pickle.dump(tmp, open('data/items.pickle', 'wb'))

def getItems(k):
    try:
        with open('data/items.pickle', 'rb') as itemsFile:
            tmp = pickle.load(itemsFile)
            return tmp[k]
    except Exception as e:
        tmp = {}
        pickle.dump(tmp, open('data/items.pickle', 'wb'))
        return None

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
