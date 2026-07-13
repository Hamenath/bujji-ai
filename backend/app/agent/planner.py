import logging
from typing import List, Dict, Any, Optional
from app.core.config import settings
from app.llm.schemas import Message as LLMMessage, ChatRequest
from app.services.chat_service import chat_service
from app.agent.schemas import ActionPlan, PlanStep
from app.agent.prompts import PLANNER_SYSTEM_PROMPT
from app.agent.router import extract_json
from app.tools.registry import tool_registry
from pydantic import ValidationError
import json

logger = logging.getLogger("app.agent.planner")

class AgentPlanner:
    """Class handling generation of structured multi-step execution plans."""

    async def plan(self, context: List[LLMMessage]) -> ActionPlan:
        """Generates a structured plan of steps to solve the user message using tools."""
        logger.info("Generating action plan...")
        
        tools_list = tool_registry.get_tools_metadata()
        tools_str = json.dumps(tools_list, indent=2)
        
        system_prompt = PLANNER_SYSTEM_PROMPT.format(
            tools_metadata=tools_str,
            max_steps=settings.AGENT_MAX_STEPS
        )

        planner_messages = []
        for i, msg in enumerate(context):
            if i == 0 and msg.role == "system":
                planner_messages.append(LLMMessage(role="system", content=system_prompt))
            else:
                planner_messages.append(LLMMessage(role=msg.role, content=msg.content))
                
        if not planner_messages or planner_messages[0].role != "system":
            planner_messages.insert(0, LLMMessage(role="system", content=system_prompt))

        retries = 0
        max_retries = settings.AGENT_PLANNER_PARSE_RETRIES
        error_msg = "Invalid JSON structure"
        
        while retries <= max_retries:
            content = ""
            try:
                chat_req = ChatRequest(
                    messages=planner_messages,
                    stream=False,
                    options={"temperature": 0.0}
                )
                response = await chat_service.get_chat_completion(chat_req)
                content = response.get("message", {}).get("content", "")
                
                parsed = extract_json(content)
                if parsed:
                    plan = ActionPlan(**parsed)
                    
                    if len(plan.steps) > settings.AGENT_MAX_STEPS:
                        raise ValueError(f"Plan exceeds maximum step limit of {settings.AGENT_MAX_STEPS} steps.")
                        
                    for step in plan.steps:
                        tool = tool_registry.get_tool(step.tool_name)
                        if not tool:
                            raise ValueError(f"Unknown tool '{step.tool_name}' in step {step.id}.")
                        
                        # Validate step arguments, mocking step references for type-checking
                        mock_args = {}
                        for arg_name, arg_val in step.arguments.items():
                            if isinstance(arg_val, dict) and "$from_step" in arg_val:
                                from_step = arg_val.get("$from_step")
                                path = arg_val.get("path")
                                if from_step is None or not isinstance(from_step, int) or from_step <= 0:
                                    raise ValueError(f"Step reference in step {step.id} has invalid '$from_step': must be a positive integer.")
                                if from_step >= step.id:
                                    raise ValueError(f"Step reference in step {step.id} references forward or self step {from_step}.")
                                if not path or not isinstance(path, str) or not path.strip():
                                    raise ValueError(f"Step reference in step {step.id} has invalid or missing 'path'.")
                                if set(arg_val.keys()) - {"$from_step", "path"}:
                                    raise ValueError(f"Step reference in step {step.id} contains unexpected keys: {set(arg_val.keys()) - {'$from_step', 'path'}}")

                                # Mock the argument based on schema definition
                                field_info = tool.input_schema.model_fields.get(arg_name)
                                if field_info:
                                    annotation = field_info.annotation
                                    if annotation is str:
                                        mock_args[arg_name] = "https://dummy-resolved-url.com"
                                    elif annotation is int:
                                        mock_args[arg_name] = 1
                                    elif annotation is float:
                                        mock_args[arg_name] = 1.0
                                    elif annotation is bool:
                                        mock_args[arg_name] = True
                                    else:
                                        mock_args[arg_name] = "dummy"
                                else:
                                    mock_args[arg_name] = "dummy"
                            else:
                                mock_args[arg_name] = arg_val

                        # Validate using tool's input schema
                        tool.input_schema(**mock_args)
                        
                    logger.info(f"Generated valid plan with {len(plan.steps)} steps: {plan.goal}")
                    return plan
                    
                logger.warning(f"Failed to parse plan on attempt {retries + 1}. Content: {content}")
            except Exception as e:
                logger.warning(f"Error in planner execution/validation on attempt {retries + 1}: {e}")
                error_msg = str(e)
                
            retries += 1
            if retries <= max_retries:
                planner_messages.append(LLMMessage(role="assistant", content=content if 'content' in locals() else "Error"))
                planner_messages.append(LLMMessage(role="user", content=f"Your previous response was invalid. Error: {error_msg}. Please reply with ONLY a strict valid JSON object matching the requested schema."))

        raise ValueError(f"Failed to generate a valid action plan after retries. Last error: {error_msg}")

agent_planner = AgentPlanner()
