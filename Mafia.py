#!/usr/bin/pyton3

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
    reddit = praw.Reddit('DozenIncBOT')
    ke = reddit.subreddit("SomethingsNotRight")

    dbConfig = {
    'user': 'dummy',
    'password': '1234',
    'host': '127.0.0.1',
    'port': '3306',
    'database': 'Reddit',
    'raise_on_warnings': True,
    'connection_timeout': 3600
    }
    db = mysql.connector.pooling.MySQLConnectionPool(pool_name = None, **dbConfig)
    pool = db.get_connection()
    con = pool.cursor(prepared=True)
    con.execute("SET SQL_SAFE_UPDATES = 0;")
    con.execute("INSERT INTO Log (`utc`,`username`,`action`) VALUES ('{}', 'root', 'Game Initalized');".format(time.time()))
    con.execute("COMMIT;")
    con.execute("SHOW PROCESSLIST")
    conStat = con.fetchall()

    gameState = 0
    curCycle = 0
    stateReply = ["has not yet started.", "has already started."]

    print("Connected as " + str(reddit.user.me()))
    print("Database Connections: ")
    for row in conStat:
        print(row[0])
    print("______")

    while True:
        for item in reddit.inbox.stream():
            if ((re.search('!join', item.body)) and (gameState == 0)):
                addUser(item, ke, con)
            elif ((re.search('!leave', item.body)) and (gameState == 0)):
                removeUser(item, ke, con)
            elif ((re.search('!vote', item.body)) and (gameState == 1)):
                voteUser(item, ke, con, curCycle)
            elif ((re.search('!digup', item.body)) and (gameState == 1)):
                digupUser(item, ke, con)
            elif (re.search('!gamestate', item.body)):
                gameState = gamestate(item, gameState)
            elif (re.search('!cycle', item.body)):
                curCycle = cycle(item, curCycle)
            elif (re.search('!RESET', item.body)):
                reset(item, ke, db, con)
            elif (re.search('!HAULT', item.body)):
                hault(item, db, con)
            else:
                item.reply("Invalid Command.\n\nNote: The game " + stateReply[gameState])

            item.mark_read()

    con.close()
    db.close()

def gamestate(item, gameState):
    log = "INSERT INTO Log (`utc`,`username`,`action`) VALUES (%s, %s, %s)"
    pattern = re.search("!gamestate\s([0-9]{1,1})", item.body)
    target = pattern.group(1)

    try:
        if (item.author.name != "goldenninjadragon"):
            con.execute(log, (item.created_utc, item.author.name, "ATTEMPTED ADMIN COMMAND: gameState"))
            con.execute("COMMIT;")
            return
        else:
            con.execute(log, (item.created_utc, item.author.name, "Changed gameState to " + target))
            con.execute("COMMIT;")

            item.reply("**gamestate changed to " + target + "**")
            print("Moving to gamestate " + target)

            return int(target)
    except mysql.connector.Error as err:
        print("EXCEPTION {}".format(err))
        con.close()
        os._exit(-1)

def addUser(item, ke, con):
    log = "INSERT INTO Log (`utc`,`username`,`action`) VALUES (%s, %s, 'Joined Game')"
    inst = "INSERT IGNORE INTO Mafia (`utc`,`username`,`role`) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE `username`=`username`"
    roles = ['ASSASIN', 'HANDLER', 'OPERATIVE', 'ANALYST']
    random.seed(item.author.name)
    curPos = random.randint(0,3)

    try:
        con.execute(log, (item.created_utc, item.author.name))
        con.execute(inst, (item.created_utc, item.author.name, roles[curPos]))
        con.execute("COMMIT;")

        item.author.message("The Twelve vs MI6", "Hello u/"
        + item.author.name + " you have joined the game!"
        + "\n\nYour role is: *" + roles[curPos]
        + "*.\n\nSHHHH!!! Don't tell anyone!"
        + "\n\nYou can leave the game by replying `!leave` to the game thread. **You cannot rejoin once the game has started!**")

        ke.flair.set(item.author, text="Mafia: Alive")

        curPos += 1
        if (curPos >= len(roles)):
            curPos = 0
        print("  > " + item.author.name + " has joined")
    except mysql.connector.Error as err:
        print("EXCEPTION {}".format(err))
        con.close()
        os._exit(-1)

def removeUser(item, ke, con):
    log = "INSERT INTO Log (`utc`,`username`,`action`) VALUES (%s, %s, 'Left Game');"
    leave = "DELETE FROM Mafia WHERE `username`=%s"

    try:
        con.execute(log, (item.created_utc, item.author.name))
        con.execute(leave, (item.author.name,))
        con.execute("COMMIT;")

        item.reply("You have left the game. You can rejoin before the game starts.")
        ke.flair.delete(item.author)
        print("  > " + item.author.name + " has left")
    except mysql.connector.Error as err:
        print("EXCEPTION {}".format(err))
        con.close()
        os._exit(-1)

def voteUser(item, ke, con, curCycle):
    log = "INSERT INTO Log (`utc`,`username`,`action`) VALUES (%s, %s, %s);"
    check = "SELECT `username`,`role` FROM Mafia WHERE `username`=%s AND `alive`=1;"
    vote = "INSERT INTO VoteCall (`username`, `vote`) VALUES(%s, %s) ON DUPLICATE KEY UPDATE `vote`=%s"
    pattern = re.search("!vote\s([A-Za-z0-9_]{1,20})", item.body)
    target = ""

    if pattern:
        target = pattern.group(1)
        try:
            con.execute(check, (item.author.name,))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply("You are a spectator. You cannot vote.")
                return
            elif ((str(r[0][1]) == "HANDLER") or (str(r[0][1]) == "ANALYST")):
                item.reply("You cannot vote in this role.")
                return
            elif (((str(r[0][1]) == "ASSASIN") and (curCycle % 2 != 0)) or ((str(r[0][1]) == "OPERATIVE") and (curCycle % 2 == 0))):
                item.reply("You cannot vote at this time.")
                return

            con.execute(log, (item.created_utc, item.author.name, "Vote: " + target))
            con.execute(vote, (item.author.name, target, target))
            con.execute("COMMIT;")
            item.reply("Your vote has been tallied. You can change your vote until the cycle ends.")
            print("  > " + item.author.name + " has voted to kill " + target)
        except mysql.connector.Error as err:
            print("EXCEPTION {}".format(err))
            con.close()
            os._exit(-1)
    else:
        item.reply("Invalid username. Do not include the `u/` prefix")

def digupUser(item, ke, con):
    log = "INSERT INTO Log (`utc`,`username`,`action`) VALUES (%s, %s, %s);"
    check = "SELECT `username`,`role` FROM Mafia WHERE `username`=%s AND `alive`=1;"
    inv = "SELECT `role`,`alive` FROM Mafia WHERE `username`=%s"
    pattern = re.search("!digup\s([A-Za-z0-9_]{1,20})", item.body)
    target = ""
    cred = random.randint(1,75)
    role = 0
    roles = {
    "ASSASIN": 0,
    "HANDLER": 1,
    "OPERATIVE": 2,
    "ANALYST": 3
    }
    grammar = {
    0: " an Assasin ",
    1: " a Handler ",
    2: " an Operative ",
    3: " an Analyst "
    }
    alive = {
    1: " alive.",
    0: " deceased."
    }

    if pattern:
        target = pattern.group(1)
        try:
            con.execute(check, (item.author.name,))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply("You are a spectator. You cannot investigate.")
                return
            elif ((str(r[0][1]) == "ASSASIN") or (str(r[0][1]) == "OPERATIVE")):
                item.reply("You cannot investigate in this role.")
                return

            con.execute(log, (item.created_utc, item.author.name, "Investigate: " + target))
            con.execute(inv, (target,))
            r = con.fetchall()

            if (len(r) <= 0):
                item.reply("Cannot find user or user is not playing in the game.")
                return

            con.execute("COMMIT;")
            random.seed(time.time())

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

            item.reply("**Intelligence Report**\n\nu/"
            + target + " is believed to be" + grammar[role]
            + "and is currently" + alive[r[0][1]]
            + "\n\n^(This information is believed to be " + str(cred) + "% credible.)")
            print("  > " + item.author.name + " has investgated " + target)
        except mysql.connector.Error as err:
            print("EXCEPTION {}".format(err))
            con.close()
            os._exit(-1)
    else:
        item.reply("Invalid username. Do not include the `u/` prefix")

def cycle(item, curCycle):
    log = "INSERT INTO Log (`utc`,`username`,`action`) VALUES (%s, %s, %s)"
    pattern = re.search("!cycle", item.body)
    target = curCycle + 1

    try:
        if (item.author.name != "goldenninjadragon"):
            con.execute(log, (item.created_utc, item.author.name, "ATTEMPTED ADMIN COMMAND: cycle"))
            con.execute("COMMIT;")
            return
        else:
            con.execute(log, (item.created_utc, item.author.name, "curCycle incremented to " + str(target)))
            con.execute("COMMIT;")

            item.reply("**Moving to cycle " + str(target) + "**")
            print("Moving to cycle " + str(target))

            return target
    except mysql.connector.Error as err:
        print("EXCEPTION {}".format(err))
        con.close()
        os._exit(-1)

def reset(item, ke, db, con):
    log = "INSERT INTO Log (`utc`,`username`,`action`) VALUES (%s, %s, %s)"

    item.mark_read()

    try:
        if (item.author.name != "goldenninjadragon"):
            con.execute(log, (item.created_utc, item.author.name, "ATTEMPTED ADMIN COMMAND: reset"))
            con.execute("COMMIT;")
            return
        else:
            con.execute(log, (item.created_utc, item.author.name, "REMOTE RESET"))
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


def hault(item, db, con):
    log = "INSERT INTO Log (`utc`,`username`,`action`) VALUES (%s, %s, %s)"

    item.mark_read()

    try:
        if (item.author.name != "goldenninjadragon"):
            con.execute(log, (item.created_utc, item.author.name, "ATTEMPTED ADMIN COMMAND: hault"))
            con.execute("COMMIT;")
            return
        else:
            con.execute(log, (item.created_utc, item.author.name, "REMOTE HAULT"))
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
        if input("\nReally quit? (y/n)> ").lower().startswith('y'):
            sys.exit(1)
    except KeyboardInterrupt:
        print("Ok ok, quitting")
        sys.exit(1)

    signal.signal(signal.SIGINT, exit_gracefully)

if __name__ == "__main__":
    original_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, exit_gracefully)
    main()
