import socket
import re
import logging
import time
from threading import Thread
logger = logging.getLogger(name="tmi")


class twitchirc_handler:

    def __init__(self, user, oauth, channels):
        logger.info('tmi starting up')
        self.user = user
        self.oauth = oauth
        self.ircSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ircServ = 'irc.twitch.tv'
        self.ircChans = channels
        self.subscribers = []
        self.socketthread = Thread(target=self.run)

    def connect(self, port):
        logger.info('Connecting to twitch irc')
        self.ircSock.connect((self.ircServ, port))
        logger.info('Connected..authenticating as %s' % self.user)
        self.ircSock.send(str('Pass ' + self.oauth + '\r\n').encode('UTF-8'))
        self.ircSock.send(str('NICK ' + self.user + '\r\n').lower().encode('UTF-8'))
        self.ircSock.send(str('CAP REQ :twitch.tv/tags\r\n').encode('UTF-8'))
        logger.info('Joining channels %s' % self.ircChans)
        for chan in self.ircChans:
            self.ircSock.send(str('JOIN ' + chan + '\r\n').encode('UTF-8'))

    def subscribeMessage(self, callback):
        self.subscribers.append(callback)

    def handleIRCMessage(self, ircMessage):
        #logger.debug(ircMessage)
        regex = r'@color=(?:|#([^;]*));'
        regex += r'display-name=([^;]*);'
        regex += r'emotes=([^;]*);'
        regex += r'subscriber=([^;]*);'
        regex += r'turbo=([^;]*);'
        regex += r'user-id=([^;]*);'
        regex += r'user-type=([^ ]*)'
        regex += r' :([^!]*)![^!]*@[^.]*.tmi.twitch.tv'  # username
        regex += r' PRIVMSG #([^ ]*)'  # channel
        regex += r' :(.*)'  # message
        match = re.search(regex, ircMessage)
        if match:
            result = {
                'color': match.group(1),
                'displayname': match.group(2),
                'emotes': match.group(3),
                'subscribed': bool(int(match.group(4))),
                'turbo': bool(int(match.group(5))),
                'usertype': match.group(7),
                'username': match.group(8),
                'channel': match.group(9),
                'message': match.group(10)
            }
            for subscriber in self.subscribers:
                subscriber(result)
        if re.search(r':tmi.twitch.tv NOTICE \* :Error logging i.*', ircMessage):
            logger.critical('Error logging in to twitch irc, check oauth and username are set in config.txt!')
            sys.exit()
        elif ircMessage.find('PING ') != -1:
            logger.info('Responding to a ping from twitch... pong!')
            self.ircSock.send(str('PING :pong\n').encode('UTF-8'))

    def start(self):
        if not self.socketthread.is_alive():
            self.running = True
            self.socketthread = Thread(target=self.run)
            self.socketthread.start()
        else:
            logger.critical("Already running can't run twice")

    def stop(self):
        if self.socketthread.is_alive():
            self.running = False
            self.ircSock.shutdown(socket.SHUT_RDWR)
            self.ircSock.close()
        self.socketthread.join()

    def run(self):
        line_sep_exp = re.compile(b'\r?\n')
        socketBuffer = b''
        while self.running:
            try:
                # get messages
                socketBuffer += self.ircSock.recv(1024)
                ircMsgs = line_sep_exp.split(socketBuffer)
                socketBuffer = ircMsgs.pop()
                # Deal with them
                for ircMsg in ircMsgs:
                    msg = ircMsg.decode('utf-8')
                    self.handleIRCMessage(msg)
            except:
                raise
