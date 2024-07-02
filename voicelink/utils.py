
import random
import time
import socket
from timeit import default_timer as timer
from itertools import zip_longest

__all__ = [
    "ExponentialBackoff",
    "NodeStats"
]

class ExponentialBackoff:
    def __init__(self, base: int = 1, *, integral: bool = False) -> None:

        self._base = base

        self._exp = 0
        self._max = 10
        self._reset_time = base * 2 ** 11
        self._last_invocation = time.monotonic()

        rand = random.Random()
        rand.seed()

        self._randfunc = rand.randrange if integral else rand.uniform

    def delay(self) -> float:

        invocation = time.monotonic()
        interval = invocation - self._last_invocation
        self._last_invocation = invocation

        if interval > self._reset_time:
            self._exp = 0

        self._exp = min(self._exp + 1, self._max)
        return self._randfunc(0, self._base * 2 ** self._exp)


class NodeStats:
    """The base class for the node stats object.
       Gives critical information on the node, which is updated every minute.
    """

    def __init__(self, data: dict) -> None:

        memory: dict = data.get("memory")
        self.used = memory.get("used")
        self.free = memory.get("free")
        self.reservable = memory.get("reservable")
        self.allocated = memory.get("allocated")

        cpu: dict = data.get("cpu")
        self.cpu_cores = cpu.get("cores")
        self.cpu_system_load = cpu.get("systemLoad")
        self.cpu_process_load = cpu.get("lavalinkLoad")

        self.players_active = data.get("playingPlayers")
        self.players_total = data.get("players")
        self.uptime = data.get("uptime")

    def __repr__(self) -> str:
        return f"<Voicelink.NodeStats total_players={self.players_total!r} playing_active={self.players_active!r}>"


class Ping:
    # Thanks to https://github.com/zhengxiaowai/tcping for the nice ping impl
    def __init__(self, host, port, timeout=5):
        self.timer = self.Timer()

        self._successed = 0
        self._failed = 0
        self._conn_time = None
        self._host = host
        self._port = port
        self._timeout = timeout

    class Socket(object):
        def __init__(self, family, type_, timeout):
            s = socket.socket(family, type_)
            s.settimeout(timeout)
            self._s = s

        def connect(self, host, port):
            self._s.connect((host, int(port)))

        def shutdown(self):
            self._s.shutdown(socket.SHUT_RD)

        def close(self):
            self._s.close()


    class Timer(object):
        def __init__(self):
            self._start = 0
            self._stop = 0

        def start(self):
            self._start = timer()

        def stop(self):
            self._stop = timer()

        def cost(self, funcs, args):
            self.start()
            for func, arg in zip_longest(funcs, args):
                if arg:
                    func(*arg)
                else:
                    func()

            self.stop()
            return self._stop - self._start

    def _create_socket(self, family, type_):
        return self.Socket(family, type_, self._timeout)

    def get_ping(self):
        s = self._create_socket(socket.AF_INET, socket.SOCK_STREAM)
     
        cost_time = self.timer.cost(
            (s.connect, s.shutdown),
            ((self._host, self._port), None))
        s_runtime = 1000 * (cost_time)

        return s_runtime

