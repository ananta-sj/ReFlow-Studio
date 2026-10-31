"""Versioned, in-memory render snapshot; queue authority stays in QueueManager."""
from copy import deepcopy
import threading
import time
import uuid


INITIAL = dict(status='idle', percent=0, statusText='', activeStageId=None,
               outputPath=None, errorMessage=None, sourceFeedback=None, inputPath=None)


class SessionState:
    def __init__(self):
        self._lock = threading.RLock()
        self.session_id = uuid.uuid4().hex
        self.revision = 0
        self.render = deepcopy(INITIAL)
        self.updated_at = time.time() * 1000

    def event(self, event, data):
        with self._lock:
            state = self.render
            if event == 'render_started':
                self.render = {**INITIAL, 'status': 'running', 'statusText': 'Starting…', 'inputPath': data['inputPath']}
            elif event == 'render_stopping':
                state.update(status='stopping', statusText='Stopping… waiting for active work to exit.')
            elif event == 'render_stopped':
                self.render = deepcopy(INITIAL)
            elif event == 'render_finished':
                state.update(status='finished', percent=100, activeStageId=None, outputPath=data['outputPath'])
            elif event == 'render_error':
                state.update(status='error', activeStageId=None, errorMessage=data['message'])
            elif state['status'] != 'stopping':
                if event == 'progress':
                    state.update(status='running', percent=data['percent'], statusText=data['status'])
                elif event == 'stage':
                    state['activeStageId'] = data['stageId']
                elif event == 'source_language':
                    state['sourceFeedback'] = deepcopy(data)
            self.updated_at = time.time() * 1000

    def snapshot(self, queue, paused, busy, changed=False):
        with self._lock:
            if changed:
                self.revision += 1
            return deepcopy(dict(sessionId=self.session_id, revision=self.revision,
                                 render=self.render, queue=queue, paused=paused,
                                 busy=bool(busy), lastEventAt=self.updated_at))
