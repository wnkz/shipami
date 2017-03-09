from click.testing import CliRunner
import pytest
import os
import json

from shipami import __version__ as VERSION
from shipami.cli import cli as shipami

runner = CliRunner()

def test_version():
    r = runner.invoke(shipami, ['--version'])
    assert r.exit_code == 0
    assert VERSION in r.output
