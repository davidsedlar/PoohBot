###
# Copyright (c) 2012, Matthias Meusburger
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
###

from supybot.commands import *
import supybot.plugins as plugins
import supybot.callbacks as callbacks
import supybot.schedule as schedule
import supybot.ircdb as ircdb
import supybot.ircmsgs as ircmsgs
import supybot.log as log
import supybot.conf as conf


import threading, random, pickle, os, time, datetime


class DuckHunt(callbacks.Plugin):
    """
    A DuckHunt game for supybot. Use the "start" command to start a game.
    The bot will randomly launch ducks. Whenever a duck is launched, the first
    person to use the "bang" command wins a point. Using the "bang" command
    when there is no duck launched costs a point.
    """

    threaded = True

    # Those parameters are per-channel parameters
    started = {}       # Has the hunt started?
    duck = {}          # Is there currently a duck to shoot?
    banging = {}       # Is there someone "banging" ;) right now?
    shoots = {}        # Number of successfull shoots in a hunt
    scores = {}        # Scores for the current hunt
    times = {}         # Elapsed time since the last duck was launched
    channelscores = {} # Saved scores for the channel
    toptimes = {}      # Times for the current hunt
    channeltimes = {}  # Saved times for the channel
    worsttimes = {}     # Worst times for the current hunt
    channelworsttimes = {} # Saved worst times for the channel
    averagetime = {}   # Average shooting time for the current hunt
    fridayMode = {}

    # Does a duck needs to be launched?
    lastSpoke = {}
    minthrottle = {}
    maxthrottle = {}
    throttle = {}

    # Where to save scores?
    fileprefix = "DuckHunt_"
    path = conf.supybot.directories.data

    # Enable the 'dbg' command, which launch a duck, if true
    debug = 0

    # Other params
    perfectbonus = 5 # How many extra-points are given when someones does a perfect hunt?
    toplist = 5      # How many high{scores|times} are displayed by default?


    def _calc_scores(self, channel):
	"""
	Adds new scores and times to the already saved ones
	"""

	# scores
	# Adding current scores to the channel scores
	for player in self.scores[channel].keys():
	    if not player in self.channelscores[channel]:
		# It's a new player
		self.channelscores[channel][player] = self.scores[channel][player]
	    else:
		# It's a player that already has a saved score
		self.channelscores[channel][player] += self.scores[channel][player]

	# times
	# Adding times scores to the channel scores
	for player in self.toptimes[channel].keys():
	    if not player in self.channeltimes[channel]:
		# It's a new player
		self.channeltimes[channel][player] = self.toptimes[channel][player]
	    else:
		# It's a player that already has a saved score
		# And we save the time of the current hunt if it's better than it's previous time
		if(self.toptimes[channel][player] < self.channeltimes[channel][player]):
		    self.channeltimes[channel][player] = self.toptimes[channel][player]

	# worst times
	# Adding worst times scores to the channel scores
	for player in self.worsttimes[channel].keys():
	    if not player in self.channelworsttimes[channel]:
		# It's a new player
		self.channelworsttimes[channel][player] = self.worsttimes[channel][player]
	    else:
		# It's a player that already has a saved score
		# And we save the time of the current hunt if it's worst than it's previous time
		if(self.worsttimes[channel][player] > self.channelworsttimes[channel][player]):
		    self.channelworsttimes[channel][player] = self.worsttimes[channel][player]



    def _write_scores(self, channel):
	"""
	Write scores and times to the disk
	"""

	# scores
        outputfile = open(self.path.dirize(self.fileprefix + channel + ".scores"), "wb")
        pickle.dump(self.channelscores[channel], outputfile)
        outputfile.close()

	# times
        outputfile = open(self.path.dirize(self.fileprefix + channel + ".times"), "wb")
        pickle.dump(self.channeltimes[channel], outputfile)
        outputfile.close()

	# worst times
        outputfile = open(self.path.dirize(self.fileprefix + channel + ".worsttimes"), "wb")
        pickle.dump(self.channelworsttimes[channel], outputfile)
        outputfile.close()





    def _read_scores(self, channel):
	"""
	Reads scores and times from disk
	"""
	filename = self.path.dirize(self.fileprefix + channel)
	# scores
	if not self.channelscores.get(channel):
	    if os.path.isfile(filename + ".scores"):
		inputfile = open(filename + ".scores", "rb")
		self.channelscores[channel] = pickle.load(inputfile)
		inputfile.close()

	# times
	if not self.channeltimes.get(channel):
	    if os.path.isfile(filename + ".times"):
		inputfile = open(filename + ".times", "rb")
		self.channeltimes[channel] = pickle.load(inputfile)
		inputfile.close()

	# worst times
	if not self.channelworsttimes.get(channel):
	    if os.path.isfile(filename + ".worsttimes"):
		inputfile = open(filename + ".worsttimes", "rb")
		self.channelworsttimes[channel] = pickle.load(inputfile)
		inputfile.close()

    
    def _initthrottle(self, irc, msg, args, channel):

	if (not self.fridayMode.get(channel)):
	    self.fridayMode[channel] = False


	# autoFriday?
	if self.registryValue('autoFriday', channel) and int(time.strftime("%w")) == 5 and int(time.strftime("%H")) > 8 and int(time.strftime("%H")) < 18:
	    self.fridayMode[channel] = True


	if self.fridayMode[channel] == False:
	    # Init min throttle[currentChannel] and max throttle[currentChannel]
	    if self.registryValue('minthrottle', channel):
		self.minthrottle[channel] = self.registryValue('minthrottle', channel)
	    else:
		self.minthrottle[channel] = 30

	    if self.registryValue('maxthrottle', channel):
		self.maxthrottle[channel] = self.registryValue('maxthrottle', channel)
	    else:
		self.maxthrottle[channel] = 300

	else:
	    self.minthrottle[channel] = 3
	    self.maxthrottle[channel] = 60

	self.throttle[channel] = random.randint(self.minthrottle[channel], self.maxthrottle[channel])


    def start(self, irc, msg, args):
        """
        Starts the hunt
        """

	currentChannel = msg.args[0]
	if irc.isChannel(currentChannel):

	    if(self.started.get(currentChannel) == True):
		irc.reply("There is already a hunt right now!")
	    else:

		self._initthrottle(irc, msg, args, currentChannel)

		#log.info("throttle : " + str(self.throttle[currentChannel]))

		# Init saved scores
		try:
		    self.channelscores[currentChannel]
		except:
		    self.channelscores[currentChannel] = {}

		# Init saved times
		try:
		    self.channeltimes[currentChannel]
		except:
		    self.channeltimes[currentChannel] = {}

		# Init saved times
		try:
		    self.channelworsttimes[currentChannel]
		except:
		    self.channelworsttimes[currentChannel] = {}


		# Init times
		self.toptimes[currentChannel] = {}
		self.worsttimes[currentChannel] = {}

		# Init bangdelay
		self.times[currentChannel] = False

		# Init lastSpoke
		self.lastSpoke[currentChannel] = time.time()

		if not self.channelscores[currentChannel] or not self.channeltimes[currentChannel] or not self.channelworsttimes[currentChannel]:
		    self._read_scores(currentChannel)

		# Reinit current hunt scores
		if self.scores.get(currentChannel):
		    self.scores[currentChannel] = {}

		# No duck launched
		self.duck[currentChannel] = False

		# Hunt started
		self.started[currentChannel] = True

		# Init banging
		self.banging[currentChannel] = False

		# Init shoots
		self.shoots[currentChannel] = 0

		# Init averagetime
		self.averagetime[currentChannel] = 0;

		# Init schedule

		# First of all, stop the scheduler if it was still running
		try:
		    schedule.removeEvent('DuckHunt_' + currentChannel)
		except KeyError:
		    pass

		# Then restart it
		def myEventCaller():
		    self._launchEvent(irc, msg)
		try:
		    schedule.addPeriodicEvent(myEventCaller, 5, 'DuckHunt_' + currentChannel, False)
		except AssertionError:
		    pass

		irc.reply("The hunt starts now!")
	else:
	    irc.error('You have to be on a channel')
    start = wrap(start)


    def _launchEvent(self, irc, msg):
	currentChannel = msg.args[0]
	now = time.time()
	if irc.isChannel(currentChannel):
	    if(self.started.get(currentChannel) == True):
		if (self.duck[currentChannel] == False):
		    if now > self.lastSpoke[currentChannel] + self.throttle[currentChannel]:
			# If someone is "banging" right now, do not launch a duck
			if (not self.banging[currentChannel]):
			    #log.info("Delay since the last launch for " + currentChannel + " "  + str(now - self.lastSpoke[currentChannel]) + " / throttle[currentChannel]: " + str(self.throttle[currentChannel]) + " / minthrottle[currentChannel]: " + str(self.minthrottle[currentChannel]) + " / maxthrottle[currentChannel]: " + str(self.maxthrottle[currentChannel]))
			    self._launch(irc, msg, '')



    def stop(self, irc, msg, args):
        """
        Stops the current hunt
        """

	currentChannel = msg.args[0]
	if irc.isChannel(currentChannel):
	    if (self.started.get(currentChannel) == True):
		self._end(irc, msg, args)

		# If someone uses the stop command,
		# we stop the scheduler, even if autoRestart is enabled
		try:
		    schedule.removeEvent('DuckHunt_' + currentChannel)
		except KeyError:
		    irc.reply('Error: the spammer wasn\'t running! This is a bug.')
	    else:
		irc.reply('Nothing to stop: there\'s no hunt right now.')
	else:
	    irc.error('You have to be on a channel')
    stop = wrap(stop)

    def fridaymode(self, irc, msg, args, channel):
	"""
	Enable/disable friday mode! (there are lots of ducks on friday :))
	"""
	if irc.isChannel(channel):

	    if (not self.fridayMode.get(channel)):
		self.fridayMode[channel] = False

	    if self.fridayMode[channel] == True:
		self.fridayMode[channel] = False
		irc.reply("Friday mode is now disabled.")

	    else:
		self.fridayMode[channel] = True
		irc.reply("Friday mode is now enabled! Shoot alllllllllllll the ducks!")

	    self._initthrottle(irc, msg, args, channel)
	else:
	    irc.error('You have to be on a channel')


    fridaymode = wrap(fridaymode, ['channel', 'admin'])

    def launched(self, irc, msg, args):
        """
        Is there a duck right now?
        """

	currentChannel = msg.args[0]
	if irc.isChannel(currentChannel):
	    if(self.started.get(currentChannel) == True):
		if(self.duck[currentChannel] == True):
		    irc.reply("There is currently a duck! You can shoot it with the 'bang' command")
		else:
		    irc.reply("There is no duck right now! Wait for one to be launched!")
	    else:
		irc.reply("There is no hunt right now! You can start a hunt with the 'start' command")
	else:
	    irc.error('You have to be on a channel')
    launched = wrap(launched)



    def score(self, irc, msg, args, nick):
	"""
	<nick>

	Shows the score for a given nick
	"""
	currentChannel = msg.args[0]
	if irc.isChannel(currentChannel):
	    self._read_scores(currentChannel)
	    try:
		self.channelscores[currentChannel]
	    except:
		self.channelscores[currentChannel] = {}


	    try:
		irc.reply(self.channelscores[currentChannel][nick])
	    except:
		irc.reply("There is no score for %s on %s" % (nick, currentChannel))
	else:
	    irc.error('You have to be on a channel')

    score = wrap(score, ['nick'])



    def mergescores(self, irc, msg, args, channel, nickto, nickfrom):
	"""
	[<channel>] <nickto> <nickfrom>
	
	nickto gets the points of nickfrom and nickfrom is removed from the scorelist
	"""
	if irc.isChannel(channel):
	    try:
		self._read_scores(channel)
		self.channelscores[channel][nickto] += self.channelscores[channel][nickfrom]
		del self.channelscores[channel][nickfrom]
		self._write_scores(channel)
		irc.replySuccess()

	    except:
		irc.replyError()


	else:
	    irc.error('You have to be on a channel')


    mergescores = wrap(mergescores, ['channel', 'nick', 'nick', 'admin'])



    def mergetimes(self, irc, msg, args, channel, nickto, nickfrom):
	"""
	[<channel>] <nickto> <nickfrom>
	
	nickto gets the best time of nickfrom if nickfrom time is better than nickto time, and nickfrom is removed from the timelist. Also works with worst times. 
	"""
	if irc.isChannel(channel):
	    try:
		self._read_scores(channel)

		# Merge best times
		if self.channeltimes[channel][nickfrom] < self.channeltimes[channel][nickto]:
		    self.channeltimes[channel][nickto] = self.channeltimes[channel][nickfrom]
		del self.channeltimes[channel][nickfrom]

		# Merge worst times
		if self.channelworsttimes[channel][nickfrom] > self.channelworsttimes[channel][nickto]:
		    self.channelworsttimes[channel][nickto] = self.channelworsttimes[channel][nickfrom]
		del self.channelworsttimes[channel][nickfrom]

		self._write_scores(channel)

		irc.replySuccess()

	    except:
		irc.replyError()


	else:
	    irc.error('You have to be on a channel')


    mergetimes = wrap(mergetimes, ['channel', 'nick', 'nick', 'admin'])



    def rmtime(self, irc, msg, args, channel, nick):
	"""
	[<channel>] <nick>
	
	Remove <nick>'s best time
	"""
	if irc.isChannel(channel):
	    self._read_scores(channel)
	    del self.channeltimes[channel][nick]
	    self._write_scores(channel)
	    irc.replySuccess()

	else:
	    irc.error('Are you sure ' + str(channel) + ' is a channel?')

    rmtime = wrap(rmtime, ['channel', 'nick', 'admin'])



    def rmscore(self, irc, msg, args, channel, nick):
	"""
	[<channel>] <nick>
	
	Remove <nick>'s score
	"""
	if irc.isChannel(channel):
	    try:
		self._read_scores(channel)
		del self.channelscores[channel][nick]
		self._write_scores(channel)
		irc.replySuccess()

	    except:
		irc.replyError()

	else:
	    irc.error('Are you sure this is a channel?')

    rmscore = wrap(rmscore, ['channel', 'nick', 'admin'])



    def listscores(self, irc, msg, args, size, channel):
        """
	[<size>] [<channel>]
	
	Shows the <size>-sized score list for <channel> (or for the current channel if no channel is given)
	"""

	if irc.isChannel(channel):
	    try:
		self.channelscores[channel]
	    except:
		self.channelscores[channel] = {}

	    self._read_scores(channel)

	    # How many results do we display?
	    if (not size):
		listsize = self.toplist
	    else:
		listsize = size

	    # Sort the scores (reversed: the higher the better)
	    scores = sorted(self.channelscores[channel].iteritems(), key=lambda (k,v):(v,k), reverse=True)
	    del scores[listsize:] 

	    msgstring = ""
	    for item in scores:
		# Why do we show the nicks as xnickx?
		# Just to prevent everyone that has ever played a hunt in the channel to be pinged every time anyone asks for the score list
		msgstring += "x" + item[0] + "x: "+ str(item[1]) + " | "
	    if msgstring != "":
		irc.reply("\_o< ~ DuckHunt top-" + str(listsize) + " scores for " + channel + " ~ >o_/")
		irc.reply(msgstring)
	    else:
		irc.reply("There aren't any scores for this channel yet.")
	else:
	    irc.reply("Are you sure this is a channel?")
    listscores = wrap(listscores, [optional('int'), 'channel'])


    def total(self, irc, msg, args, channel):
	"""
	Shows the total amount of ducks shot in <channel> (or in the current channel if no channel is given)
	"""

	if irc.isChannel(channel):
	    self._read_scores(channel)
	    if (self.channelscores.get(channel)):
		scores = self.channelscores[channel]
		total = 0
		for player in scores.keys():
		    total += scores[player]
		irc.reply(str(total) + " ducks have been shot in " + channel + "!")
	    else:
		irc.reply("There are no scores for this channel yet")

	else:
	    irc.reply("Are you sure this is a channel?")
    total = wrap(total, ['channel'])


    def listtimes(self, irc, msg, args, size, channel):
        """
	[<size>] [<channel>]
	
	Shows the <size>-sized time list for <channel> (or for the current channel if no channel is given)
	"""

	if irc.isChannel(channel):
	    self._read_scores(channel)

	    try:
		self.channeltimes[channel]
	    except:
		self.channeltimes[channel] = {}

	    try:
		self.channelworsttimes[channel]
	    except:
		self.channelworsttimes[channel] = {}

	    # How many results do we display?
	    if (not size):
		listsize = self.toplist
	    else:
		listsize = size

	    # Sort the times (not reversed: the lower the better)
	    times = sorted(self.channeltimes[channel].iteritems(), key=lambda (k,v):(v,k), reverse=False)
	    del times[listsize:] 

	    msgstring = ""
	    for item in times:
		# Same as in listscores for the xnickx
		msgstring += "x" + item[0] + "x: "+ str(round(item[1],2)) + " | "
	    if msgstring != "":
		irc.reply("\_o< ~ DuckHunt top-" + str(listsize) + " times for " + channel + " ~ >o_/")
		irc.reply(msgstring)
	    else:
		irc.reply("There aren't any best times for this channel yet.")


	    times = sorted(self.channelworsttimes[channel].iteritems(), key=lambda (k,v):(v,k), reverse=True)
	    del times[listsize:] 

	    msgstring = ""
	    for item in times:
		# Same as in listscores for the xnickx
		#msgstring += "x" + item[0] + "x: "+ time.strftime('%H:%M:%S', time.gmtime(item[1])) + ", "
		roundseconds = round(item[1])
		delta = datetime.timedelta(seconds=roundseconds)
		msgstring += "x" + item[0] + "x: " + str(delta) + " | "
	    if msgstring != "":
		irc.reply("\_o< ~ DuckHunt top-" + str(listsize) + " longest times for " + channel + " ~ >o_/")
		irc.reply(msgstring)
	    else:
		irc.reply("There aren't any longest times for this channel yet.")



	else:
	    irc.reply("Are you sure this is a channel?")
    listtimes = wrap(listtimes, [optional('int'), 'channel'])



    def dbg(self, irc, msg, args):
	""" 
	This is a debug command. If debug mode is not enabled, it won't do anything 
	"""
	currentChannel = msg.args[0]
	if (self.debug):
	    if irc.isChannel(currentChannel):
		self._launch(irc, msg, '')
    dbg = wrap(dbg)
		


    def bang(self, irc, msg, args):
        """
        Shoots the duck!
        """
        currentChannel = msg.args[0]
	self.banging[currentChannel] = True

	if irc.isChannel(currentChannel):
	    if(self.started.get(currentChannel) == True):

		    # bangdelay: how much time between the duck was launched and this shot?
		    if self.times[currentChannel]:
			bangdelay = time.time() - self.times[currentChannel]
		    else:
			bangdelay = False

		    # There was a duck
		    if (self.duck[currentChannel] == True):

			# Adds one point for the nick that shot the duck
			try:
			    self.scores[currentChannel][msg.nick] += 1
			except:
			    try:
				self.scores[currentChannel][msg.nick] = 1
			    except:
				self.scores[currentChannel] = {} 
				self.scores[currentChannel][msg.nick] = 1

			irc.reply("\_x< %s: %i (%.2f seconds)" % (msg.nick,  self.scores[currentChannel][msg.nick], bangdelay))

			self.averagetime[currentChannel] += bangdelay

			# Now save the bang delay for the player (if it's quicker than it's previous bangdelay)
			try:
			    previoustime = self.toptimes[currentChannel][msg.nick]
			    if(bangdelay < previoustime):
				self.toptimes[currentChannel][msg.nick] = bangdelay
			except:
			    self.toptimes[currentChannel][msg.nick] = bangdelay


			# Now save the bang delay for the player (if it's worst than it's previous bangdelay)
			try:
			    previoustime = self.worsttimes[currentChannel][msg.nick]
			    if(bangdelay > previoustime):
				self.worsttimes[currentChannel][msg.nick] = bangdelay
			except:
			    self.worsttimes[currentChannel][msg.nick] = bangdelay


			self.duck[currentChannel] = False

			# Reset the basetime for the waiting time before the next duck
			self.lastSpoke[currentChannel] = time.time()

			if self.registryValue('ducks', currentChannel):
			    maxShoots = self.registryValue('ducks', currentChannel)
			else:
			    maxShoots = 10

			# End of Hunt
			if (self.shoots[currentChannel]  == maxShoots):
			    self._end(irc, msg, args)

			    # If autorestart is enabled, we restart a hunt automatically!
			    if self.registryValue('autoRestart', currentChannel):
				# This code shouldn't be here
				self.started[currentChannel] = True
				self._initthrottle(irc, msg, args, currentChannel)
				if self.scores.get(currentChannel):
				    self.scores[currentChannel] = {}
				self.averagetime[currentChannel] = 0


		    # There was no duck or the duck has already been shot
		    else:

			# Removes one point for the nick that shot
			try:
			    self.scores[currentChannel][msg.nick] -= 1
			except:
			    try:
				self.scores[currentChannel][msg.nick] = -1
			    except:
				self.scores[currentChannel] = {} 
				self.scores[currentChannel][msg.nick] = -1

			# Base message
			message = 'There was no duck!'

			# Adding additional message if kick
			if self.registryValue('kickMode', currentChannel) and irc.nick in irc.state.channels[currentChannel].ops:
			    message += ' You just shot yourself!'

			# Adding nick and score
			message += " %s: %i" % (msg.nick, self.scores[currentChannel][msg.nick])

			# If we were able to have a bangdelay (ie: a duck was launched before someone did bang)
			if (bangdelay):
			    # Adding time
			    message += " (" + str(round(bangdelay,2)) + " seconds)"

			# If kickMode is enabled for this channel, and the bot have op capability, let's kick!
			if self.registryValue('kickMode', currentChannel) and irc.nick in irc.state.channels[currentChannel].ops:
			    irc.queueMsg(ircmsgs.kick(currentChannel, msg.nick, message))
			else:
			    # Else, just say it
			    irc.reply(message)


	    else:
		irc.reply("There is no hunt right now! You can start a hunt with the 'start' command")
	else:
	    irc.error('You have to be on a channel')

	self.banging[currentChannel] = False

    bang = wrap(bang)



    def _end(self, irc, msg, args):
	""" 
	End of the hunt (is called when the hunts stop "naturally" or when someone uses the !stop command)
	"""

	currentChannel = msg.args[0]

	# End the hunting
	self.started[currentChannel] = False

	try:
	    self.channelscores[currentChannel]
	except:
	    self.channelscores[currentChannel] = {}


	if not self.registryValue('autoRestart', currentChannel):
	    irc.reply("The hunt stops now!")

	# Showing scores
	if (self.scores.get(currentChannel)):

	    # Getting winner
	    winnernick, winnerscore = max(self.scores.get(currentChannel).iteritems(), key=lambda (k,v):(v,k))
	    if self.registryValue('ducks', currentChannel):
		maxShoots = self.registryValue('ducks', currentChannel)
	    else:
		maxShoots = 10

	    # Showing scores
	    #irc.reply("Winner: %s with %i points" % (winnernick, winnerscore))
	    #irc.reply(self.scores.get(currentChannel))
	    #TODO: Better display
	    irc.reply(sorted(self.scores.get(currentChannel).iteritems(), key=lambda (k,v):(v,k), reverse=True))

	    # Is there a perfect?
	    if (winnerscore == maxShoots):
		irc.reply("\o/ %s: %i ducks out of %i: perfect!!! +%i \o/" % (winnernick, winnerscore, maxShoots, self.perfectbonus))
		self.scores[currentChannel][winnernick] += self.perfectbonus

	    # Getting channel best time (to see if the best time of this hunt is better)
	    channelbestnick = None
	    channelbesttime = None
	    if self.channeltimes.get(currentChannel):
		channelbestnick, channelbesttime = min(self.channeltimes.get(currentChannel).iteritems(), key=lambda (k,v):(v,k))

	    # Showing best time
	    recordmsg = ''
	    if (self.toptimes.get(currentChannel)):
		key,value = min(self.toptimes.get(currentChannel).iteritems(), key=lambda (k,v):(v,k))
		if (channelbesttime and value < channelbesttime):
		    recordmsg = '. This is the new record for this channel! (previous record was held by ' + channelbestnick + ' with ' + str(round(channelbesttime,2)) +  ' seconds)'
		else:
		    try:
			if(value < self.channeltimes[currentChannel][key]):
			    recordmsg = ' (this is your new record in this channel! Your previous record was ' + str(round(self.channeltimes[currentChannel][key],2)) + ')'
		    except:
			recordmsg = ''

		irc.reply("Best time: %s with %.2f seconds%s" % (key, value, recordmsg))

	    # Getting channel worst time (to see if the worst time of this hunt is worst)
	    channelworstnick = None
	    channelworsttime = None
	    if self.channelworsttimes.get(currentChannel):
		channelworstnick, channelworsttime = max(self.channelworsttimes.get(currentChannel).iteritems(), key=lambda (k,v):(v,k))


	    # Showing worst time
	    recordmsg = ''
	    if (self.worsttimes.get(currentChannel)):
		key,value = max(self.worsttimes.get(currentChannel).iteritems(), key=lambda (k,v):(v,k))
		if (channelworsttime and value > channelworsttime):
		    recordmsg = '. This is the new longest time for this channel! (previous longest time was held by ' + channelworstnick + ' with ' + str(round(channelworsttime,2)) +  ' seconds)'
		else:
		    try:
			if(value > self.channelworsttimes[currentChannel][key]):
			    recordmsg = ' (this is your new longest time in this channel! Your previous longest time was ' + str(round(self.channelworsttimes[currentChannel][key],2)) + ')'
		    except:
			recordmsg = ''

		# Only display worst time if something new
		if (recordmsg != ''):
		    irc.reply("Longest time: %s with %.2f seconds%s" % (key, value, recordmsg))

	    # Showing average shooting time:
	    if (self.shoots[currentChannel] > 1):
		irc.reply("Average shooting time: %.2f seconds" % ((self.averagetime[currentChannel] / self.shoots[currentChannel])))

	    # Write the scores and times to disk
	    self._calc_scores(currentChannel)
	    self._write_scores(currentChannel)
	else:
	    irc.reply("Not a single duck was shot during this hunt!")

	# Reinit current hunt scores
	if self.scores.get(currentChannel):
	    self.scores[currentChannel] = {}

	# Reinit current hunt times
	if self.toptimes.get(currentChannel):
	    self.toptimes[currentChannel] = {}
	if self.worsttimes.get(currentChannel):
	    self.worsttimes[currentChannel] = {}

	# No duck lauched
	self.duck[currentChannel] = False

	# Reinit number of shoots
	self.shoots[currentChannel] = 0



    def _launch(self, irc, msg, args):
	"""
	Launch a duck
	"""
	currentChannel = msg.args[0]
	if irc.isChannel(currentChannel):
	    if(self.started[currentChannel] == True):
		if (self.duck[currentChannel] == False):

		    # Store the time when the duck has been launched
		    self.times[currentChannel] = time.time()

		    # Store the fact that there's a duck now
		    self.duck[currentChannel] = True

		    # Send message directly (instead of queuing it with irc.reply)
		    irc.sendMsg(ircmsgs.privmsg(currentChannel,"\_o< quack!"))

		    # Define a new throttle[currentChannel] for the next launch
		    self.throttle[currentChannel] = random.randint(self.minthrottle[currentChannel], self.maxthrottle[currentChannel])
		    #log.info("throttle for " + currentChannel + " : " + str(self.throttle[currentChannel]))

		    try:
			self.shoots[currentChannel] += 1
		    except:
			self.shoots[currentChannel] = 1
		else:

		    irc.reply("Already a duck")
	    else:
		irc.reply("The hunting has not started yet!")
	else:
	    irc.error('You have to be on a channel')


Class = DuckHunt

# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79: