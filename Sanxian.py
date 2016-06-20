import youtube_dl
import math
import subprocess
import asyncio
import discord
import ujson
import redis
from datetime import timedelta
from key import *


class Sanxian(discord.Client):
    def __init__(self):
        super().__init__()
        self.voice = {}
        self.players = {}
        self.queues = {}
        self.prefixes = {}
        self.channel = {}
        self.commands = [['play', self.enqueue], ['queue', self.show_queue], ['join', self.join_voice], ['rejoin', self.rejoin], ['setnotice', self.set_notices],
                         ['setvoice', self.set_voice], ['q', self.show_queue], ['now playing', self.now_playing], ['np', self.now_playing]]
        rcon = redis.StrictRedis(db='5', encoding='utf-8')
        test = rcon.exists('Prefixes')
        if test:
            self.prefixes = ujson.loads(rcon.get('Prefixes'))
        del rcon

    async def on_message(self, message):
        if message.author.bot or message.author == self.user:
            return
        elif message.content.lower() == 'siwang' and message.author.id == '66257033204080640':
            rcon = redis.StrictRedis(db='5', encoding='utf-8')
            rcon.set('Prefixes', ujson.dumps(self.prefixes))
            await self.logout()
        elif message.content.lower().startswith('saba'):
            if message.content.split()[1].lower().startswith('prefix') and message.channel.permissions_for(message.author).manage_server:
                self.prefixes[message.server.id] = message.content.split(':')[1]
                await self.send_message(message.channel, "Changed server prefix to {}".format(message.content.split(':')[1]))
        else:
            prefix = 'yinyue ' if message.server.id not in self.prefixes else self.prefixes[message.server.id]
            for command in self.commands:
                if message.content.lower().startswith(prefix + command[0]):
                    ret = await command[1](message)
                    if isinstance(ret, str):
                        await self.send_message(message.channel, ret)
                    elif isinstance(ret, list):
                        attempt = "\n".join(ret)
                        if len(attempt) > 2000:
                            for x in ret:
                                await self.send_message(message.channel, x)
                        else:
                            await self.send_message(message.channel, attempt)

    async def enqueue(self, message):
        prefix = 'yinyue ' if message.server.id not in self.prefixes else self.prefixes[message.server.id]
        if ' ' in prefix:
            url = message.content.split()[2]
        else:
            url = message.content.split()[1]
        ytdl = await asyncio.create_subprocess_exec('youtube-dl', '-q', '-s', '--skip-download', '-J', url, stdout=asyncio.subprocess.PIPE)
        await self.send_message(message.channel, "Downloading information on <{}>".format(url))
        stdout, _ = await ytdl.communicate()
        if ytdl.returncode != 0:
            return "That video was not found or could not be downloaded by youtube-dl."
        jsd = ujson.loads(stdout.decode())
        if message.server.id not in self.queues:
            self.queues[message.server.id] = []
        if 'entries' in jsd:  #Playlist
            for x in jsd['entries']:
                if x['duration'] < 900:
                    self.queues[message.server.id].append([x['title'], x['webpage_url'], x['duration']])
            if message.server.id in self.voice and self.voice[message.server.id].is_connected():
                if message.server.id not in self.players and message.server.id in self.voice:
                    data = self.queues[message.server.id].pop(0)
                    self.players[message.server.id] = await self.voice[message.server.id].create_ytdl_player(data[1], after=self.play_next(message.server))
                    self.players[message.server.id].start()
                elif message.server.id in self.players and self.players[message.server.id].is_done():
                    data = self.queues[message.server.id].pop(0)
                    self.players[message.server.id] = await self.voice[message.server.id].create_ytdl_player(data[1], after=self.play_next(message.server))
                    self.players[message.server.id].start()
            return '<{}> linked to a playlist called {} with {} tracks and a playtime of {}.'.format(url, jsd['title'],
                                                                                                             len(jsd['entries']),
                                                                                                             timedelta(seconds=sum([x['duration'] for x in jsd['entries']])))
        else:  #Single video
            if jsd['duration'] > 900:
                return "No songs over 15 minutes."
            self.queues[message.server.id].append([jsd['title'], jsd['webpage_url'], jsd['duration']])
            if message.server.id in self.voice and self.voice[message.server.id].is_connected():
                if message.server.id not in self.players:
                    data = self.queues[message.server.id].pop(0)
                    self.players[message.server.id] = await self.voice[message.server.id].create_ytdl_player(data[1], after=self.play_next(message.server))
                    self.players[message.server.id].start()
                elif message.server.id in self.players and self.players[message.server.id].is_done():
                    data = self.queues[message.server.id].pop(0)
                    self.players[message.server.id] = await self.voice[message.server.id].create_ytdl_player(data[1], after=self.play_next(message.server))
                    self.players[message.server.id].start()
            return '<{}> linked to a video called {} with a playtime of {}.'.format(url, jsd['title'],
                                                                                            timedelta(seconds=jsd['duration']))

    async def show_queue(self, message):
        if message.server.id not in self.queues or not len(self.queues[message.server.id]):
            return "Your server doesn't have a queue."
        messages = []
        if ':' in message.content:  #pagination
            try:
                page = int(message.content.split(":")[1])
            except:
                return "Page needs to be a number."
            for idx, x in enumerate(self.queues[message.server.id][(10*(page-1)):(10*page)]):
                messages.append("{}. {} [{}]".format(idx+1+((page-1)*10), x[0], timedelta(seconds=x[2])))
            messages.append("{} - {} of {}  -  Page {} of {}  -  Use queue:# for pages".format(10*(page-1), 10*page if 10*page < len(self.queues[message.server.id]) else len(self.queues[message.server.id]),
                                                                                               len(self.queues[message.server.id]), page,
                                                                                               math.ceil(len(self.queues[message.server.id]) / 10)))
            return messages
        else:
            for idx, x in enumerate(self.queues[message.server.id][:10]):
                messages.append("{}. {} [{}]".format(idx+1, x[0], x[2]))
            messages.append("1 - {} of {}  -  Page 1 of {}  -  Use queue:# for pages".format(10 if 10 <= len(self.queues[message.server.id]) else len(self.queues[message.server.id]),
                                                                                             len(self.queues[message.server.id]),
                                                                                             math.ceil(len(self.queues[message.server.id])/10)))
            return messages

    async def rejoin(self, message):
        if message.server.id in self.channel and 'voice' in self.channel[message.server.id]:
            self.voice[message.server.id] = await self.join_voice_channel(self.channel[message.server.id]['voice'])
        else:
            return "You need to set the default voice channel to use rejoin. For now use join."

    async def set_voice(self, message):
        if not message.channel.permissions_for(message.author).manage_server:
            return "Permissions not granted"
        prefix = 'yinyue ' if message.server.id not in self.prefixes else self.prefixes[message.server.id]
        if ' ' in prefix:
            name = " ".join(message.content.split()[2:])
        else:
            name = " ".join(message.content.split()[1:])
        vchan = discord.utils.get(message.server.channels, name=name, type=discord.ChannelType.voice)
        if vchan is None:
            return "Couldn't find a voice channel by that name."
        else:
            if message.server.id in self.channel:
                self.channel[message.server.id]['voice'] = vchan
            else:
                self.channel[message.server.id] = {'voice': vchan}
        return "Default voice channel is now {}".format(name)

    async def set_notices(self, message):
        if not message.channel.permissions_for(message.author).manage_server:
            return "Permissions not granted"
        prefix = 'yinyue ' if message.server.id not in self.prefixes else self.prefixes[message.server.id]
        if ' ' in prefix:
            name = " ".join(message.content.split()[2:])
        else:
            name = " ".join(message.content.split()[1:])
        vchan = discord.utils.get(message.server.channels, name=name, type=discord.ChannelType.text)
        if vchan is None:
            return "Couldn't find a voice channel by that name."
        else:
            if message.server.id in self.channel:
                self.channel[message.server.id]['notice'] = vchan
            else:
                self.channel[message.server.id] = {'notice': vchan}
        return "Default now playing notice channel is {}".format(name)

    async def now_playing(self, message):
        if message.server.id in self.players and not self.players[message.server.id].is_done():
            return "{} [{}]".format()

    async def join_voice(self, message):
        if message.server.id in self.voice and self.voice[message.server.id].is_connected() and not message.channel.permissions_for(message.author).manage_server:
            return "I'm already connected to a voice channel."
        prefix = 'yinyue ' if message.server.id not in self.prefixes else self.prefixes[message.server.id]
        if ' ' in prefix:
            channel = " ".join(message.content.split()[2:])
        else:
            channel = " ".join(message.content.split()[1:])
        vchan = discord.utils.get(message.server.channels, name=channel, type=discord.ChannelType.voice)
        if vchan is None:
            return "{} didn't match a voice channel.".format(channel)
        else:
            if message.server.id in self.voice:
                if message.server.id in self.players and self.players[message.server.id].is_playing():
                    self.channel[message.server.id]['voice'] = vchan
                    self.players[message.server.id].pause()
                    await self.voice[message.server.id].move_to(vchan)
                    self.players[message.server.id].resume()
                    return "Moved to a new voice channel. Now in {}. Resuming play.".format(vchan)
                else:
                    self.channel[message.server.id] = {'voice': vchan}
                    await self.voice[message.server.id].move_to(vchan)
                    return "Moved to a new voice channel. Now in {}.".format(vchan)
            else:
                self.voice[message.server.id] = await self.join_voice_channel(vchan)
        if message.server.id in self.queues and len(self.queues[message.server.id]) and message.server.id not in self.players:
            data = self.queues[message.server.id].pop(0)
            self.players[message.server.id] = await self.voice[message.server.id].create_ytdl_player(data[1], after=self.play_next(message.server))
            self.players[message.server.id].start()
            if message.server.id in self.channel and 'notice' in self.channel[message.server.id]:
                await self.send_message(self.channel[message.server.id]['notice'], "Now playing {} [{}]".format(data[0], timedelta(seconds=data[2])))
            else:
                return "Now playing {} [{}]".format(data[0], timedelta(seconds=data[2]))

    def play_next(self, server):
        print("Made it")
        if server.id in self.queues and len(self.queues[server.id]):
            self.loop.create_task(self.new_song(server))

    async def new_song(self, server):
        data = self.queues[server.id].pop(0)
        self.players[server.id] = await self.voice[server.id].create_ytdl_player(data[1], after=self.play_next(server))
        if server.id in self.channel and 'notice' in self.channel[server.id]:
            await self.send_message(self.channel[server.id]['notice'], "Now playing {} [{}]".format(data[0], timedelta(seconds=data[2])))


if __name__ == "__main__":
    Sanxian_Instance = Sanxian()
    Sanxian_Instance.run(bottoken)