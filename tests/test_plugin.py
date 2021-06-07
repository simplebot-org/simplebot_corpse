class TestPlugin:
    def test_new(self, mocker) -> None:
        settings = "⏳{} - 📝{}"

        msg = mocker.get_one_reply(
            "/corpse_new", addr="test0@example.org", group="group0"
        )
        assert settings.format(3, 10) in msg.text

        msg = mocker.get_one_reply("/corpse_new")
        assert "❌" in msg.text

        msg = mocker.get_one_reply("/corpse_new 1 2", group="group1")
        assert settings.format(1, 2) in msg.text
        chat = msg.chat

        msg = mocker.get_one_reply("/corpse_new", group="group2")
        assert "❌" in msg.text

        msg = mocker.get_one_reply("/corpse_new", addr="test1@example.org", group=chat)
        assert "❌" in msg.text

    def test_gameplay(self, mocker) -> None:
        chat = mocker.get_one_reply("/corpse_new 1 2", group="group1").chat

        msg = mocker.get_one_reply("/corpse_join", addr="test1@example.org", group=chat)
        assert "❌" not in msg.text

        msgs = mocker.get_replies("/corpse_start", group=chat)
        assert len(msgs) == 2

        # player #1 is turn, but text is too short
        msg = mocker.get_one_reply("hello")
        assert "❌" in msg.text
        # player #2 can't play in player #1 is turn
        msgs = mocker.get_replies("hello world", addr="test1@example.org")
        assert not msgs
        # player #1 is turn, valid text
        msgs = mocker.get_replies("hello world")
        assert len(msgs) == 2

        # player #2 is turn
        msg = mocker.get_one_reply("from the test land", addr="test1@example.org")
        assert "Game finished" in msg.text
        assert "hello world from the test land" in msg.text

    def test_end(self, mocker) -> None:
        chat = mocker.get_one_reply("/corpse_new 1 2", group="group1").chat
        mocker.get_one_reply("/corpse_join", addr="test1@example.org", group=chat)

        msg = mocker.get_one_reply("/corpse_end", group=chat)
        assert "Game aborted" in msg.text

        chat = mocker.get_one_reply("/corpse_new 1 2", group="group1").chat
        mocker.get_one_reply("/corpse_join", addr="test1@example.org", group=chat)

        mocker.get_replies("/corpse_start", group=chat)
        mocker.get_replies("hello world")

        msg = mocker.get_one_reply("/corpse_end", group=chat)
        assert "hello world" in msg.text

    def test_leave(self, mocker) -> None:
        chat = mocker.get_one_reply("/corpse_new 1 2", group="group1").chat
        mocker.get_one_reply("/corpse_join", addr="test1@example.org", group=chat)
        mocker.get_one_reply("/corpse_join", addr="test2@example.org", group=chat)

        msg = mocker.get_one_reply(
            "/corpse_leave", addr="test2@example.org", group=chat
        )
        assert "❌" not in msg.text

        mocker.get_replies("/corpse_start", group=chat)

        msg = mocker.get_one_reply(
            "/corpse_status", addr="test1@example.org", group=chat
        )
        assert "❌" not in msg.text

        # game ended so an aditional message is sent in group
        msgs = mocker.get_replies("/corpse_leave", group=chat)
        assert len(msgs) == 2

        msg = mocker.get_one_reply(
            "/corpse_status", addr="test1@example.org", group=chat
        )
        assert "❌" in msg.text

    def test_status(self, mocker) -> None:
        chat = mocker.get_one_reply("/corpse_new 1 2", group="group1").chat
        msg = mocker.get_one_reply("/corpse_status", group=chat)
        assert "❌" not in msg.text

        mocker.get_one_reply("/corpse_end", group=chat)

        msg = mocker.get_one_reply("/corpse_status", group=chat)
        assert "❌" in msg.text
