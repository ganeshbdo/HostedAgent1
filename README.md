# Hosted agent starter: from a repository to a Foundry source ZIP

A small teaching repository for publishing a Python **Microsoft Agent Framework**
agent as a **Microsoft Foundry hosted agent**, using **Foundry Toolkit for VS Code**.
The sample is a conversational assistant with **no tools or infrastructure access**.

This is the **source-code / ZIP** deployment path: no Dockerfile, local Docker,
container registry, Fabric workspace, MCP server, or Toolbox is required.
Hosted agents and some tooling are preview features; verify support in your
project's region and installed extension before deploying.

## 1. Understand the two boundaries

```text
Repository workspace                 Source package
  README + azure.yaml                 main.py
  src/ + tests + package script  -->   requirements.txt at the ZIP root
                                            |
                                            v
                                 Foundry remote dependency build
                                            |
                                            v
                                 Hosted Responses endpoint
```

**The documented VS Code workflow takes a source directory and creates the ZIP
for you.** It is not a generic "upload an arbitrary ZIP" command. Open this
repository root in VS Code and deploy its `src` directory through the wizard.

The included packaging script produces the equivalent flat source payload for
inspection, sharing, or a later SDK/REST upload. It does **not** deploy the agent.
If you receive only that ZIP, extract it into a source directory and configure
a workspace before using the extension. A ZIP does not carry the project,
runtime, protocol, or environment settings declared in `azure.yaml`.

## 2. Know what each file does

```text
hosted-agent-starter/
  README.md                 This walkthrough
  azure.yaml                Project binding and hosted-agent service settings
  .gitignore                Keeps local settings and generated files out of Git
  .gitattributes            Keeps text line endings consistent across platforms
  src/                      The deployment source root
    main.py                 Agent logic and Responses server entry point
    requirements.txt        Direct dependency pins and approved package index
    .agentignore            Source-package allowlist used by the extension
    .env.example            Blank local-development configuration template
  scripts/
    package.py              Reproducible, source-only ZIP builder
  tests/
    test_agent.py           Configuration and offline Responses wiring
    test_package.py         Flat layout, exclusions and reproducibility
  dist/                     Generated locally; never committed
    agent-code.zip
```

Keep everything the agent imports inside the deployment source directory.
The host cannot import modules that exist only elsewhere in your repository.
Documentation, tests and packaging helpers are not runtime inputs.

## 3. Prepare your environment and Azure resources

You need:

- VS Code and [Microsoft Foundry Toolkit](https://aka.ms/foundrytk), including
  its prerequisites; install/update the official Microsoft extension.
- An **existing Foundry project** in a region supporting hosted agents.
- An **existing Responses-capable model deployment** in that project. Use the
  deployment name, not a model catalog name.
- **Foundry Project Manager** or equivalent project deployment permission.
  Users who only invoke the deployed agent need suitable invocation permissions,
  such as **Foundry Agent Consumer**.
- An existing Python **3.13** interpreter for matching local and hosted execution.
- Azure CLI **2.80+** for local sign-in.

In VS Code, select that interpreter with **Python: Select Interpreter**. In a
terminal at the repository root, install the sample dependencies:

```powershell
python --version
python -s -m pip install --index-url https://packagefeedproxy.microsoft.io/pypi/simple -r .\src\requirements.txt
```

Select an existing suitable environment; this repository does not create one.
If your package policy differs, review the index directive deliberately rather
than adding an unapproved fallback. The remote build must also reach this index.
Direct dependencies are pinned, including a prerelease hosting adapter.
Transitive dependencies are resolved by pip; this is not a fully locked build.

For optional local execution, copy the blank template only when the target
does not already exist:

```powershell
if (-not (Test-Path .\src\.env)) {
    Copy-Item .\src\.env.example .\src\.env
}
```

Fill these two settings in `src/.env`:

```dotenv
FOUNDRY_PROJECT_ENDPOINT=https://<account>.services.ai.azure.com/api/projects/<project>
AZURE_AI_MODEL_DEPLOYMENT_NAME=<existing-model-deployment-name>
```

There are no API keys in this sample. The local process uses
`DefaultAzureCredential`; an Azure CLI sign-in is one supported local credential.
Environment variables take precedence over the local file. Never print or
commit credentials.

## 4. Turn your agent into a hosted application

The important parts of `src/main.py` are:

1. **Configuration:** reject missing endpoint/deployment settings explicitly;
   do not silently fall back to a sample model.
2. **Model client:** use `FoundryChatClient` with `DefaultAzureCredential`.
3. **Agent:** supply your instructions to `Agent`. This sample deliberately
   registers no tools.
4. **Protocol adapter:** wrap the agent in `ResponsesHostServer`, then call
   `run()`. A script that only prints a reply and exits is not a hosted server.
5. **Conversation ownership:** `store=False` disables provider-side storage;
   the hosting adapter handles the caller's Responses conversation state.

The hosting library implements the Responses protocol, health endpoints and
port **8088**. Do not replace it with an unrelated web server or declare a
protocol that your application does not actually implement.

To adapt your own code, replace the instructions and agent construction.
Put extra Python modules/assets under `src`, declare dependencies in
`src/requirements.txt`, and update **both** `src/.agentignore` and the
packaging script's `SOURCE_FILES` allowlist. Keep optional integrations out
of the first startup test.

## 5. Check locally and inspect the ZIP

Run the offline checks from the repository root after installing dependencies:

```powershell
python -s -m unittest discover -s .\tests -v
python -s .\scripts\package.py
python -s -m zipfile -l .\dist\agent-code.zip
```

The ZIP must have exactly this initial layout, with **no wrapper directory**:

```text
agent-code.zip
  main.py
  requirements.txt
```

The script prints its SHA-256 and includes only explicit runtime inputs.
It excludes local environment files, caches and other unexpected files by
construction. Rebuilding unchanged inputs produces the same bytes and hash.
Review the source itself too: ignore rules do not detect hard-coded secrets.

The extension applies the separate source-root `.agentignore`. That file
replaces `.gitignore` and `.dockerignore` for source packaging, so keep its
allowlist correct. Do not ZIP the entire repository or include a virtual
environment, Windows binary dependencies, run history or local credentials.

### Optional live local check

This calls Azure and can incur model charges. Perform it only when intended:

```powershell
az login
python -s .\src\main.py
```

In a second terminal:

```powershell
$Body = @{
    input = "Explain what a hosted agent is in two sentences."
    stream = $false
    store = $false
} | ConvertTo-Json
$Response = Invoke-RestMethod -Uri http://127.0.0.1:8088/responses `
    -Method Post -ContentType 'application/json' -Body $Body
if ($Response.status -ne 'completed') {
    throw 'The Responses turn did not complete. Inspect the response and server logs.'
}
$Response.output
```

The local sample server is not an authenticated public gateway. Use it only
on a trusted development machine, protect the listening port, and stop it
with Ctrl+C when finished.

## 6. Deploy through VS Code: Code + Remote

Open the **repository root**, not just `src` or the ZIP:

```powershell
code .
```

Review `azure.yaml` before deployment:

| Setting | This starter |
| --- | --- |
| Agent source (`project`) | `src` |
| Agent kind | `hosted` |
| Runtime | `python_3_13` |
| Entry-point filename | `main.py` |
| Dependency resolution | `remote_build` |
| Protocol | `responses`, version `2.0.0` |
| CPU / memory | `0.5` / `1Gi` |
| Agent name | `hosted-agent-starter-dev`; use a unique dev name initially |
| Declared deployment variable | `AZURE_AI_MODEL_DEPLOYMENT_NAME` |

`codeConfiguration` selects ZIP deployment. The current unified schema still
uses `language: docker` for the hosted service; this does **not** request a
Docker build when `codeConfiguration` is present. There is no image or Docker
build configuration in this repository.

The project service's endpoint binds to an existing project. Do **not** declare
`FOUNDRY_PROJECT_ENDPOINT` under the agent's `env`: Foundry injects the correct
runtime endpoint. Do not override reserved `FOUNDRY_` or `AGENT_` variables.
The model deployment is declared explicitly and must exist in the target project.

Deployment steps:

1. Sign into Azure in the extension and select the intended default project.
   Confirm the tenant, subscription and project; do not deploy to an accidental
   default destination.
2. Set the existing model deployment in `src/.env` or the process environment.
   If using `azd` as well, set its corresponding active-environment variables.
3. Run **Foundry Toolkit: Deploy Hosted Agent** from the Command Palette,
   or select **Developer Tools > Build > Deploy to Microsoft Foundry**.
4. Complete **Foundry Project Setup** if shown.
5. On **Basics**, select **Code**, **Remote**, and **New agent**.
6. Enter your dev agent name and select **Next**.
7. On **Review + Deploy**, confirm the source is `src`, the runtime is
   **Python 3.13**, and the effective startup command is **`python3 main.py`**.
   `azure.yaml` supplies the entry-point filename, not a shell command string.
   Also verify the protocol, model deployment, CPU and memory.
8. Select **Deploy** and watch notifications and **Output**. The extension
   packages source, uploads it, and Foundry installs the declared requirements.
9. Wait for the numbered agent version to reach **active** before testing it.

The wizard can save configuration even if deployment fails. A ZIP, a saved
wizard form, or an accepted create request is not evidence of a running agent.
This path does not require an ACR or provision one.

## 7. Verify the actual hosted version

Under **My Resources > Agents > Hosted Agent**, select the newly deployed
**numbered version**, not an ambiguous automatic/latest selection.

1. Confirm its status and model configuration on **Details**.
2. Open **Playground** and ask the same question as the local check.
3. Verify the response actually completes; a health check or HTTP 200 alone
   does not prove model inference works.
4. Inspect **Sessions** and logs if the request fails. Provisioning/dependency
   build errors are separate from runtime session logs.

The deployed runtime uses a **platform-created agent identity**, not your
local Azure CLI credentials. Model access through the project is provided by
the platform; external resources require their own reviewed permissions.
Nothing in this sample passes through an end user's identity to external tools.

To update, edit and test the code, then select **Existing agent** to create a
new immutable version. Test that version and review endpoint routing before
promoting it. Keep a known-good version available for rollback.

## 8. Common mistakes

| Symptom | Check |
| --- | --- |
| Missing settings at startup | Supply a real project endpoint locally and declare an existing model deployment for hosting. |
| `ModuleNotFoundError` remotely | Include every imported local module; check pins, remote-build output and package-index network access. |
| Source files omitted | Update the `.agentignore` allowlist and the manual ZIP allowlist together. |
| Runtime/entry-point failure | Select Python 3.13 and `main.py`; avoid a wrapper directory in the ZIP. |
| Version fails during provisioning | Read its error and the build output; session logs cannot diagnose a container that never started. |
| Local call works, hosted call fails | Compare the model deployment, runtime identity, dependencies and network access. |
| Agent claims an action | This sample has no tools; model prose is not evidence that an action occurred. |

Bundled ZIP deployment is a different mode: install matching **Linux x86_64**
dependencies into `packages/` and change dependency resolution deliberately.
Do not bundle a Windows environment. Start with **Remote** for this sample.

## Official references

The deployment contract and extension steps were checked against these sources
on 2026-11-25. Product labels and preview APIs can change.

- [Deploy a hosted agent from source code](https://learn.microsoft.com/azure/foundry/agents/how-to/deploy-hosted-agent-code)
- [Foundry Toolkit source-deployment walkthrough](https://learn.microsoft.com/azure/foundry/how-to/develop/vs-code-agents-workflow-pro-code#deploy-the-hosted-agent)
- [Host Agent Framework agents in Foundry](https://learn.microsoft.com/azure/foundry/how-to/develop/framework-hosted-agents?pivots=programming-language-python)
- [Unified azure.yaml reference](https://learn.microsoft.com/azure/foundry/agents/concepts/azure-yaml-reference)
- [Hosted-agent permissions](https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agent-permissions)

This repository and its ZIP are local deliverables. Creating them does not
publish a GitHub repository, sign into Azure, or deploy cloud resources.
