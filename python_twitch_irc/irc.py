import pendulum
import pydle

from pydle.features import IRCv3Support


# Constants
TS_KEY = 'tmi-sent-ts'
MILLI_TO_SECONDS = 1000


# REALLY BAD FIX FOR ON_MESSAGE (Capability issue)
class IRCv3SupportFix(IRCv3Support):
    def __init__(self, *args):
        super().__init__(*args)
        self._capabilities.update({"echo-message" : True})


# Create a featurized client
BaseIrcClass = pydle.featurize(pydle.features.RFC1459Support, IRCv3SupportFix)

class TwitchIrc(BaseIrcClass):
    def __init__(self, username):

        # Instantiate inherited class
        super().__init__(username)

    async def whisper(self, user, message):
        """
        THIS DOESN'T WORK ANYMORE
        """
        raise NotImplementedError()

    async def message(self, target, message):
        if target[0] == '#':
            await super().message(target, message)
        else:
            await self.whisper(target, message)

    async def action(self, target, message):
        if target[0] == '#':
            await self.message(target, f"\x01ACTION {message}\x01")
        else:  # Again, gimmicky
            await self.whisper(target, f"/me {message}")

    async def timeout(self, channel, user, seconds, reason=None):
        reason = reason or ''

        await self.message(channel, f".timeout {user} {seconds} {reason}")

    async def ban(self, channel, user, reason=None):
        reason = reason or ''

        await self.message(channel, f".ban {user} {reason}")

    async def unban(self, channel, user):
        await self.message(channel, f".unban {user}")

    async def slow(self, channel, seconds):
        await self.message(channel, f".slow {seconds}")

    async def slow_off(self, channel):
        await self.message(channel, ".slowoff")

    async def followers(self, channel, restrict):
        await self.message(channel, f".followers {restrict}")

    async def followers_off(self, channel):
        await self.message(channel, ".followersoff")

    async def subscribers(self, channel):
        await self.message(channel, ".subscribers")

    async def subscribers_off(self, channel):
        await self.message(channel, ".subscribersoff")

    async def clear(self, channel):
        await self.message(channel, f".clear")

    async def r9kbeta(self, channel):
        await self.message(channel, f".r9kbeta")

    async def r9kbeta_off(self, channel):
        await self.message(channel, f".r9kbetaoff")

    async def emoteonly(self, channel):
        await self.message(channel, f".emoteonly")

    async def emoteonly_off(self, channel):
        await self.message(channel, f".emoteonlyoff")

    async def commercial(self, channel, seconds=30):
        await self.message(channel, f".commercial {seconds}")

    async def host(self, channel, target):
        await self.message(channel, f".host {target}")

    async def unhost(self, channel):
        await self.message(channel, f".unhost")

    async def mod(self, channel, user):
        await self.message(channel, f".mod {user}")

    async def unmod(self, channel, user):
        await self.message(channel, f".unmod {user}")

    async def on_unknown(self, message):
        await self._on_handle_twitch(message)

    async def _on_handle_twitch(self, message):
        cmd_to_func = {
            'CLEARCHAT': self.on_raw_twitch_clear_chat,
            'HOSTTARGET': self.on_raw_twitch_host_target,
            'RECONNECT': self.on_raw_twitch_reconnect_cmd,
            'ROOMSTATE': self.on_raw_twitch_roomstate,
            'USERNOTICE': self.on_raw_twitch_usernotice,
            'USERSTATE': self.on_raw_twitch_userstate,
            'WHISPER': self.on_raw_twitch_whisper,
            'NOTICE': self.on_raw_twitch_notice,
            'PRIVMSG': self.on_raw_twitch_privmsg,
        }

        try:
            funct = cmd_to_func[message.command]
        except KeyError:
            await super().on_unknown(message)
        
        # Generate the timestamp if not included
        # in provided tags
        if TS_KEY in message.tags:
            ts = from_twitch_ts(message.tags[TS_KEY])
        else:
            ts = pendulum.now().int_timestamp

        await funct(ts, message)

    # Raw Capabilities
    async def on_raw_twitch_clear_chat(self, timestamp, message):
        if len(message.params) > 1:
            await self.on_channel_ban(timestamp, message.tags, message.params[0], message.params[1])
        else:
            await self.on_cleared_chat(timestamp, message.tags, message.params[0])

    async def on_raw_twitch_host_target(self, timestamp, message):
        host = message.params[0].split('#')[1]
        params = message.params[1].split()
        hostee = params[0]
        viewers = int(params[1]) if params[1] != '-' else 0

        if hostee == '-':
            await self.on_stop_hosting(timestamp, host, viewers)
        else:
            await self.on_hosting(timestamp, host, hostee, viewers)

    async def on_raw_twitch_reconnect_cmd(self, timestamp, message):
        # Call overrideable
        await self.on_reconnect_cmd(timestamp)

    async def on_raw_twitch_roomstate(self, timestamp, message):
        await self.on_roomstate(
            timestamp,
            message.tags,
            message.params[0],
        )

    async def on_raw_twitch_usernotice(self, timestamp, message):
        await self.on_usernotice(
            timestamp,
            message.tags,
            message.params[0],
            message.params[1] if len(message.params) > 1 else '',
        )

    async def on_raw_twitch_userstate(self, timestamp, message):
        await self.on_userstate(
            timestamp,
            message.tags,
            message.params[0],
        )

    async def on_raw_twitch_whisper(self, timestamp, message):
        await self.on_whisper(
            timestamp,
            message.tags,
            parse_user(message.source),
            message.params[1],
        )

    async def on_raw_twitch_notice(self, timestamp, message):
        await self.on_notice(
            timestamp,
            message.tags,
            message.params[0],
            message.params[1],
        )

    async def on_raw_twitch_privmsg(self, timestamp, message):
        await self.on_message(
            timestamp,
            message.tags,
            message.params[0],
            parse_user(message.source),
            message.params[1],
        )

    # Capabilities
    # These cause the client to request the twitch capabilities
    async def on_capability_twitch_tv_membership_available(self, value):
        return True

    async def on_capability_twitch_tv_tags_available(self, value):
        return True

    async def on_capability_twitch_tv_commands_available(self, value):
        return True

    # Raw IRC codes and commands
    async def on_raw_004(self, msg):
        """
        Twitch IRC does not match what the pydle library expects
        which causes Pydle to raise exceptions.
        Override on_raw_004 and prevent super call
        """
        pass

    async def on_raw_421(self, message):
        """
        Twitch doesn't support WHO/WHOIS,
        so ignore errors from those commands
        """
        if message.params[1] in {'WHO', 'WHOIS'}:
            pass
        else:
            await super().on_raw_421(message)

    async def on_raw_notice(self, message):
        """
        NOTICE is technically a capabilities issue but
        Pydle does not return tags so override it and pass the
        arguments we want
        """
        await self._on_handle_twitch(message)

    async def on_raw_privmsg(self, message):
        """
        Pydle does not returns tags so override on_raw_privmsg
        without calling the super (as this client redefines on_message
        and calls would likely break everything)
        """
        await self._on_handle_twitch(message)

    # Overrideables
    async def on_cleared_chat(self, timestamp, tags, channel):
        pass

    async def on_channel_ban(self, timestamp, tags, channel, user):
        pass

    async def on_hosting(self, timestamp, host, hostee, viewers):
        pass

    async def on_stop_hosting(self, timestamp, host, viewers):
        pass

    async def on_notice(self, timestamp, tags, channel, message):
        pass

    async def on_reconnect_cmd(self, timestamp):
        pass

    async def on_roomstate(self, timestamp, tags, channel):
        pass

    async def on_usernotice(self, timestamp, tags, channel, message):
        pass

    async def on_userstate(self, timestamp, tags, channel):
        pass

    async def on_whisper(self, timestamp, tags, user, message):
        pass

    async def on_message(self, timestamp, tags, channel, user, message):
        pass


# Utility
def from_twitch_ts(ts):
    return int(ts) // MILLI_TO_SECONDS


def parse_user(source):
    return source.split('!')[0]
