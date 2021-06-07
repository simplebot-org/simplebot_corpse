import os
from typing import Optional

import simplebot
from deltachat import Chat, Contact, Message
from simplebot import DeltaBot
from simplebot.bot import Replies

from .orm import Game, Player, init, session_scope

__version__ = "1.0.0"
GAME_BANNER = "💀 Exquisite Corpse\n\n"


@simplebot.hookimpl
def deltabot_start(bot: DeltaBot) -> None:
    path = os.path.join(os.path.dirname(bot.account.db_path), __name__)
    if not os.path.exists(path):
        os.makedirs(path)
    path = os.path.join(path, "sqlite.db")
    init(f"sqlite:///{path}")


@simplebot.hookimpl
def deltabot_member_removed(
    bot: DeltaBot, chat: Chat, contact: Contact, replies: Replies
) -> None:
    with session_scope() as session:
        game = session.query(Game).filter_by(chat_id=chat.id).first()
        if game:
            if bot.self_contact == contact or len(chat.get_contacts()) <= 1:
                session.delete(game)
            else:
                for player in game.players:
                    if player.addr == contact.addr:
                        _remove_from_game(bot, replies, session, player, game)
                        break


@simplebot.filter
def filter_messages(bot: DeltaBot, message: Message, replies: Replies) -> None:
    """Process turns in Exquisite Corpse game groups"""
    if not message.chat.is_group():
        sender = message.get_sender_contact()
        with session_scope() as session:
            player = session.query(Player).filter_by(addr=sender.addr).first()
            if not player or player.game.turn != sender.addr:
                return

            game = player.game

            if len(message.text.split()) < game.words:
                replies.add(
                    text=f"❌ Text too short. Send a message with at least {game.words} words",
                    quote=message,
                )
            else:
                paragraph = game.text + " " + message.text
                game.text = paragraph

                if player.round == game.rounds:
                    game.players.remove(player)
                else:
                    player.round += 1

                p = _get_by_round(game)

                if p is None or p.addr == sender.addr:  # game over
                    replies.add(
                        text=_end_game(session, game),
                        chat=bot.get_chat(game.chat_id),
                    )
                else:
                    game.turn = p.addr
                    _run_turn(bot, replies, p, game, bot.get_chat(game.chat_id))


@simplebot.command
def corpse_new(bot: DeltaBot, payload: str, message: Message, replies: Replies) -> None:
    """Start a new game of Exquisite Corpse.

    You can pass the number of rounds and minimum word count per turn, by
    default the game will have three turns and players must send at least
    ten words each turn. For example, to create a game with six turns and
    a minimum of five words per turn: `/corpse_new 6 5`
    """
    if not message.chat.is_group():
        replies.add(text="❌ This is not a group.", quote=message)
        return

    sender = message.get_sender_contact()
    with session_scope() as session:
        player = session.query(Player).filter_by(addr=sender.addr).first()
        if player:
            replies.add(
                text="❌ You are already playing Exquisite Corpse.", quote=message
            )
            return

        game = session.query(Game).filter_by(chat_id=message.chat.id).first()
        if game:
            replies.add(
                text="❌ There is already a game created in this group.", quote=message
            )
            return

        game = Game(chat_id=message.chat.id, rounds=3, words=10)
        if payload:
            args = list(map(int, payload.split()[:2]))
            game.rounds = args[0]
            if len(args) == 2:
                game.words = args[1]

        if game.rounds < 1 and game.words < 1:
            replies.add(text="❌ Invalid game setup.", quote=message)
        else:
            game.players.append(Player(addr=sender.addr))
            session.add(game)
            replies.add(text=_show_status(bot, game))


@simplebot.command
def corpse_join(bot: DeltaBot, message: Message, replies: Replies) -> None:
    """Join to an Exquisite Corpse game in the group it is sent."""
    if not message.chat.is_group():
        replies.add(text="❌ This is not a group.", quote=message)
        return

    sender = message.get_sender_contact()
    with session_scope() as session:
        game = session.query(Game).filter_by(chat_id=message.chat.id).first()
        if not game:
            replies.add(text="❌ There is no game created in this group.", quote=message)
            return

        player = session.query(Player).filter_by(addr=sender.addr).first()
        if player:
            if player.game.chat_id == game.chat_id:
                replies.add(text="❌ You already joined this game.", quote=message)
            else:
                replies.add(
                    text="❌ You are already playing Exquisite Corpse in another group.",
                    quote=message,
                )
            return

        if (
            game.turn
            and session.query(Player).filter_by(addr=game.turn).first().round > 1
        ):
            replies.add(
                text="⌛ Too late!!! You can't join the game at this time", quote=message
            )
            return

        game.players.append(Player(addr=sender.addr))
        replies.add(text=_show_status(bot, game))


@simplebot.command
def corpse_start(bot: DeltaBot, message: Message, replies: Replies) -> None:
    """Start Exquisite Corpse game."""
    if not message.chat.is_group():
        replies.add(text="❌ This is not a group.", quote=message)
        return

    with session_scope() as session:
        game = session.query(Game).filter_by(chat_id=message.chat.id).first()
        if not game:
            replies.add(text="❌ There is no game created in this group.", quote=message)
            return
        if game.turn:
            replies.add(text="❌ Game already started.", quote=message)
            return
        if len(game.players) <= 1:
            replies.add(text="❌ There is not sufficient players", quote=message)
            return

        player = _get_by_round(game)
        assert player is not None
        game.turn = player.addr
        _run_turn(bot, replies, player, game, message.chat)


@simplebot.command
def corpse_end(message: Message, replies: Replies) -> None:
    """End Exquisite Corpse game."""
    if not message.chat.is_group():
        replies.add(text="❌ This is not a group.", quote=message)
        return

    with session_scope() as session:
        game = session.query(Game).filter_by(chat_id=message.chat.id).first()
        if not game:
            replies.add(text="❌ There is no game created in this group.", quote=message)
            return

        replies.add(text=_end_game(session, game))


@simplebot.command
def corpse_leave(bot: DeltaBot, message: Message, replies: Replies) -> None:
    """Leave the Exquisite Corpse game you are in."""
    sender = message.get_sender_contact()
    with session_scope() as session:
        player = session.query(Player).filter_by(addr=sender.addr).first()
        if player:
            _remove_from_game(bot, replies, session, player, player.game)
            replies.add(text="You abandoned the game.", quote=message)
        else:
            replies.add(text="❌ You are not playing Exquisite Corpse.", quote=message)


@simplebot.command
def corpse_status(bot: DeltaBot, message: Message, replies: Replies) -> None:
    """Show the game status."""
    if not message.chat.is_group():
        replies.add(text="❌ This is not a group.", quote=message)
        return

    with session_scope() as session:
        game = session.query(Game).filter_by(chat_id=message.chat.id).first()
        if game:
            replies.add(text=_show_status(bot, game))
        else:
            replies.add(text="❌ There is no game created in this group.", quote=message)


def _run_turn(
    bot: DeltaBot, replies: Replies, player: Player, game: Game, group: Chat
) -> None:
    contact = bot.get_contact(player.addr)
    replies.add(
        text=f"{GAME_BANNER}⏳ Round {player.round}/{game.rounds}\n\n{contact.name}, it's your turn...",
        chat=group,
    )

    if game.text:
        hint = " ".join(game.text.rsplit(maxsplit=5)[-5:])
        text = f"{GAME_BANNER}📝 Complete the phrase:\n...{hint}\n\n"
    else:
        text = f"{GAME_BANNER}📝 You are the first!\nSend a message with at least {game.words} words."

    replies.add(text, chat=bot.get_chat(contact))


def _show_status(bot: DeltaBot, game: Game) -> str:
    text = f"{GAME_BANNER}⚙️ Settings: ⏳{game.rounds} - 📝{game.words}\n👤 Players({len(game.players)}):\n"

    if game.turn:
        fmt = "• {} ({})\n"
    else:
        fmt = "• {0}\n"
    for player in game.players:
        text += fmt.format(bot.get_contact(player.addr).name, player.round)

    text += "\n"
    if game.turn:
        text += f"Turn: {bot.get_contact(game.turn).name}"
    else:
        text += "Waiting for players...\n\n/corpse_join  /corpse_start"

    return text


def _get_by_round(game: Game) -> Optional[Player]:
    if len(game.players):
        return sorted(game.players, key=lambda p: p.round)[0]


def _end_game(session, game: Game) -> str:
    text = GAME_BANNER
    if game.text:
        text += "⌛ Game finished!\n📜 The result is:\n" + game.text
    else:
        text += "❌ Game aborted"
    session.delete(game)
    return text + "\n\n▶️ Play again? /corpse_new"


def _remove_from_game(
    bot: DeltaBot, replies: Replies, session, player: Player, game: Game
) -> None:
    player_round = player.round
    game.players.remove(player)
    if player.addr == game.turn:
        p = _get_by_round(game)
        chat = bot.get_chat(game.chat_id)
        if p is None or (
            len(game.players) == 1 and (not game.text or p.round > player_round)
        ):
            replies.add(text=_end_game(session, game), chat=chat)
        else:
            game.turn = p.addr
            _run_turn(bot, replies, p, game, chat)
