"""Run Proton Bridge only while the tracker's server runs.

start() launches `protonmail-bridge-core --noninteractive` as a child process,
unless something already listens on the IMAP port (e.g. the interactive
--cli): that one is left alone and never stopped by us.
"""
import socket
import time

import children
from mail import HOST, PORT

CMD = ["protonmail-bridge-core", "--noninteractive"]


def is_listening(host=HOST, port=PORT):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def start():
    """Start Bridge. Returns the process, or None if a Bridge was already running."""
    return None if is_listening() else children.start(CMD)


def wait_ready(proc, timeout=60):
    """Block until IMAP accepts connections. False if Bridge exited or timed out."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_listening():
            return True
        if proc is not None and proc.poll() is not None:
            return False
        time.sleep(0.5)
    return False


def stop(proc):
    children.stop(proc)
