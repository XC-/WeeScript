# -*- coding: UTF-8 -*-
__author__ = 'Aki Mäkinen'

import weechat
import uuid

_LICENSE = "MIT"
_AUTHOR = "Aki Makinen"
_VERSION = "1.1.0"


_LOG_LEVELS = ["DEBUG", "INFO", "NOTICE", "WARNING", "ERR", "CRIT", "ALERT", "EMERG"]


class WS(object):
    LOG_LEVELS = {v: k for k, v in enumerate(_LOG_LEVELS)}
    MSG_CMD = "PRIVMSG"
    LOG_PREFIXES = {
        LOG_LEVELS["DEBUG"]: "/(^.^)/ DEBUG: ",
        LOG_LEVELS["INFO"]: "~ INFO ~: ",
        LOG_LEVELS["NOTICE"]: "~ NOTICE ~: ",
        LOG_LEVELS["WARNING"]: "== WARNING ==: ",
        LOG_LEVELS["ERR"]: "=! ERROR !=: ",
        LOG_LEVELS["CRIT"]: "!! CRITICAL !!: ",
        LOG_LEVELS["ALERT"]: "!!!! ALERT !!!!: ",
        LOG_LEVELS["EMERG"]: "UNHOLY S#!&, BATMAN!: "
    }

    LOG_COLORS = {
        LOG_LEVELS["DEBUG"]: weechat.color("blue"),
        LOG_LEVELS["INFO"]: weechat.color("chat"),
        LOG_LEVELS["NOTICE"]: weechat.color("chat"),
        LOG_LEVELS["WARNING"]: weechat.color("orange"),
        LOG_LEVELS["ERR"]: weechat.color("red"),
        LOG_LEVELS["CRIT"]: weechat.color("black,red"),
        LOG_LEVELS["ALERT"]: weechat.color("_black,red"),
        LOG_LEVELS["EMERG"]: weechat.color("_orange,red")
    }

    DEFAULT_LOG_COLOR = weechat.color("chat")

    @staticmethod
    def parse_message(signal):
        parts = signal.split()
        if WS.MSG_CMD not in parts:
            return {
                "type": "OTHER",
                "raw": signal
            }
        else:
            cmd_index = parts.index(WS.MSG_CMD)
            return {
                "type": WS.MSG_CMD,
                "raw": signal,
                "channel": parts[cmd_index + 1],
                "msg": parts[cmd_index + 2:]
            }

    @staticmethod
    def log(*args, **kwargs):
        level = kwargs.get("log_level", WS.LOG_LEVELS["INFO"])
        string = WS.LOG_PREFIXES[level] + ", ".join(map(str, args))
        color_coded = WS.LOG_COLORS[level] + string + WS.DEFAULT_LOG_COLOR
        weechat.prnt("", color_coded)

    def __init__(self, *args, **kwargs):
        self.name = {
            "short": kwargs.get("name_short", "WeeScript"),
            "long": kwargs.get("name_long", "WeeScript framework")
        }
        self.version = kwargs.get("version", _VERSION)
        self.author = kwargs.get("author", _AUTHOR)

        self.global_scope = self.get_globals()

        self.activations = {}
        self.commands = {}
        self.weechat_commands = {}

        self.in_hooks = {}
        self.out_hooks = {}
        self.buffers = {}

        self.logging_level = WS.LOG_LEVELS["DEBUG"]
        weechat.register(self.name["short"], self.author, self.version, _LICENSE, "", "", "")
        self.register_weechat_command(
            self.name["short"] + "_settings",
            "Set channel and network for the script to use",
            "[network add/del [network]] | [channel add/del [network channel]] | [list_channels] | [log_level list, set [level]]",
            "network eg. IRCnet or freenode, channel eg. #foobar",
            "network | add | del || channel | add | del || list_channels || log_level | set | list",
            self.handle_setup_commands
        )

    def log_debug(self, *args):
        if self.logging_level <= WS.LOG_LEVELS["DEBUG"]:
            WS.log(*args, log_level=WS.LOG_LEVELS["DEBUG"])

    def log_info(self, *args):
        if self.logging_level <= WS.LOG_LEVELS["INFO"]:
            WS.log(*args, log_level=WS.LOG_LEVELS["INFO"])

    def log_notice(self, *args):
        if self.logging_level <= WS.LOG_LEVELS["NOTICE"]:
            WS.log(*args, log_level=WS.LOG_LEVELS["NOTICE"])

    def log_warning(self, *args):
        if self.logging_level <= WS.LOG_LEVELS["WARNING"]:
            WS.log(*args, log_level=WS.LOG_LEVELS["WARNING"])

    def log_err(self, *args):
        if self.logging_level <= WS.LOG_LEVELS["ERR"]:
            WS.log(*args, log_level=WS.LOG_LEVELS["ERR"])

    def log_crit(self, *args):
        if self.logging_level <= WS.LOG_LEVELS["CRIT"]:
            WS.log(*args, log_level=WS.LOG_LEVELS["CRIT"])

    def log_alert(self, *args):
        if self.logging_level <= WS.LOG_LEVELS["ALERT"]:
            WS.log(*args, log_level=WS.LOG_LEVELS["ALERT"])

    def log_emerg(self, *args):
        if self.logging_level <= WS.LOG_LEVELS["EMERG"]:
            WS.log(*args, log_level=WS.LOG_LEVELS["EMERG"])

    def add_network(self, *args):
        if len(args) < 1:
            self.log_info("Network is required.")
            return

        network = args[0]
        if network not in self.activations:
            self.activations[network] = set()

            def func(*args):
                return self.handle_msg_cb(*args, network=network)

            f_name = "{}_{}".format("msgcb", uuid.uuid4())
            self.global_scope[f_name] = func
            self.in_hooks[network] = weechat.hook_signal(network + ",irc_in2_PRIVMSG", f_name, "")
            self.out_hooks[network] = weechat.hook_signal(network + ",irc_out1_PRIVMSG", f_name, "")
            self.log_info("Added network {}.".format(network))
            self.list_networks()

    def register_weechat_command(self, cmd, cmd_desc, cmd_arg_list, arg_desc, arg_autofill, cb):
        if cmd in self.weechat_commands:
            self.log_info("Weechat command already exists.")
            return

        def func(*args):
            return self.handle_weechat_command(*args, command=cmd)

        f_name = "{}_{}".format(cmd, uuid.uuid4())
        self.global_scope[f_name] = func

        hook = weechat.hook_command(cmd, cmd_desc, cmd_arg_list, arg_desc, arg_autofill, f_name, "")
        self.weechat_commands[cmd] = {
            "func_name": f_name,
            "func": cb,
            "hook": hook
        }
        self.log_info("Weechat command {} registered.".format(cmd))

    def handle_weechat_command(self, *args, **kwargs):
        command = kwargs.get("command", None)
        if command is None:
            self.log_err("No command defined.")
            return weechat.WEECHAT_RC_ERROR
        try:
            self.weechat_commands[command]["func"](args[2].split())
            return weechat.WEECHAT_RC_OK
        except KeyError:
            pass

        return weechat.WEECHAT_RC_OK

    def add_channel_to_network(self, *args):
        if len(args) < 2:
            self.log_info("Network and channel both are required.")
            return
        network = args[0]
        channel = args[1]
        if network in self.activations and channel in self.activations[network]:
            self.log_info("Network and channel already active.")
            return

        if network not in self.activations:
            self.add_network(network)

        self.activations[network].add(channel)
        self.buffers[(network, channel)] = weechat.info_get("irc_buffer", network + "," + channel)
        self.log_info("Channel added.")
        self.list_channels()

    def add_command_to_channel(self, network, channel, command, func):
        id_tuple = (network, channel, command)
        if id_tuple not in self.commands:
            self.commands[id_tuple] = func
        else:
            self.log_info("Command {} already exists on channel {}@{}. Please remove the existing one first."
                          .format(command, channel, network))

    def remove_network(self, network):
        if network in self.activations:
            weechat.unhook(self.in_hooks[network])
            weechat.unhook(self.out_hooks[network])

            del self.activations[network]
            del self.in_hooks[network]
            del self.out_hooks[network]
            self.remove_commands(network=network)
            self.log_info("Network removed.")
            self.list_channels()
        else:
            self.log_info("Network {} not found.".format(network))

    def remove_channel_from_network(self, network, channel):
        if network in self.activations and channel in self.activations[network]:
            self.activations[network].remove(channel)
            self.list_channels(network)
            self.remove_commands(network=network, channel=channel)
        else:
            self.log_info("Network and/or channel not found.")

    def remove_commands(self, **kwargs):
        network = kwargs.get("network", None)
        channel = kwargs.get("channel", None)
        for key, cb in self.commands.items():
            if network == key[0]:
                if channel is None or channel == key[1]:
                    self.remove_command_from_channel(*key)

    def remove_command_from_channel(self, network, channel, command):
        id_tuple = (network, channel, command)
        if id_tuple not in self.commands:
            self.log_info("Command {} not found from the channel {}@{}.".format(command, channel, network))
        else:
            del self.commands[id_tuple]

    def set_logging_level(self, level):
        if level in _LOG_LEVELS:
            self.logging_level = WS.LOG_LEVELS[level]
            self.log_info("Current level: {}.".format(_LOG_LEVELS[self.logging_level]))
        else:
            self.log_err("Incorrect log level.")

    def list_networks(self):
        self.log("Active networks:")
        for i in self.activations:
            self.log(i)

    def list_channels(self, network=None):
        self.log("Active networks and channels:")

        if not network:
            for n, c in self.activations.items():
                self.log("{}: {}".format(n, sorted(list(c))))
        else:
            if network in self.activations:
                self.log("{}: {}".format(network, sorted(list(self.activations[network]))))
            else:
                self.log("Network {} not found.".format(network))

    def list_logging_levels(self):
        self.log("Logging levels: {}".format(_LOG_LEVELS))
        self.log("Current level: {}.".format(_LOG_LEVELS[self.logging_level]))

    def handle_setup_commands(self, params):
        cmd = params[0]
        handlers = {
            "network": {
                "add": self.add_network,
                "del": self.remove_network
            },
            "channel": {
                "add": self.add_channel_to_network,
                "del": self.remove_channel_from_network
            },
            "list_channels": self.list_channels,
            "log_level": {
                "set": self.set_logging_level,
                "list": self.list_logging_levels
            }
        }
        try:
            if callable(handlers[cmd]):
                handlers[cmd](*params[1:])
            elif cmd in handlers:
                sub = params[1]
                if callable(handlers[cmd][sub]):
                    handlers[cmd][sub](*params[2:])
                else:
                    self.log_err("Only two level commands supported currently.")
            else:
                self.log_err("Command not recognized.")
        except KeyError:
            self.log_warning("Command {} not found.".format(cmd))

    def handle_msg_cb(self, data, signal, signal_data, **kwargs):
        nw = kwargs.get("network", None)
        if nw is None:
            self.log_err("Network missing.")
            return weechat.WEECHAT_RC_ERROR

        if nw in self.activations:
            parsed_data = WS.parse_message(signal_data)
            if parsed_data["channel"] in self.activations[nw]:
                try:
                    id_tup = (nw, parsed_data["channel"], parsed_data["msg"][0][1:])
                    self.log_debug(id_tup)
                    if id_tup in self.commands:
                        self.commands[id_tup]({"network": nw, "channel": parsed_data["channel"]},
                                              parsed_data["msg"][1:])
                except IndexError:
                    pass
        return weechat.WEECHAT_RC_OK

    def send_message_to_channel(self, target, msg):
        id_tup = (target["network"], target["channel"])
        buf = self.buffers.get(id_tup, None)
        if buf is not None:
            weechat.command(buf, unicode(msg).encode("utf-8").strip())
        else:
            self.log_err("Channel buffer was not found.")

    # I am so going to Hell for this. Those who have been my teachers, please look away... please... now... do it...
    def get_globals(self):
        return globals()
