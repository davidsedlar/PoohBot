###
# Copyright (c) 2012, spline
# All rights reserved.
#
#
###

import os

import supybot.conf as conf
import supybot.registry as registry

def configure(advanced):
    # This will be called by supybot to configure this module.  advanced is
    # a bool that specifies whether the user identified himself as an advanced
    # user or not.  You should effect your configuration by manipulating the
    # registry as appropriate.
    from supybot.questions import expect, anything, something, yn
    conf.registerPlugin('NBA', True)


NBA = conf.registerPlugin('NBA')
conf.registerGlobalValue(NBA, 'dbLocation', registry.String(os.path.abspath(os.path.dirname(__file__)) + '/nba.db', """Absolute path for nba.db sqlite3 database file location."""))

# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=250:
