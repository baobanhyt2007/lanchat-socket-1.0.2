"""Slash-command dispatcher. The console thread calls handle_line()."""

HELP_TEXT = """[*] Commands:
    /list                 show online peers (number, name, IP, status)
    /chat <name|number>   open (or switch to) a chat with that peer
    /send <file>          send a file to the current chat partner
    /leave                close the current chat
    /status <online|away> change your presence status (sent via UDP)
    /help                 show this help
    /quit                 leave the network and exit

    Any other line is sent as a chat message."""


def handle_line(app, line):
    text = (line or "").strip()
    if not text:
        return
    if not text.startswith("/"):
        app.send_chat_message(text)
        return

    command, _, argument = text.partition(" ")
    command = command.lower()
    argument = argument.strip()

    if command == "/list":
        app.show_peer_list()
    elif command == "/chat":
        if not argument:
            app.console.show("[!] Usage: /chat <name|number>  (see /list)")
            return
        app.start_chat(argument)
    elif command == "/send":
        if not argument:
            app.console.show("[!] Usage: /send <path-to-file>")
            return
        app.send_file(argument)
    elif command == "/leave":
        if app.session.partner is None:
            app.console.show("[!] You are not in a chat. Use /chat <name>.")
        else:
            app.session.leave()
    elif command == "/status":
        app.set_status(argument)
    elif command == "/help":
        app.console.show(HELP_TEXT)
    elif command == "/quit":
        app.shutdown()
    else:
        app.console.show(
            "[!] Unknown command %r. Type /help for the command list." % command)
