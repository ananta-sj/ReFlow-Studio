"""Bounded handling of transient scanner/sharing locks on owned worker files."""
import json,time

def read_json(path,check=lambda:None):
    for attempt in range(5):
        check()
        try:return json.loads(path.read_text(encoding='utf-8'))
        except PermissionError:
            if attempt==4:raise
            time.sleep(.05*2**attempt)

def replace(pending,destination,check=lambda:None):
    for attempt in range(5):
        check()
        try:pending.replace(destination);return
        except PermissionError:
            if attempt==4:raise
            time.sleep(.05*2**attempt)

def retire(path):
    """Consumed sidecar cleanup cannot invalidate successful inference."""
    for attempt in range(5):
        try:path.unlink();return
        except FileNotFoundError:return
        except PermissionError:
            if attempt==4:return
            time.sleep(.05*2**attempt)
