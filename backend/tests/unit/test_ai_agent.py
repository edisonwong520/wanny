from unittest.mock import AsyncMock, patch

from django.test import SimpleTestCase

from comms.ai import AIAgent


class AIAgentTest(SimpleTestCase):
    def test_generate_json_returns_raw_response_when_model_output_is_not_json(self):
        agent = AIAgent()
        agent.provider = "openai"
        agent.model = "fake-model"
        agent._openai_client = type(
            "FakeClient",
            (),
            {
                "chat": type(
                    "FakeChat",
                    (),
                    {
                        "completions": type(
                            "FakeCompletions",
                            (),
                            {
                                "create": AsyncMock(
                                    return_value=type(
                                        "FakeResponse",
                                        (),
                                        {
                                            "choices": [
                                                type(
                                                    "FakeChoice",
                                                    (),
                                                    {
                                                        "message": type(
                                                            "FakeMessage",
                                                            (),
                                                            {"content": "你好！有什么我可以帮你的吗？ 😊"},
                                                        )()
                                                    },
                                                )()
                                            ]
                                        },
                                    )()
                                )
                            },
                        )()
                    },
                )()
            },
        )()

        result = self.async_run(agent.generate_json("system", "user"))

        self.assertEqual(result["type"], "simple")
        self.assertEqual(result["error"], "invalid_json")
        self.assertEqual(result["raw_response"], "你好！有什么我可以帮你的吗？ 😊")

    def async_run(self, coroutine):
        import asyncio

        return asyncio.run(coroutine)
