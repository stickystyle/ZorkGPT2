"""Agent action: generate next game action via LLM with structured output."""
from __future__ import annotations
import logging
import instructor
from burr.core import action, State
from zorkburr.config import GameConfig
from zorkburr.llm.models import AgentResponse
from zorkburr.llm.prompts import load_prompt
from zorkburr.state import S
from zorkburr.utils import clean_action

logger = logging.getLogger(__name__)
_system_prompt: str | None = None

def _get_system_prompt(knowledge_base: str = "") -> str:
    global _system_prompt
    if _system_prompt is None:
        _system_prompt = load_prompt("agent")
    prompt = _system_prompt
    if knowledge_base:
        marker = "**Output Format"
        if marker in prompt:
            guide = (
                "\n\n**STRATEGIC GUIDE FROM PREVIOUS EPISODES:**\n"
                f"{knowledge_base}\n"
                "**END OF STRATEGIC GUIDE**\n\n"
            )
            prompt = prompt.replace(marker, guide + marker)
    return prompt

@action(
    reads=[S.FORMATTED_CONTEXT, S.REJECTION_COUNT, S.CRITIC_JUSTIFICATION, S.KNOWLEDGE_BASE, S.TURN_COUNT],
    writes=[S.PROPOSED_ACTION, S.AGENT_REASONING, S.NEW_OBJECTIVE, S.ACTION_TO_TAKE],
)
def generate_action(state: State, client: instructor.Instructor, config: GameConfig) -> tuple[dict, State]:
    """Ask the agent LLM for the next action. Returns validated AgentResponse."""
    system = _get_system_prompt(state[S.KNOWLEDGE_BASE])
    user_content = state[S.FORMATTED_CONTEXT]

    if state[S.REJECTION_COUNT] > 0:
        feedback = state[S.CRITIC_JUSTIFICATION]
        user_content += (
            f"\n\n**Your previous action was rejected (attempt {state[S.REJECTION_COUNT]}).**\n"
            f"Reason: {feedback}\nPlease propose a DIFFERENT action."
        )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]

    try:
        response: AgentResponse = client.create(
            model=config.agent_model,
            response_model=AgentResponse,
            messages=messages,
            temperature=config.default_temperature,
            max_tokens=config.default_max_tokens,
            max_retries=3,
        )
        action_text = clean_action(response.action)
        reasoning = response.thinking
        new_objective = response.new_objective
    except Exception as e:
        logger.error(f"Agent LLM call failed: {e}")
        action_text = "look"
        reasoning = f"LLM error: {e}"
        new_objective = ""

    new_state = state.update(**{
        S.PROPOSED_ACTION: action_text,
        S.AGENT_REASONING: reasoning,
        S.NEW_OBJECTIVE: new_objective,
        S.ACTION_TO_TAKE: action_text,
    })
    return {"action": action_text}, new_state


# Expose .run for test compatibility (delegates to run_and_update on the FunctionBasedAction)
generate_action.run = generate_action.action_function.run_and_update
