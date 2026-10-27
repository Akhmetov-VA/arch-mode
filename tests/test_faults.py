"""Faults and time (Designing Data-Intensive Applications): timeouts, clocks, swallowed errors."""
import pytest


def lines(project, rule):
    return [f["line"] for f in project.findings(rule=rule)]


@pytest.mark.parametrize("code", [
    "import requests\nrequests.get(url)\n",
    "import requests\nrequests.post(url, json={})\n",
    "import requests as r\nr.request('GET', url)\n",
    "from requests import put\nput(url)\n",
    "import urllib.request\nurllib.request.urlopen(url)\n",
    "from urllib.request import urlopen\nurlopen(url)\n",
    "import socket\nsocket.create_connection(addr)\n",
    "import httpx\nhttpx.get(url, timeout=None)\n",
])
def test_network_call_without_timeout_is_an_error(project, code):
    project.write({"app.py": code})
    [f] = project.findings(rule="network-timeout")
    assert f["severity"] == "error" and f["line"] == 2


@pytest.mark.parametrize("code", [
    "import requests\nrequests.get(url, timeout=5)\n",
    "import urllib.request\nurllib.request.urlopen(url, timeout=10)\n",
    "import httpx\nhttpx.get(url)\n",
    "def get(url): ...\nget(url)\n",
])
def test_network_call_with_timeout_is_fine(project, code):
    project.write({"app.py": code})
    assert project.findings(rule="network-timeout") == []


def test_duration_from_wall_clock_is_a_warning(project):
    project.write({"app.py": "import time\nt0 = time.time()\nwork()\nspent = time.time() - t0\n"})
    assert lines(project, "wall-clock-duration") == [4]


def test_duration_from_monotonic_clock_is_fine(project):
    project.write({"app.py": "import time\nt0 = time.monotonic()\nspent = time.monotonic() - t0\nstamp = time.time()\n"})
    assert lines(project, "wall-clock-duration") == []


@pytest.mark.parametrize("code", [
    "from datetime import datetime\ndatetime.utcnow()\n",
    "from datetime import datetime\ndatetime.now()\n",
    "import datetime\ndatetime.datetime.now()\n",
])
def test_naive_datetime_is_a_warning(project, code):
    project.write({"app.py": code})
    assert lines(project, "naive-datetime") == [2]


def test_aware_datetime_is_fine(project):
    project.write({"app.py": "from datetime import datetime, timezone\ndatetime.now(timezone.utc)\ndatetime.now(tz=timezone.utc)\n"})
    assert lines(project, "naive-datetime") == []


@pytest.mark.parametrize("handler", ["except:\n    pass", "except Exception:\n    pass",
                                     "except BaseException:\n    continue", "except (ValueError, Exception):\n    ..."])
def test_swallowed_broad_error_is_a_warning(project, handler):
    project.write({"app.py": f"for x in xs:\n  try:\n    work()\n  {handler.replace(chr(10), chr(10) + '  ')}\n"})
    assert lines(project, "swallowed-error") == [4]


@pytest.mark.parametrize("handler", ["except ValueError:\n    pass", "except Exception as e:\n    log(e)",
                                     "except Exception:\n    raise"])
def test_narrow_or_handled_error_is_fine(project, handler):
    project.write({"app.py": f"try:\n    work()\n{handler}\n"})
    assert lines(project, "swallowed-error") == []


@pytest.mark.parametrize("code", [
    "import pickle\npickle.load(f)\n",
    "import pickle\npickle.dumps(x)\n",
    "from joblib import dump\ndump(model, path)\n",
    "import shelve\nshelve.open(path)\n",
    "import marshal\nmarshal.loads(b)\n",
])
def test_language_specific_serialization_is_a_warning(project, code):
    project.write({"app.py": code})
    [f] = project.findings(rule="language-serialization")
    assert f["severity"] == "warning" and f["line"] == 2


def test_schema_formats_are_fine(project):
    project.write({"app.py": "import json\njson.load(f)\njson.dumps(x)\n"})
    assert project.findings(rule="language-serialization") == []


@pytest.mark.parametrize("code", [
    "import queue\nqueue.Queue()\n",
    "import asyncio\nasyncio.Queue(maxsize=0)\n",
    "from multiprocessing import Queue\nQueue()\n",
    "import queue\nqueue.SimpleQueue()\n",
])
def test_unbounded_queue_is_a_warning(project, code):
    project.write({"app.py": code})
    [f] = project.findings(rule="unbounded-queue")
    assert f["severity"] == "warning" and f["line"] == 2


@pytest.mark.parametrize("code", [
    "import queue\nqueue.Queue(100)\n",
    "import asyncio\nasyncio.Queue(maxsize=10)\n",
    "from collections import deque\ndeque()\n",
])
def test_bounded_queue_is_fine(project, code):
    project.write({"app.py": code})
    assert project.findings(rule="unbounded-queue") == []
