from types import SimpleNamespace


class FakeBot:
    def __init__(self):
        self.replies = []

    async def reply(self, _message, text):
        self.replies.append(text)


class FakeMessage(SimpleNamespace):
    def __init__(self, text="", user_id="wx-user-1", voices=None):
        super().__init__(text=text, user_id=user_id, voices=voices or [])

