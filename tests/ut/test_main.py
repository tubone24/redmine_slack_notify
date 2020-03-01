from unittest.mock import call
from unittest.mock import patch
from datetime import datetime
import os
import sys
import pathlib
current_dir = pathlib.Path(__file__).resolve().parent
sys.path.append(os.path.join(current_dir.parent.parent, 'src'))
from src import main as target


def test_check_daily_time_true():
    tdatetime = datetime.strptime("2020/03/01 09:01", "%Y/%m/%d %H:%M")
    actual = target.check_daily_time(tdatetime)
    assert actual is True
