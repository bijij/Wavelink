__title__ = 'WaveLink'
__author__ = 'EvieePy'
__license__ = 'MIT'
__copyright__ = 'Copyright 2019-2020 (c) PythonistaGuild'
__version__ = '0.9.4'

from .client import Client
from .errors import *
from .eqs import Equalizer
from .events import *
from .player import Player
from .node import Node
from .meta import WavelinkClientMixin, WavelinkCogMixin
from .track import Track, TrackPlaylist
from .websocket import WebSocket
