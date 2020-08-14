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

import re


__all__ = ('Track', 'TrackPlaylist')


class Track:
    """Wavelink Tack object.

    Attributes
    ------------
    id: str
        The Base64 Track ID.
    info: dict
        The raw track info.
    title: str
        The track title.
    identifier: Optional[str]
        The tracks identifier. could be None depending on track type.
    ytid: Optional[str]
        The tracks YouTube ID. Could be None if ytsearch was not used.
    length:
        The duration of the track.
    duration:
        Alias to length.
    uri: Optional[str]
        The tracks URI. Could be None.
    author: Optional[str]
        The author of the track. Could be None
    is_stream: bool
        Indicated whether the track is a stream or not.
    thumb: Optional[str]
        The thumbnail URL associated with the track. Could be None.
    """

    __slots__ = ('id',
                 'info',
                 'query',
                 'title',
                 'identifier',
                 'ytid',
                 'length',
                 'duration',
                 'uri',
                 'author',
                 'is_stream',
                 'dead',
                 'thumb')

    def __init__(self, id_, info: dict, query: str = None):
        self.id = id_
        self.info = info
        self.query = query

        self.title = info.get('title')
        self.identifier = info.get('identifier')
        self.ytid = self.identifier if re.match(r"^[a-zA-Z0-9_-]{11}$", self.identifier) else None
        self.length = info.get('length')
        self.duration = self.length
        self.uri = info.get('uri')
        self.author = info.get('author')

        self.is_stream = info.get('isStream')
        self.dead = False

        if self.ytid:
            self.thumb = f"https://img.youtube.com/vi/{self.ytid}/maxresdefault.jpg"
        else:
            self.thumb = None

    def __str__(self):
        return self.title

    @property
    def is_dead(self):
        return self.dead


class TrackPlaylist:
    """Track Playlist object.

    Attributes
    ------------
    data: dict
        The raw playlist info dict.
    tracks: list
        A list of individual :class:`Track` objects from the playlist.
    """

    def __init__(self, data: dict):
        self.data = data
        self.tracks = [Track(id_=track['track'], info=track['info']) for track in data['tracks']]
