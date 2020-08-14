"""MIT License

Copyright (c) 2019-2020 PythonistaGuild

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import logging
import time

from typing import Any, Dict, Optional

import discord
from discord.gateway import DiscordWebSocket

from .eqs import Equalizer
from .node import Node
from .track import Track
from . import errors, events


__all__ = ('Player')
__log__ = logging.getLogger(__name__)


class Player(discord.VoiceProtocol):
    """Wavelink Player class.

    Attributes
    ----------
    client: :class:`discord.Client`
        the discord client instance.
    node: :class:`wavelink.node.Node`
        the node the player belongs to.
    channel: discord.VoiceChannel
        the channel the player is connected to.
    volume: int
        the players volume.
    """

    def __init__(self, client: discord.Client, channel: discord.VoiceChannel):
        super().__init__(client, channel)

        node = self.client.wavelink.get_best_node()
        if node is None:
            raise errors.ZeroConnectedNodes('Could not find a node to connect with.')

        self.node: Node = node
        self.node.players[self.guild.id] = self
        self._voice_state: Dict[str, Any] = {}
        self._connected = False

        self.last_update: Optional[float] = None
        self.last_position: Optional[float] = None
        self.position_timestamp: Optional[float] = None

        self.volume = 100
        self._paused = False
        self._track: Optional[Track] = None
        self._equalizer = Equalizer.flat()

    @property
    def guild(self):
        return self.channel.guild

    @property
    def user(self):
        return self.client.user

    @property
    def equalizer(self) -> Equalizer:
        """The currently applied Equalizer."""
        return self._equalizer

    @property
    def eq(self) -> Equalizer:
        """Alias to :func:`equalizer`."""
        return self.equalizer

    @property
    def track(self) -> Optional[Track]:
        return self._track

    @property
    def position(self):
        if not self.is_playing():
            return 0

        if self.is_paused():
            return min(self.last_position, self.track.duration)

        difference = (time.time() * 1000) - self.last_update
        position = self.last_position + difference

        if position > self.track.duration:
            return 0

        return min(position, self.track.duration)

    async def update_state(self, state: Dict[str, Any]):
        state = state['state']

        self.last_update = time.time() * 1000
        self.last_position = state.get('position', 0)
        self.position_timestamp = state.get('time', 0)

    async def on_voice_server_update(self, data: Dict[str, Any]):
        self._voice_state.update({
            'event': data
        })

        await self._dispatch_voice_update()

    async def on_voice_state_update(self, data: Dict[str, Any]):
        self._voice_state.update({
            'sessionId': data['session_id']
        })

        channel_id = data['channel_id']
        if not channel_id:  # We're disconnecting
            self._voice_state.clear()
            return

        self.channel = discord.utils.get(self.guild.channels, id=int(channel_id))
        await self._dispatch_voice_update()

    async def _dispatch_voice_update(self):
        __log__.debug(f'PLAYER | Dispatching voice update:: {self.channel.id}')
        if {'sessionId', 'event'} == self._voice_state.keys():
            await self.node._send(op='voiceUpdate', guildId=str(self.guild.id), **self._voice_state)

    async def hook(self, event) -> None:
        if isinstance(event, (events.TrackEnd, events.TrackException, events.TrackStuck)):
            self._track = None

    def _get_shard_socket(self, shard_id: int) -> DiscordWebSocket:
        if isinstance(self.client, discord.AutoShardedClient):
            try:
                return self.client.shards[shard_id].ws
            except AttributeError:
                return self.client.shards[shard_id]._parent.ws
        else:
            return self.client.ws

    async def connect(self, *, timeout: float, reconnect: bool):
        await self._get_shard_socket(self.guild.shard_id).voice_state(self.guild.id, str(self.channel.id))
        self._connected = True
        __log__.info(f'PLAYER | Connected to voice channel:: {self.channel.id}')

    async def disconnect(self, *, force: bool):
        __log__.info(f'PLAYER | Disconnected from voice channel:: {self.channel.id}')
        await self._get_shard_socket(self.guild.shard_id).voice_state(self.guild.id, None)
        self._connected = False

    async def play(self, track: Track, replace: bool = True, start: int = 0, end: int = 0):
        """|coro|

        Play a WaveLink Track.

        Parameters
        ------------
        track: :class:`Track`
            The :class:`Track` to initiate playing.
        replace: bool
            Whether or not the current track, if there is one, should be replaced or not. Defaults to True.
        start: int
            The position to start the player from in milliseconds. Defaults to 0.
        end: int
            The position to end the track on in milliseconds. By default this always allows the current
            song to finish playing.
        """
        if replace or not self.is_playing():
            self.last_update = 0
            self.last_position = 0
            self.position_timestamp = 0
            self._paused = False
        else:
            return

        no_replace = not replace

        self._track = track

        payload = {'op': 'play',
                   'guildId': str(self.guild.id),
                   'track': track.id,
                   'noReplace': no_replace,
                   'startTime': str(start)
                   }
        if end > 0:
            payload['endTime'] = str(end)

        await self.node._send(**payload)

        __log__.debug(f'PLAYER | Started playing track:: {str(track)} ({self.channel.id})')

    def is_connected(self):
        return self._connected

    def is_playing(self):
        return self.is_connected() and self._track is not None

    def is_paused(self):
        return self._paused

    async def stop(self):
        """|coro|

        Stop the Player's currently playing song.
        """
        await self.node._send(op='stop', guildId=str(self.guild.id))
        __log__.debug(f'PLAYER | Current track stopped:: {str(self.track)} ({self.channel.id})')
        self._track = None

    async def set_pause(self, pause: bool) -> None:
        """|coro|

        Set the players paused state.

        Parameters
        ------------
        pause: bool
            A bool indicating if the player's paused state should be set to True or False.
        """
        await self.node._send(op='pause', guildId=str(self.guild.id), pause=pause)
        self._paused = pause
        __log__.info(f'PLAYER | Set pause:: {self._paused} ({self.channel.id})')

    async def pause(self):
        """|coro|

        Pauses the player if it was playing.
        """
        await self.set_pause(True)

    async def resume(self):
        """|coro|

        Resumes the player if it was paused.
        """
        await self.set_pause(False)

    async def set_volume(self, volume: int):
        """|coro|

        Set the player's volume, between 0 and 1000.

        Parameters
        ------------
        volume: int
            The volume to set the player to.
        """
        self.volume = max(min(volume, 1000), 0)
        await self.node._send(op='volume', guildId=str(self.guild.id), volume=self.volume)
        __log__.debug(f'PLAYER | Set volume:: {self.volume} ({self.channel.id})')

    async def seek(self, position: int = 0):
        """Seek to the given position in the song.

        Parameters
        ------------
        position: int
            The position as an int in milliseconds to seek to. Could be None to seek to beginning.
        """

        await self.node._send(op='seek', guildId=str(self.guild.id), position=position)

    async def change_node(self, node: Optional[Node]):
        """|coro|

        Change the players current :class:`wavelink.node.Node`. Useful when a Node fails or when changing regions.
        The change Node behaviour allows for near seamless fallbacks and changeovers to occur.

        Parameters
        ------------
        Optional[Node]
            The node to change to. If None, the next best available Node will be found.
        """
        client = self.node._client

        if node is not None:
            if node == self.node:
                raise errors.WavelinkException('Player is already on this node.')
        else:
            self.node.close()
            node = client.get_best_node(region=self.node.region, shard_id=self.node.shard_id)
            self.node.open()
            if node is None:
                raise errors.WavelinkException('No Nodes available for changeover.')

        old_node = self.node
        del old_node.players[self.guild.id]
        await old_node._send(op='destroy', guildId=str(self.guild.id))

        self.node = node
        self.node.players[self.guild.id] = self

        if self._voice_state:
            await self._dispatch_voice_update()

        if self._track:
            await self.node._send(op='play', guildId=str(self.guild.id), track=self._track.id, startTime=int(self.position))
            self.last_update = time.time() * 1000

            if self.is_paused():
                await self.node._send(op='pause', guildId=str(self.guild.id), pause=self._paused)

        if self.volume != 100:
            await self.node._send(op='volume', guildId=str(self.guild.id), volume=self.volume)
