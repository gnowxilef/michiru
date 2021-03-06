#!/usr/bin/env python3
# Seenbot module.
from datetime import datetime
import json

import db
import personalities
from modules import command, hook
_ = personalities.localize

__name__ = 'seenbot'
__author__ = 'Shiz'
__license__ = 'WTFPL'

db.ensure('seen', {
    'id': db.ID,
    'server': db.STRING,
    'nickname': db.STRING,
    'action': (db.INT),
    'data': (db.STRING),
    'time': (db.DATETIME)
})

class Actions:
    JOIN = 0x1
    PART = 0x2
    QUIT = 0x3
    KICK = 0x4
    KICKED = 0x5
    NICKCHANGE = 0x6
    NICKCHANGED = 0x7
    MESSAGE = 0x8
    NOTICE = 0x9
    TOPICCHANGE = 0x10
    CTCP = 0x11


def timespan(date, current=None, reach=2):
    """ Calculate human readable timespan. """
    if current is None:
        current = datetime.now()

    timespans = [
        ('millennium', 'millennia',    60*60*24*365*1000),
        ('century', 'centuries',       60*60*24*365*100),
        ('decennium', 'decennia',      60*60*24*365*10),
        ('year', 'years',              60*60*24*365),
        ('month', 'months',            60*60*24*30),
        ('week', 'weeks',              60*60*24*7),
        ('day', 'days',                60*60*24),
        ('hour', 'hours',              60*60),
        ('minute', 'minutes',          60),
        ('second', 'seconds',          1)
    ]

    message = None
    reachstart = None
    delta = int((current - date).total_seconds())

    for i, (singular, plural, seconds) in enumerate(timespans):
        if delta >= seconds:
            n, delta = divmod(delta, seconds)
            if message is not None:
                message += ', '
            else:
                reachstart = i
                message = ''
            message += '{n} {noun}'.format(n=n, noun=plural if n >= 2 else singular)

        if reachstart is not None and reach is not None and i - reachstart + 1 >= reach:
            break

    if message is None:
        message = 'just now'
    else:
        message += ' ago'
    return message

@command(r'seen (\S+)$')
@command(r'have you seen (\S+)(?: lately)?\??$')
def seen(bot, server, target, source, message, parsed, private):
    nick = parsed.group(1)

    if nick == source[0]:
        bot.privmsg(target, _('Asking for yourself?', serv=server, nick=nick))
        return
    elif nick == bot.current_nick:
        bot.privmsg(target, _("I'm right here.", serv=server, nick=nick))
        return

    entry = db.from_('seen').where('nickname', nick).and_('server', server).single('action', 'data', 'time')
    if not entry:
        bot.privmsg(target, _("I don't know who {nick} is.", serv=server, nick=nick))
        return

    message = 'I saw {nick} {timeago}, {action}'
    submessage = None
    action, raw_data, raw_time = entry
    data = json.loads(raw_data)
    time = datetime.strptime(raw_time, db.DATETIME_FORMAT)

    if action == Actions.JOIN:
        submessage = _('joining {chan}.', serv=server, **data)
    elif action == Actions.PART:
        submessage = _('leaving {chan}, with reason "{reason}".', serv=server, **data)
    elif action == Actions.QUIT:
        submessage = _('disconnecting with reason "{reason}".', serv=server, **data)
    elif action == Actions.KICK:
        submessage = _('kicking {target} from {chan} with reason "{reason}".', serv=server, **data)
    elif action == Actions.KICKED:
        submessage = _('getting kicked from {chan} by {kicker} with reason "{reason}".', serv=server, **data)
    elif action == Actions.NICKCHANGE:
        submessage = _('changing nickname to {newnick}.', serv=server, **data)
    elif action == Actions.NICKCHANGED:
        submessage = _('changing nickname from {oldnick}.', serv=server, **data)
    elif action == Actions.MESSAGE:
        submessage = _('telling {chan} "<{nick}> {message}".', serv=server, nick=nick, **data)
    elif action == Actions.NOTICE:
        submessage = _('noticing {chan} "*{nick}* {message}".', serv=server, nick=nick **data)
    elif action == Actions.TOPICCHANGE:
        submessage = _('changing topic for {chan} to "{topic}".', serv=server, **data)
    elif action == Actions.CTCP:
        submessage = _('CTCPing {target}.', serv=server, **data)
    else:
        submessage = _('doing something.', serv=server, **data)

    message = _(message, action=submessage, nick=nick, serv=server, rawtime=time, timeago=timespan(time))
    bot.privmsg(target, message)


## Hooks.
def log(server, nick, what, **data):
    db.from_('seen').where('nickname', nick).and_('server', server).delete()

    db.to('seen').add({
        'server': server,
        'nickname': nick,
        'action': what,
        'data': json.dumps(data),
        'time': datetime.now()
    })

def meify(bot, nick):
    if bot.current_nick == nick:
        return 'me'
    return nick


@hook('irc.join')
def join(bot, server, channel, who):
    log(server, who[0], Actions.JOIN, chan=channel)

@hook('irc.part')
def part(bot, server, channel, who, reason):
    log(server, who[0], Actions.PART, chan=channel, reason=reason)

@hook('irc.quit')
def quit(bot, server, who, reason):
    log(server, who[0], Actions.QUIT, reason=reason)

@hook('irc.kick')
def kick(bot, server, channel, target, by, reason):
    log(server, by[0], Actions.KICK, chan=channel, target=meify(bot, target[0]), reason=reason)
    log(server, target[0], Actions.KICKED, chan=channel, kicker=meify(bot, by[0]), reason=reason)

@hook('irc.nickchange')
def nickchange(bot, server, who, to):
    log(server, who[0], Actions.NICKCHANGE, newnick=to)
    log(server, to[0], Actions.NICKCHANGED, oldnick=who)

@hook('irc.message')
def message(bot, server, target, who, message, private):
    if not private:
        log(server, who[0], Actions.MESSAGE, chan=target, message=message)

@hook('irc.notice')
def notice(bot, server, target, who, message, private):
    if not private:
        log(server, who[0], Actions.NOTICE, chan=target, message=message)

@hook('irc.topicchange')
def topicchange(bot, server, channel, who, topic):
    log(server, who[0], Actions.TOPICCHANGE, chan=channel, topic=topic)

@hook('irc.ctcp')
def ctcp(bot, server, target, who, message):
    log(server, who[0], Actions.CTCP, target=meify(bot, target[0] if isinstance(target, tuple) else target), message=message)


# Module.
def load():
    return True

def unload():
    pass
