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
    alive = get(guild.roles, id=cfg['discord']['roles']['alive']);
    dead = get(guild.roles, id=cfg['discord']['roles']['dead']);
    userID = ctx.message.author.id

    if guild.get_member(userID) is not None or hasattr(ctx.message.author, 'roles') is False:
        raise commands.CommandError(message='NotInGuild')

    if state != 1:
        raise commands.CommandError(message='NotStarted')

    if dead in ctx.message.author.roles:
        raise commands.CommandError(message='Dead')

    if alive not in ctx.message.author.roles:
        raise commands.CommandError(message='Dead')

    try:
        con.execute(stm['preStm']['chkCmt'], (userID, cfg['commands']['useThreshold']))
        r = con.fetchall()

        if (len(r) <= 0):
            raise commands.CommandError(message='Inactive')
    except mysql.connector.Error:
        raise commands.CommandError(message='ConLos')

    return True

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

@bot.command(pass_context=True, aliases=['v', 'kill'])
@commands.check(checkUser)
async def vote(ctx, target: discord.User = None):
    if target is None:
        await ctx.message.channel.send(stm['err']['notFound'])
        return False

    await ctx.message.delete()

    con.execute(stm['preStm']['unlock'][0], (ctx.message.author.id,))
    r = con.fetchall()

    if (r[0][0] < cfg['commands']['unlockVote']):
        await ctx.message.channel.send(stm['err']['notUnlocked'])
        return False

    con.execute(stm['preStm']['voteUser'], (ctx.message.author.id, target.id))
    success = con.rowcount

    if ((r[0][1] > cfg['commands']['escapeHit']) and (success > 0)):
        await target.send(stm['reply']['hitAlertEsc'].format(target.name, curCycle + 1))
        await ctx.message.author.send(stm['reply']['voteUser'])
    elif (success > 0):
        await target.send(stm['reply']['hitAlert'].format(target.name, curCycle + 1))
        await ctx.message.author.send(stm['reply']['voteUser'])
    else:
        await ctx.message.author.send(stm['reply']['voteUser'])

@bot.command(pass_context=True, aliases=['expose'])
@commands.check(checkUser)
async def burn(ctx, target):
    pass

@bot.command(pass_context=True, aliases=['heal'])
@commands.check(checkUser)
async def revive(ctx, target):
    pass

@bot.command(pass_context=True, aliases=['dp', 'info'])
@commands.check(checkUser)
async def digup(ctx, target):
    pass

@bot.command(pass_context=True, aliases=['loc', 'find', 'where'])
@commands.check(checkUser)
async def locate(ctx, target):
    pass

@bot.command(pass_context=True)
@commands.check(checkUser)
async def request(ctx, target):
    pass

@bot.command(pass_context=True)
@commands.check(checkUser)
async def unlock(ctx, code):
    pass

@bot.command(pass_context=True)
@commands.check(checkUser)
async def convert(ctx, target):
    pass

@bot.command(pass_context=True)
@commands.check(checkUser)
async def accept(ctx):
    pass

@bot.command(pass_context=True)
async def stats(ctx):
    pass

@bot.command(pass_context=True)
async def help(ctx):
    pre = cfg['discord']['cmdPrefix']
    embed = discord.Embed(
        title = 'Help',
        description = f'Command prefix: `{pre}`\n Full information: {stm["help"]["url"]}',
        color = discord.Colour.blue()
    )
    embed.insert_field_at(index=0, name='join', value=stm['help']['commands'][0])
    embed.insert_field_at(index=1, name='leave', value=stm['help']['commands'][1])
    embed.insert_field_at(index=2, name='vote', value=stm['help']['commands'][2])
    embed.insert_field_at(index=3, name='burn', value=stm['help']['commands'][3])
    embed.insert_field_at(index=4, name='revive', value=stm['help']['commands'][4])
    embed.insert_field_at(index=5, name='digup', value=stm['help']['commands'][5])
    embed.insert_field_at(index=6, name='locate', value=stm['help']['commands'][6])
    embed.insert_field_at(index=7, name='request', value=stm['help']['commands'][7])
    embed.insert_field_at(index=8, name='unlock', value=stm['help']['commands'][8])
    embed.insert_field_at(index=9, name='convert', value=stm['help']['commands'][9])
    embed.insert_field_at(index=10, name='accept', value=stm['help']['commands'][10])
    embed.insert_field_at(index=11, name='stats', value=stm['help']['commands'][11])
    embed.insert_field_at(index=12, name='rules', value=stm['help']['commands'][12])
    await ctx.message.channel.send(embed=embed)

@bot.command(pass_context=True)
async def rules(ctx):
    embed = discord.Embed(
        title = 'Rules',
        description = f'Full information: {stm["help"]["url"]}\nStrategy: {stm["help"]["strat"]}',
        color = discord.Colour.blue()
    )
    embed.insert_field_at(index=0, name='#1', value=stm['help']['rules'][0], inline=False)
    embed.insert_field_at(index=1, name='#2', value=stm['help']['rules'][1], inline=False)
    embed.insert_field_at(index=2, name='#3', value=stm['help']['rules'][2], inline=False)
    embed.insert_field_at(index=3, name='#4', value=stm['help']['rules'][3], inline=False)
    embed.insert_field_at(index=4, name='#5', value=stm['help']['rules'][4], inline=False)
    embed.insert_field_at(index=5, name='#6', value=stm['help']['rules'][5], inline=False)
    await ctx.message.channel.send(embed=embed)

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
    elif payload.emoji.name == 'burn':
        #TODO: burn
        await reaction.remove(payload.member)
    elif payload.emoji.name == 'revive':
        #TODO: revive
        await reaction.remove(payload.member)
    elif payload.emoji.name == 'digup':
        #TODO: Lookup
        await reaction.remove(payload.member)
    elif payload.emoji.name == 'locate':
        #TODO: Locate
        await reaction.remove(payload.member)

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
    elif isinstance(error, (commands.MissingRole, commands.MissingAnyRole)):
        await ctx.message.channel.send(stm['err']['spec'])
        await ctx.message.delete()
        return
    elif isinstance(error, commands.errors.BadArgument):
        await ctx.message.channel.send(stm['err']['badArgument'])
        return
    elif err == 'NotInGuild':
        await ctx.message.channel.send(stm['err']['notInGuild'])
        return
    elif err == 'Started':
        await ctx.message.channel.send(stm['err']['alreadyStarted'])
        return
    elif err == 'NotStarted':
        await ctx.message.channel.send(stm['err']['notStarted'])
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
