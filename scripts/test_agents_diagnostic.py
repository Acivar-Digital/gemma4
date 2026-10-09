import asyncio
from pathlib import Path
from adk_submission.compiler import compile_submission
from swegemma.models import setup_gemma_model_registry
from swegemma.context import SwegemmaContext
from swegemma.sandbox.subprocess import SubprocessManager
from google.adk.runners import Runner, RunConfig
from google.adk.apps import App
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

SUBMISSION_DIR = Path("my_submission")

import re

async def test_agent(agent, agent_name: str):
    app_name = re.sub(r"[^a-zA-Z0-9_]", "_", f"diag_{agent_name.lower()}")
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=app_name,
        user_id="user",
        state={},
    )
    app = App(name=app_name, root_agent=agent)
    runner = Runner(app=app, session_service=session_service)

    msg = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text="What tools, skills, and permissions do you have? List them in detail.")],
    )

    print(f"\n{'=' * 60}")
    print(f"DIAGNOSTIC TEST: {agent_name.upper()}")
    print(f"{'=' * 60}")
    async for event in runner.run_async(
        user_id="user",
        session_id=session.id,
        new_message=msg,
        run_config=RunConfig(max_llm_calls=2),
    ):
        content = getattr(event, "content", None)
        if content and content.parts:
            for p in content.parts:
                if p.text:
                    print(p.text)
                if p.function_call:
                    print(f"TOOL CALL: {p.function_call.name}({p.function_call.args})")

async def main():
    served_model = os.getenv("SWEGEMMA_MODEL", "gemma-4-31b-it-qat-w4a16-ct")
    allow_proxy = os.getenv("SWEGEMMA_ALLOW_PROXY", "0").lower() in ("1", "true", "yes")
    if served_model != "gemma-4-31b-it-qat-w4a16-ct" and not allow_proxy:
        raise ValueError(
            f"Refusing proxy model in diagnostic test: '{served_model}'. "
            f"Must be 'gemma-4-31b-it-qat-w4a16-ct' unless SWEGEMMA_ALLOW_PROXY=1."
        )
    models = setup_gemma_model_registry(
        api_base=os.getenv("SWEGEMMA_API_BASE", "http://literouter.lan:7766/v1"),
        api_key=os.getenv("SWEGEMMA_API_KEY", "EMPTY"),
        served_model=served_model,
    )
    mgr = SubprocessManager(system_site_packages=True)
    sb_id = mgr.start()
    context = SwegemmaContext(
        docker_manager=mgr,
        container_id=sb_id,
        problem_statement="Main & Supervisor diagnostic test",
    )
    tools = context.create_tools()

    main_agent = compile_submission(
        submission_dir=SUBMISSION_DIR,
        tool_registry=tools,
        model_registry=models,
    )

    # 1. Test Main
    await test_agent(main_agent, "Main Developer Agent")

    # 2. Test Subagents (if present)
    subagent_tools = [t for t in main_agent.tools if hasattr(t, "agent")]
    for sat in subagent_tools:
        sub_name = getattr(sat.agent, "name", "Subagent")
        await test_agent(sat.agent, sub_name)

    mgr.stop(sb_id)

if __name__ == "__main__":
    asyncio.run(main())
