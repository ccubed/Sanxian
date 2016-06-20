import youtube_dl
import math
import subprocess
import asyncio
import discord
import ujson
import redis
from datetime import timedelta


class Sanxian(discord.Client):
    def __init__(self):
        super().__init__()
        self.voice = {}
        self.queues = {}
        self.prefixes = {}
        self.commands = []
        rcon = redis.StrictRedis(db='5', encoding='utf-8')
        test = rcon.exists('Prefixes')
        if test:
            self.prefixes = ujson.loads(rcon.get('Prefixes'))
        del rcon

    async def on_message(self, message):
        if message.author.bot or message.author == self.user:
            return
        elif message.content.lower() == 'shinaide' and message.author.id == '66257033204080640':
            rcon = redis.StrictRedis(db='5', encoding='utf-8')
            rcon.set('Prefixes', ujson.dumps(self.prefixes))
            await self.logout()
        elif message.startswith('saba'):
            if message.content.split()[1].startswith('prefix') and message.channel.permissions_for(message.author).manage_server:
                self.prefixes[message.server.id] = message.content.split(':')[1]
                await self.send_message(message.channel, "[Sanxian] Changed server prefix to {}".format(message.content.split(':')[1]))
        else:
            prefix = 'ongaku' if message.server.id not in self.prefixes else self.prefixes[message.server.id]
            for command in self.commands:
                if message.content.lower().startswith(prefix + command[0]):
                    ret = await command[1](message)
                    if isinstance(ret, str):
                        await self.send_message(message.channel, ret)
                    elif isinstance(ret, list):
                        for x in ret:
                            await self.send_message(message.channel, ret)

    async def enqueue(self, message):
        url = message.content.split()[2]
        ytdl = await asyncio.create_subprocess_exec('youtube-dl', '-q', '-s', '--skip-download', '-J', url, stdout=asyncio.subprocess.PIPE)
        await self.send_message(message.channel, "[Sanxian] Downloading information on {}".format(url))
        stdout, _ = await ytdl.communicate()
        if ytdl.retcode != 0:
            return "That video was not found or could not be downloaded by youtube-dl."
        jsd = ujson.loads(stdout.decode())
        if message.server.id not in self.queues:
            self.queues[message.server.id] = []
        if 'entries' in jsd:  #Playlist
            for x in jsd['entries']:
                self.queues[message.server.id].append([x['title'], x['webpage_url'], x['duration']])
            return '[Sanxian] {} linked to a playlist called {} with {} tracks and a playtime of {}.'.format(url, jsd['title'],
                                                                                                             len(jsd['entires']),
                                                                                                             timedelta(seconds=sum([x['duration'] for x in jsd['entries']])))
        else:  #Single video
            self.queues[message.server.id].append([jsd['title'], jsd['webpage_url'], jsd['duration']])
            return '[Sanxian] {} linked to a video called {} with a playtime of {}.'.format(url, jsd['title'],
                                                                                            timedelta(seconds=jsd['duration']))

    async def show_queue(self, message):
        if message.server.id not in self.queues or not len(self.queues[message.server.id]):
            return "[Sanxian] Your server doesn't have a queue."
        messages = []
        if ':' in message.content:  #pagination
            try:
                page = int(message.content.split(":")[1])
            except:
                return "[Sanxian] Page needs to be a number."
            for idx, x in enumerate(self.queues[message.server.id][(10*(page-1)):(10*page)]):
                messages.append("{}. {} [{}]".format(idx, x[0], x[2]))
            messages.append("{} - {} of {}  -  Page {} of {}  -  Use queue # for pages".format(10*(page-1), 10*page,
                                                                                  len(self.queues[message.server.id]), page,
                                                                                  math.ceil(len(self.queues[message.server.id]) / 10)))
            return messages
        else:
            for idx, x in enumerate(self.queues[message.server.id][:10]):
                messages.append("{}. {} [{}]".format(idx, x[0], x[2]))
            messages.append("1 - 10 of {}  -  Page 1 of {}  -  Use queue # for pages".format(len(self.queues[message.server.id]),
                                                                                         math.ceil(len(self.queues[message.server.id])/10)))
            return messages