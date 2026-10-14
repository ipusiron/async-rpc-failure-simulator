"""Small stdio teaching client. Correlation is not authentication."""

import json
import math
import secrets
import subprocess
import threading
from collections import deque
from concurrent.futures import Future, TimeoutError


class StdioClient:
    MAX_PENDING = 128
    MAX_HISTORY = 100

    def __init__(self, python_exe, server_script, *, discard_orphans=False):
        self._lock = threading.RLock()
        self._write_lock = threading.Lock()
        self._pending = {}
        self._next_id = 0
        self._closed = False
        self.discard_orphans = discard_orphans
        self.orphan_responses = deque(maxlen=self.MAX_HISTORY)
        self.notifications = deque(maxlen=self.MAX_HISTORY)
        self.orphan_event = threading.Event()
        self.stats = dict(requests_sent=0, responses_received=0,
                          orphans_observed=0, orphans_discarded=0,
                          timeouts=0, invalid_messages=0)
        self.process = subprocess.Popen(
            [python_exe, '-X', 'utf8', server_script], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding='utf-8', bufsize=1)
        self._reader = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader.start()

    def _issue_id(self):
        if self.discard_orphans:
            return secrets.token_hex(16)
        self._next_id += 1
        return self._next_id

    def _send(self, message):
        text = json.dumps(message, ensure_ascii=True, allow_nan=False)
        with self._write_lock:
            if self._closed:
                raise ConnectionError('Client is closed')
            self.process.stdin.write(text + '\n')
            self.process.stdin.flush()

    def _remove_pending(self, request_id, future):
        with self._lock:
            if self._pending.get(request_id) is future:
                self._pending.pop(request_id)

    def send_request(self, method, params):
        """Return (id, Future). Cancel the Future if abandoning this API's wait."""
        with self._lock:
            if self._closed:
                raise ConnectionError('Client is closed')
            if len(self._pending) >= self.MAX_PENDING:
                raise RuntimeError('Too many pending requests')
            request_id = self._issue_id()
            while request_id in self._pending:
                request_id = self._issue_id()
            future = Future()
            self._pending[request_id] = future
            future.add_done_callback(lambda f: self._remove_pending(request_id, f))
            # Keep registration and transmission ordered against close/EOF.
            try:
                self._send(dict(jsonrpc='2.0', id=request_id, method=method, params=params))
            except Exception:
                future.cancel()
                raise
            self.stats['requests_sent'] += 1
        return request_id, future

    def request(self, method, params, timeout=5.0):
        if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
                or not math.isfinite(timeout) or timeout <= 0):
            raise ValueError('Timeout must be finite and greater than zero')
        request_id, future = self.send_request(method, params)
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            # A response may win the race between result() and this lock.
            with self._lock:
                if future.done():
                    return future.result()
                self.stats['timeouts'] += 1
                future.cancel()
            raise
        finally:
            self._remove_pending(request_id, future)

    def notify(self, method, params):
        self._send(dict(jsonrpc='2.0', method=method, params=params))

    def _accept(self, data):
        with self._lock:
            if not isinstance(data, dict) or data.get('jsonrpc') != '2.0':
                self.stats['invalid_messages'] += 1
                return
            if 'id' not in data and isinstance(data.get('method'), str):
                self.notifications.append(data)
                return
            response_id = data.get('id')
            if (type(response_id) not in (int, str) or 'method' in data
                    or ('result' in data) == ('error' in data)):
                self.stats['invalid_messages'] += 1
                return
            if 'error' in data and (not isinstance(data['error'], dict)
                    or type(data['error'].get('code')) is not int
                    or not isinstance(data['error'].get('message'), str)):
                self.stats['invalid_messages'] += 1
                return
            future = self._pending.pop(response_id, None)
            if future is None or future.done():
                self.stats['orphans_observed'] += 1
                if self.discard_orphans:
                    self.stats['orphans_discarded'] += 1
                else:
                    self.orphan_responses.append(data)
                self.orphan_event.set()
                return
            self.stats['responses_received'] += 1
            future.set_result(data)

    def _reader_loop(self):
        try:
            for line in self.process.stdout:
                try:
                    self._accept(json.loads(line))
                except (ValueError, TypeError):
                    with self._lock:
                        self.stats['invalid_messages'] += 1
        except (OSError, UnicodeError, ValueError):
            pass
        finally:
            self._fail_pending()

    def _fail_pending(self):
        with self._lock:
            self._closed = True
            pending = list(self._pending.values())
            self._pending.clear()
            for future in pending:
                if not future.done():
                    future.set_exception(ConnectionError('Server stream closed'))

    def get_stats(self):
        with self._lock:
            return dict(self.stats)

    def close(self):
        self._fail_pending()
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        self._reader.join(timeout=3)
        self.process.stdin.close()
        self.process.stdout.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
