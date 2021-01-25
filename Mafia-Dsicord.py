#!/usr/bin/pyton3

import asyncio
import datetime
import discord
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

from discord.ext import commands
from discord.utils import get
from mysql.connector import errorcode
from mysql.connector.cursor import MySQLCursorPrepared
from random import randrange
from time import sleep

with open('init/discord_statements.json') as jsonFile1:
    stm = json.load(jsonFile1)
with open('data/save.json') as jsonFile2:
    sve = json.load(jsonFile2)
with open('init/discord_settings.json') as jsonFile3:
    cfg = json.load(jsonFile3)

exceptCnt = 0
state = sve['state']
curCycle = sve['curCycle']

db = mysql.connector.pooling.MySQLConnectionPool(pool_name=None, raise_on_warnings=True, connection_timeout=3600, **cfg['sql'])
pool = db.get_connection()
con = pool.cursor(prepared=True)

bot = commands.Bot(command_prefix=cfg['discord']['cmdPrefix'])
bot.remove_command('help')

def checkUser(ctx):
    guild = bot.get_guild(cfg['discord']['guild'])
    dead = str(get(guild.roles, id=cfg['discord']['roles']['dead']));
    userID = ctx.message.author.id

    if guild.get_member(userID) is None:
        return False

    for role in guild.get_member(userID).roles:
        if (role.name == dead):
            raise commands.CommandError(message='Dead')

    try:
        con.execute(stm['preStm']['chkCmt'], (userID, cfg['commands']['useThreshold']))
        r = con.fetchall()

        if (len(r) <= 0):
            raise commands.CommandError(message='Inactive')
    except mysql.connector.Error:
        raise commands.CommandError(message='ConLos')

    return true


@bot.event
async def on_ready():
    print("Bot Started")

@bot.event
async def on_command(ctx):
    try:
        con.execute(stm['preStm']['log'], (time.time(), ctx.message.author.id, ctx.message.content[2:27]))
        con.execute('COMMIT;')
    except mysql.connector.Error as e:
        print(f'SQL EXCEPTION {e}')
        con.close()
        await client.change_presence(status=discord.Status.dnd, activity=discord.Game(name=' has stopped. Check DB.'))

@bot.command(name='ping',pass_context=True)
async def ping(ctx):
    await ctx.message.channel.send("Pong!")

@bot.command(pass_context=True)
@commands.guild_only()
async def join(ctx):
    gameCh = bot.get_channel(cfg['discord']['channels']['game'])
    author = ctx.message.author

    if state == 1:
        raise commands.CommandError(message='Started')

    con.execute(stm['preStm']['chkUsrState'],(author.id,))
    r = con.fetchall()

    if(len(r) > 0):
        con.execute(stm['preStm']['addExistingUser'], (cfg['commands']['maxRequests'], author.id))
        await author.add_roles( get(ctx.guild.roles, id=cfg['discord']['roles']['alive']))
        await gameCh.send(stm['comment']['actions']['addExistingUser'].format(author.id))
    else:
        con.execute(stm['preStm']['addUser'], (time.time(), author.id))
        await author.add_roles(get(ctx.guild.roles, id=cfg['discord']['roles']['alive']))
        await gameCh.send(stm['comment']['actions']['addUser'].format(author.id))

    if get(ctx.guild.roles, id=cfg['discord']['roles']['dead']) in author.roles:
        await author.remove_roles(get(ctx.guild.roles, id=cfg['discord']['roles']['dead']))

@bot.command(pass_context=True)
@commands.has_any_role(cfg['discord']['roles']['alive'], cfg['discord']['roles']['dead'])
async def leave(ctx):
    gameCh = bot.get_channel(cfg['discord']['channels']['game'])
    author = ctx.message.author

    con.execute(stm['preStm']['removeUser'], (curCycle, author.id))
    await gameCh.send(stm['comment']['actions']['removeUser'].format(author.id))

    if get(ctx.guild.roles, id=cfg['discord']['roles']['alive']) in author.roles:
        await author.remove_roles(get(ctx.guild.roles, id=cfg['discord']['roles']['alive']))

    if get(ctx.guild.roles, id=cfg['discord']['roles']['dead']) in author.roles:
        await author.remove_roles(get(ctx.guild.roles, id=cfg['discord']['roles']['dead']))

# @bot.command(pass_context=True, aliases=['ci', 'check'])
# @commands.dm_only()
# @commands.check(checkUser)
# async def checkin(ctx, target):
#     pass

@bot.command(pass_context=True, aliases=['v', 'kill'])
@commands.dm_only()
@commands.check(checkUser)
async def vote(ctx, target):
    pass

@bot.command(pass_context=True, aliases=['expose'])
@commands.dm_only()
@commands.check(checkUser)
async def burn(ctx, target):
    pass

@bot.command(pass_context=True, aliases=['heal'])
@commands.dm_only()
@commands.check(checkUser)
async def revive(ctx, target):
    pass

@bot.command(pass_context=True, aliases=['dp', 'info'])
@commands.dm_only()
@commands.check(checkUser)
async def digup(ctx, target):
    pass

@bot.command(pass_context=True, aliases=['loc', 'find', 'where'])
@commands.dm_only()
@commands.check(checkUser)
async def locate(ctx, target):
    pass

@bot.command(pass_context=True)
@commands.dm_only()
@commands.check(checkUser)
async def request(ctx, target):
    pass

@bot.command(pass_context=True)
@commands.dm_only()
@commands.check(checkUser)
async def unlock(ctx, code):
    pass

@bot.command(pass_context=True)
@commands.dm_only()
@commands.check(checkUser)
async def convert(ctx, target):
    pass

@bot.command(pass_context=True)
@commands.dm_only()
@commands.check(checkUser)
async def accept(ctx):
    pass

@bot.command(pass_context=True)
async def stats(ctx):
    pass

@bot.command(pass_context=True)
async def help(ctx):
    pass

@bot.command(pass_context=True)
async def rules(ctx):
    pass

@bot.command(pass_context=True)
@commands.has_role('narrator')
async def gamestate(ctx, state: int):
    pass

@bot.command(pass_context=True)
@commands.has_role('narrator')
async def restart(ctx):
    pass

@bot.command(pass_context=True)
@commands.has_role('narrator')
async def reset(ctx):
    pass

@bot.command(pass_context=True)
@commands.has_role('narrator')
async def halt(ctx):
    pass

@bot.event
async def on_message(message):
    await bot.process_commands(message)

    if message.channel.id == cfg['discord']['channels']['game']:
        con.execute(stm['preStm']['comment'], (message.author.id,))
        con.execute('COMMIT;')

@bot.event
async def on_raw_reaction_add(payload):
    channel = bot.get_channel(payload.channel_id)
    msg = await channel.fetch_message(payload.message_id)
    reaction = discord.utils.get(msg.reactions, emoji=payload.emoji)

    if channel.id != cfg['discord']['channels']['game']:
        return

    if payload.emoji.name == 'vote':
        #TODO: vote
        await reaction.remove(payload.member)
        pass
    elif payload.emoji.name == 'burn':
        #TODO: burn
        await reaction.remove(payload.member)
        pass
    elif payload.emoji.name == 'digup':
        #TODO: Lookup
        await reaction.remove(payload.member)
        pass
    elif payload.emoji.name == 'locate':
        #TODO: Locate
        await reaction.remove(payload.member)
        pass

@bot.event
async def on_command_error(ctx, error):

    err = str(error)

    try:
        con.execute(stm['preStm']['log'], (time.time(), ctx.message.author.id, f'{err} - {ctx.message.content[2:27]}'))
        con.execute('COMMIT;')
    except mysql.connector.Error as e:
        print(f'SQL EXCEPTION {e}')
        con.close()
        await client.change_presence(status=discord.Status.dnd, activity=discord.Game(name=' has stopped. Check DB.'))

    if isinstance(error, commands.CommandNotFound):
        await ctx.message.channel.send("Unknown Command")
        return
    elif isinstance(error, commands.PrivateMessageOnly):
        await ctx.message.channel.send(stm['err']['notPM'].format(ctx.message.author.mention))
        await ctx.message.delete()
        return
    elif isinstance(error, (commands.MissingRole, commands.MissingAnyRole)):
        await ctx.message.channel.send(stm['err']['spec'])
        await ctx.message.delete()
        return
    elif err == 'Started':
        await ctx.message.channel.send(stm['err']['alreadyStarted'])
        return
    elif err == 'Inactive':
        await ctx.message.channel.send(stm['err']['noParticipate'])
        return
    elif err == 'Dead':
        await ctx.message.channel.send(stm['err']['spec'])
        return
    elif err == 'ConLos':
        await ctx.message.channel.send(stm['err']['conLos'])
        return
    elif isinstance(error, commands.CheckFailure):
        await ctx.message.channel.send(stm['err']['generic'])
        return
    raise error

bot.run(cfg['discord']['clientID'])
