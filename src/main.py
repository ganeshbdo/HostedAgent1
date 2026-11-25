"""A minimal Agent Framework assistant served through Foundry Responses."""

import os
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlsplit

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv


def read_settings(environment: Mapping[str, str]) -> tuple[str, str]:
    names = ("FOUNDRY_PROJECT_ENDPOINT", "AZURE_AI_MODEL_DEPLOYMENT_NAME")
    missing = [name for name in names if not environment.get(name, "").strip()]
    if missing:
        raise ValueError(f"Missing required settings: {', '.join(missing)}")

    endpoint = environment[names[0]].strip()
    deployment = environment[names[1]].strip()
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or "/api/projects/" not in parsed.path
        or not parsed.path.split("/api/projects/", 1)[1].strip("/")
    ):
        raise ValueError(
            "FOUNDRY_PROJECT_ENDPOINT must be an HTTPS project endpoint "
            "ending in /api/projects/<project>."
        )
    return endpoint, deployment


def build_agent(endpoint: str, deployment: str) -> Agent:
    client = FoundryChatClient(
        project_endpoint=endpoint,
        model=deployment,
        credential=DefaultAzureCredential(),
    )
    return Agent(
        client=client,
        name="starter-assistant",
        instructions=(
            "You are a concise, helpful assistant. Explain concepts clearly. "
            "You have no external tools: do not claim to read files, inspect "
            "infrastructure, or perform actions."
        ),
        # The hosting adapter owns conversation history, not the model provider.
        default_options={"store": False},
    )


def main() -> None:
    load_dotenv(Path(__file__).with_name(".env"), override=False)
    endpoint, deployment = read_settings(os.environ)
    ResponsesHostServer(build_agent(endpoint, deployment)).run()


if __name__ == "__main__":
    main()
