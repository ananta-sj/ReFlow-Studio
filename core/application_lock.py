"""One desktop owner per portable folder; OS locks survive stale lock files."""
import errno
import os
from pathlib import Path


class AlreadyRunning(RuntimeError):
    pass


class ApplicationLock:
    def __init__(self, folder):
        self.path = Path(folder).resolve() / '.reflow-instance.lock'
        self._stream = None

    def __enter__(self):
        stream = self.path.open('a+b')
        try:
            if os.name == 'nt':
                import msvcrt
                if self.path.stat().st_size == 0:
                    stream.write(b'0')
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            stream.close()
            if error.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                raise AlreadyRunning('Reflow is already open from this folder. Close that instance before opening another.') from error
            raise
        self._stream = stream
        return self

    def __exit__(self, *_):
        if self._stream is not None:
            # Keep the inode: unlinking permits another process to lock a new file.
            # Closing also releases the OS lock on abnormal process exit.
            self._stream.close()
            self._stream = None
