#!/usr/bin/env python3
# Main code.
from __init__ import *

# The only hardcoded module.
modules.load('core')
# Load all other modules.
for module in config.current['modules']:
    modules.load(module)

# And do the IRC.
irc.setup()
irc.main_loop()

# Clean up.
modules.unload_all()

