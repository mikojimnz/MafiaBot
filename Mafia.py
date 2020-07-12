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
                pattern = re.search(r'^![\w]{1,}\s([\w\d_]{1,20})', command)
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
        setState = pattern.group(1)
        silent = pattern.group(2)

        if (item.author.name not in cfg['adminUsr']):
            con.execute(stm['preStm']['log'], (item.created_utc, item.author.name, 'ATTEMPTED ADMIN COMMAND: gameState'))
            return -1
        else:
            if ((setState == '0') and (silent == None)):
                comment = reddit.submission(id=cfg['reddit']['targetPost']).reply(stm['sticky']['pause'])
                comment.mod.distinguish(how='yes', sticky=True)
            elif ((setState == '1') and (silent == None)):
                gameStart()
            elif ((setState == '2') and (silent == None)):
                gameEnd()

            if (item.author.name != '*SELF*'): item.reply(f'**gamestate changed to {setState}**')
            save(setState, curCycle)
            return setState

    @log_commit
    def addUser():
        con.execute(stm['preStm']['chkUsrState'],(item.author.name,))
        result = con.fetchall()

        if(len(result) > 0):
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
    def voteUser():
        pass

    @log_commit
    def burnUser():
        pass

    @log_commit
    def reviveUser():
        pass

    @log_commit
    def digupUser():
        pass

    @log_commit
    def locateUser():
        pass

    @log_commit
    def requestUser():
        pass

    @log_commit
    def unlockTier():
        pass

    @log_commit
    def getStats():
        pass

    @log_commit
    def showHelp():
        item.reply(stm['reply']['showHelp'])

    @log_commit
    def showRules():
        item.reply(stm['reply']['showRules'])

    @log_commit
    def gameStart():
        con.execute(stm['preStm']['getPlaying'])
        result = con.fetchall()
        players = len(result)
        curPos = 0

        random.seed(time.time())
        random.shuffle(result)

        for row in result:
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

        if (cfg['commands']['allowBotBroadcast'] == 1):
            con.execute(stm['preStm']['getDead'])
            result = con.fetchall()

            for row in result:
                getItems(row[0]).reply(stm['reply']['gameEnd'].format(cfg['reddit']['sub'], cfg['reddit']['targetPost']))
                rateLimit(reddit)
                sleep(0.2)

        con.execute(stm['preStm']['cycle']['getAlive'])
        result = con.fetchall()

        for row in result:
            if (cfg['commands']['allowBotBroadcast'] == 1):
                getItems(row[0]).reply(stm['reply']['gameEnd'].format(cfg['reddit']['sub'], cfg['reddit']['targetPost']))
                rateLimit(reddit)

            sub.flair.set(reddit.redditor(row[0]), text=stm['flairs']['survived'].format(stm['teams'][0][row[1]], round), flair_template_id=cfg['flairID']['alive'])
            sleep(0.2)

        con.execute(stm['preStm']['getWinner'])
        result = con.fetchall()
        bad = result[0][0]
        good = result[0][1]

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
        else:
            if (cfg['commands']['allowBotBroadcast'] == 0):
                item.reply('Broadcast Disabled')
                return

            con.execute(stm['preStm']['getAll'])
            result = con.fetchall()
            for row in result:
                getItems(row[0]).reply(msg)
                rateLimit(reddit)
                sleep(0.2)

    @log_commit
    def restart():
        item.mark_read()

        if (item.author.name not in cfg['adminUsr']):
            con.execute(stm['preStm']['log'], (item.created_utc, item.author.name, 'ATTEMPTED ADMIN COMMAND: restart'))
            return -1
        else:
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
        else:
            con.execute('SELECT `username` FROM Mafia')
            result = con.fetchall()

            for row in result:
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
        else:
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
                        comment.reply(stm['error']['notPM'])

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

                if ((re.search(r'^!join', item.body)) and (state == 0)):
                    addUser()
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
                elif ((re.search(r'^!unlock', item.body)) and (state == 1)):
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
                    item.reply(stm['error']['unkCmd'][0][0].format(stm['error']['unkCmd'][1][state]))

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
