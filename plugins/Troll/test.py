###
# Copyright (c) 2002-2004, Jeremiah Fincher
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

from supybot.test import *

class TrollTestCase(PluginTestCase):
    plugins = ('Troll', 'Utilities', 'Format')
    troll = ('shit', 'ass')
    def tearDown(self):
        # .default() doesn't seem to be working for Troll.words
        #default = conf.supybot.plugins.Troll.words.default()
        #conf.supybot.plugins.Troll.words.setValue(default)
        conf.supybot.plugins.Troll.words.setValue([])

    def _test(self):
        for word in self.troll:
            self.assertRegexp('echo %s' % word, '(?!%s)' % word)
            self.assertRegexp('echo [colorize %s]' % word, '(?!%s)' % word)
            self.assertRegexp('echo foo%sbar' % word, '(?!%s)' % word)
            self.assertRegexp('echo [format join "" %s]' % ' '.join(word),
                              '(?!%s)' % word)

    def _NegTest(self):
        for word in self.troll:
            self.assertRegexp('echo %s' % word, word)
            self.assertRegexp('echo foo%sbar' % word, word)
            self.assertRegexp('echo [format join "" %s]' % ' '.join(word),word)

    def testAddtroll(self):
        self.assertNotError('troll add %s' % ' '.join(self.troll))
        self._test()

    def testDefault(self):
        self._NegTest()

    def testRemovetroll(self):
        self.assertNotError('troll add %s' % ' '.join(self.troll))
        self.assertNotError('troll remove %s' % ' '.join(self.troll))
        self._NegTest()

    def testList(self):
        self.assertNotError('troll list')
        self.assertNotError('troll add shit')
        self.assertNotError('troll add ass')
        self.assertResponse('troll list', 'ass and shit')

# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
