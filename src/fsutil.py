"""claude-light: write a JSON file atomically, and survive Windows' brief file locks."""
import json
import os
import time


def write_json(path, data, replace=os.replace, sleep=time.sleep, tries=10):
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w") as f:
        json.dump(data, f)
    for attempt in range(tries):
        try:
            replace(tmp, path)
            return
        except PermissionError:  # Windows: a reader has it open for a moment
            if attempt == tries - 1:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
                raise
            sleep(0.02)
