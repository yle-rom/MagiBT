"""Child processes that never outlive their parent (Bridge under the server, the server under the CLI).

Normal exits (q, Ctrl+C, SIGTERM, SIGHUP) stop children in a `finally`. SIGKILL
can't be caught, so that path runs no code at all: for it, each child asks the
kernel for a "parent-death signal" (prctl PR_SET_PDEATHSIG, Linux only), and
the kernel itself sends the child SIGTERM the moment the parent dies, however
it died. The child then shuts down cleanly as if it had been stopped normally.
"""
import ctypes
import os
import signal
import subprocess

PR_SET_PDEATHSIG = 1
_libc = ctypes.CDLL(None, use_errno=True)


def _die_with_parent(parent_pid):
    def setup():                                    # runs in the child, between fork and exec
        _libc.prctl(PR_SET_PDEATHSIG, signal.SIGTERM)
        if os.getppid() != parent_pid:              # parent already gone before prctl took effect
            os.kill(os.getpid(), signal.SIGTERM)
    return setup


def start(cmd, **kw):
    """Popen with no terminal I/O, its own process group, and death-with-parent."""
    # Own process group: Ctrl+C in the terminal reaches only the parent, which
    # then stops the child in order, instead of both receiving SIGINT at once.
    return subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True,
                            preexec_fn=_die_with_parent(os.getpid()), **kw)


def stop(proc, timeout=15):
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()                                # SIGTERM: let it shut down cleanly
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
