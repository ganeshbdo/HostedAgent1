import os
import tempfile
import unittest
from collections.abc import Awaitable, Mapping, Sequence
from typing import Any
from unittest.mock import patch

from agent_framework import (
    BaseChatClient,
    ChatResponse,
    ChatResponseUpdate,
    Content,
    Message,
    ResponseStream,
)
from agent_framework_foundry_hosting import ResponsesHostServer
from httpx import ASGITransport, AsyncClient
from src.main import build_agent, read_settings


class SettingsTests(unittest.TestCase):
    def test_reports_missing_setting_names(self) -> None:
        with self.assertRaisesRegex(
            ValueError, "FOUNDRY_PROJECT_ENDPOINT, AZURE_AI_MODEL_DEPLOYMENT_NAME"
        ):
            read_settings({})
        with self.assertRaisesRegex(ValueError, "AZURE_AI_MODEL_DEPLOYMENT_NAME"):
            read_settings(
                {
                    "FOUNDRY_PROJECT_ENDPOINT": (
                        "https://example.services.ai.azure.com/api/projects/demo"
                    ),
                    "AZURE_AI_MODEL_DEPLOYMENT_NAME": " ",
                }
            )

    def test_rejects_non_project_or_credential_bearing_endpoints(self) -> None:
        for endpoint in (
            "http://example.services.ai.azure.com/api/projects/demo",
            "https://example.services.ai.azure.com",
            "https://example.services.ai.azure.com/api/projects/",
            "https://user:password@example.com/api/projects/demo",
            "https://example.com/api/projects/demo?key=example",
        ):
            with self.subTest(endpoint=endpoint), self.assertRaisesRegex(
                ValueError, "HTTPS project endpoint"
            ):
                read_settings(
                    {
                        "FOUNDRY_PROJECT_ENDPOINT": endpoint,
                        "AZURE_AI_MODEL_DEPLOYMENT_NAME": "demo-deployment",
                    }
                )

    def test_uses_configured_deployment_without_substituting_a_model(self) -> None:
        endpoint, deployment = read_settings(
            {
                "FOUNDRY_PROJECT_ENDPOINT": (
                    " https://example.services.ai.azure.com/api/projects/demo "
                ),
                "AZURE_AI_MODEL_DEPLOYMENT_NAME": " my-existing-deployment ",
            }
        )
        self.assertEqual(
            endpoint, "https://example.services.ai.azure.com/api/projects/demo"
        )
        self.assertEqual(deployment, "my-existing-deployment")


class OfflineChatClient(BaseChatClient):
    def _inner_get_response(
        self,
        *,
        messages: Sequence[Message],
        stream: bool,
        options: Mapping[str, Any],
        **kwargs: Any,
    ) -> Awaitable[ChatResponse] | ResponseStream[ChatResponseUpdate, ChatResponse]:
        update = ChatResponseUpdate(
            role="assistant",
            contents=[Content.from_text("Offline hosted-agent reply.")],
            response_id="offline-model-response",
        )

        async def updates():
            yield update

        async def response() -> ChatResponse:
            return ChatResponse.from_updates([update])

        if stream:
            return ResponseStream(updates(), finalizer=ChatResponse.from_updates)
        return response()


class HostedWiringTests(unittest.IsolatedAsyncioTestCase):
    async def test_agent_answers_through_responses_without_cloud_access(self) -> None:
        with (
            tempfile.TemporaryDirectory() as state_root,
            patch.dict(
                os.environ,
                {
                    "AGENTSERVER_STATE_ROOT": state_root,
                    "OTEL_SDK_DISABLED": "true",
                },
                clear=True,
            ),
            patch("socket.socket.connect", side_effect=AssertionError("Network forbidden")),
            patch("subprocess.Popen", side_effect=AssertionError("Subprocess forbidden")),
            patch("src.main.DefaultAzureCredential"),
            patch("src.main.FoundryChatClient", return_value=OfflineChatClient()),
        ):
            agent = build_agent(
                "https://example.services.ai.azure.com/api/projects/demo",
                "offline-deployment",
            )
            server = ResponsesHostServer(agent)
            async with (
                server.router.lifespan_context(server),
                AsyncClient(
                    transport=ASGITransport(app=server), base_url="http://offline"
                ) as client,
            ):
                response = await client.post(
                    "/responses",
                    json={"input": "Hello", "stream": False, "store": False},
                )

            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["status"], "completed")
            texts = [
                part["text"]
                for item in body["output"]
                if item["type"] == "message"
                for part in item["content"]
                if part["type"] == "output_text"
            ]
            self.assertEqual(texts, ["Offline hosted-agent reply."])
