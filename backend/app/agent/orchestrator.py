import logging
import json
import uuid
import asyncio
from datetime import datetime, timezone
from typing import AsyncIterator, Dict, Any, List, Optional

from app.core.config import settings
from app.llm.schemas import Message as LLMMessage, ChatRequest
from app.services.chat_service import chat_service
from app.agent.schemas import AgentState, RouterDecision, ActionPlan, PlanStep
from app.agent.router import agent_router
from app.agent.planner import agent_planner
from app.agent.executor import agent_executor
from app.agent.observer import agent_observer
from app.agent.prompts import FINAL_ANSWER_SYSTEM_PROMPT

logger = logging.getLogger("app.agent.orchestrator")

def get_action_fingerprint(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Serializes tool arguments canonically to create a stable action fingerprint."""
    serialized = json.dumps(arguments, sort_keys=True)
    return f"{tool_name}:{serialized}"

def is_step_reference(val: Any) -> bool:
    return isinstance(val, dict) and "$from_step" in val

def validate_step_reference(val: Dict[str, Any], current_step_id: int) -> None:
    if not isinstance(val, dict):
        raise ValueError("Step reference must be a dictionary.")
    if "$from_step" not in val:
        raise ValueError("Step reference must contain '$from_step'.")
    from_step = val["$from_step"]
    if not isinstance(from_step, int) or from_step <= 0:
        raise ValueError("'$from_step' must be a positive integer.")
    if from_step >= current_step_id:
        raise ValueError(f"Forward or self reference rejected: step {from_step} >= current step {current_step_id}.")
    if "path" not in val:
        raise ValueError("Step reference must contain 'path'.")
    if not isinstance(val["path"], str) or not val["path"].strip():
        raise ValueError("'path' must be a non-empty string.")
    allowed_keys = {"$from_step", "path"}
    extra_keys = set(val.keys()) - allowed_keys
    if extra_keys:
        raise ValueError(f"Step reference contains invalid keys: {extra_keys}")

def resolve_path(data: Any, path: str) -> Any:
    parts = path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            if part not in current:
                raise ValueError(f"Path part '{part}' not found in dict.")
            current = current[part]
        elif isinstance(current, list):
            try:
                idx = int(part)
                if idx < 0 or idx >= len(current):
                    raise ValueError(f"Index {idx} out of bounds for list.")
                current = current[idx]
            except ValueError as e:
                if "invalid literal for int()" in str(e):
                    raise ValueError(f"Expected list index, got '{part}'.")
                raise
        else:
            raise ValueError(f"Cannot resolve path part '{part}' on non-container type.")
    return current

def normalize_url(url: str) -> str:
    import urllib.parse
    try:
        parsed = urllib.parse.urlparse(url)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        if scheme == "http" and netloc.endswith(":80"):
            netloc = netloc[:-3]
        elif scheme == "https" and netloc.endswith(":443"):
            netloc = netloc[:-4]
        path = parsed.path
        if not path:
            path = "/"
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]
        query = parsed.query
        if query:
            q_params = urllib.parse.parse_qsl(query, keep_blank_values=True)
            filtered_params = [(k, v) for k, v in q_params if not k.lower().startswith("utm_")]
            query = urllib.parse.urlencode(filtered_params)
        return urllib.parse.urlunparse(urllib.parse.ParseResult(
            scheme=scheme,
            netloc=netloc,
            path=path,
            params=parsed.params,
            query=query,
            fragment=""
        ))
    except Exception:
        return url

def sanitize_url(url: str) -> str:
    try:
        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        if not parsed.query:
            return url
        params = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        sensitive_keys = {"token", "api_key", "apikey", "key", "access_token", "auth", "password", "signature", "sig"}
        sanitized_params = []
        for k, v in params:
            if k.lower() in sensitive_keys:
                sanitized_params.append((k, "REDACTED"))
            else:
                sanitized_params.append((k, v))
        new_query = urllib.parse.urlencode(sanitized_params)
        reconstructed = urllib.parse.ParseResult(
            scheme=parsed.scheme,
            netloc=parsed.netloc,
            path=parsed.path,
            params=parsed.params,
            query=new_query,
            fragment=parsed.fragment
        )
        return urllib.parse.urlunparse(reconstructed)
    except Exception:
        return url

def sanitize_value(val: Any) -> Any:
    if isinstance(val, str):
        if val.startswith(("http://", "https://")) and "?" in val:
            return sanitize_url(val)
        return val
    elif isinstance(val, dict):
        return {k: sanitize_value(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [sanitize_value(v) for v in val]
    return val

def clean_citations(text: str, valid_ids: List[int]) -> str:
    import re
    pattern = r"\[(\d+)\]"
    def replacer(match):
        cit_id = int(match.group(1))
        if cit_id in valid_ids:
            return f"[{cit_id}]"
        return ""
    return re.sub(pattern, replacer, text)

class AgentOrchestrator:
    """Central coordinator executing the routing, planning, tool running, and response loop."""

    async def execute(
        self,
        conversation_id: str,
        user_message: str,
        context: List[LLMMessage],
        stream: bool = False
    ) -> AsyncIterator[tuple[str, Dict[str, Any]]]:
        """
        Executes the agent loop as an asynchronous generator yielding event tuples:
        (event_type, event_data)
        """
        run_id = str(uuid.uuid4())
        logger.info(f"Starting agent run {run_id} for conversation {conversation_id}")
        
        # 1. Initialize state
        state = AgentState(
            run_id=run_id,
            conversation_id=conversation_id,
            user_message=user_message,
            context=[{"role": msg.role, "content": msg.content} for msg in context],
            status="routing"
        )
        
        yield "agent.started", {"run_id": run_id, "conversation_id": conversation_id}

        try:
            # 2. Structured Routing
            state.status = "routing"
            decision = await agent_router.route(context)
            state.route = decision.route
            
            yield "agent.route.selected", {
                "route": decision.route,
                "reason_code": decision.reason_code
            }

            if decision.route == "direct":
                # Direct route: bypass planning and call chat service directly
                state.status = "generating_final"
                chat_req = ChatRequest(messages=context, stream=stream)
                
                if stream:
                    response_stream = await chat_service.get_chat_completion(chat_req)
                    accumulated_content = []
                    async for chunk in response_stream:
                        content_chunk = chunk.get("message", {}).get("content", "")
                        if content_chunk:
                            accumulated_content.append(content_chunk)
                            yield "response.chunk", {"content": content_chunk}
                    state.final_response = "".join(accumulated_content)
                else:
                    response = await chat_service.get_chat_completion(chat_req)
                    res_content = response.get("message", {}).get("content", "")
                    state.final_response = res_content
                    yield "response.chunk", {"content": res_content}
                
                state.status = "completed"
                state.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                yield "agent.completed", {
                    "run_id": run_id,
                    "status": "completed",
                    "final_response": state.final_response,
                    "sources": []
                }
                return

            # Agent route: Structured Planning and Tool Execution Loop
            state.status = "planning"
            try:
                plan = await agent_planner.plan(context)
                state.plan = plan
            except Exception as e:
                logger.error(f"Planning failed: {e}")
                yield "agent.failed", {"run_id": run_id, "error_code": "PLANNER_ERROR"}
                return

            yield "agent.plan.created", {
                "step_count": len(plan.steps),
                "steps": [{"id": s.id, "description": s.description, "tool_name": s.tool_name} for s in plan.steps]
            }

            # Loop Detection & Executions State
            action_fingerprints: Dict[str, int] = {}
            step_idx = 0
            steps = plan.steps
            total_steps = len(steps)
            
            pages_read_count = 0
            source_candidates = []
            state.status = "executing"

            while step_idx < total_steps:
                current_step: PlanStep = steps[step_idx]
                state.current_step = current_step.id

                # Enforce step limits
                if current_step.id > settings.AGENT_MAX_STEPS:
                    logger.error(f"Step limit exceeded ({current_step.id} > {settings.AGENT_MAX_STEPS})")
                    yield "agent.failed", {"run_id": run_id, "error_code": "STEP_LIMIT_REACHED"}
                    return

                # Resolve any step references in arguments
                resolved_arguments = {}
                for arg_name, arg_val in current_step.arguments.items():
                    if is_step_reference(arg_val):
                        try:
                            validate_step_reference(arg_val, current_step.id)
                        except Exception as e:
                            logger.error(f"Invalid step reference: {e}")
                            yield "agent.failed", {"run_id": run_id, "error_code": "INVALID_STEP_REFERENCE"}
                            return

                        from_step = arg_val["$from_step"]
                        path = arg_val["path"]

                        # Find completed step
                        prior_step = next((s for s in state.completed_steps if s["step_number"] == from_step), None)
                        if not prior_step:
                            logger.error(f"Reference to incomplete or non-existent step {from_step}")
                            yield "agent.failed", {"run_id": run_id, "error_code": "SOURCE_NOT_AVAILABLE"}
                            return

                        # Resolve path
                        try:
                            root_data = {"data": prior_step["result"]}
                            resolved_val = resolve_path(root_data, path)
                            if resolved_val is None:
                                raise ValueError("Resolved value is None.")
                        except Exception as e:
                            logger.error(f"Failed to resolve path '{path}' on step {from_step} output: {e}")
                            yield "agent.failed", {"run_id": run_id, "error_code": "INVALID_STEP_REFERENCE"}
                            return

                        resolved_arguments[arg_name] = resolved_val
                    else:
                        resolved_arguments[arg_name] = arg_val

                # Update arguments of the step in-place
                current_step.arguments = resolved_arguments

                # Calculate fingerprint & check loop limits
                fingerprint = get_action_fingerprint(current_step.tool_name, current_step.arguments)
                action_fingerprints[fingerprint] = action_fingerprints.get(fingerprint, 0) + 1
                
                if action_fingerprints[fingerprint] > (settings.AGENT_MAX_DUPLICATE_ACTIONS + 1):
                    logger.error(f"Duplicate action / loop detected on tool '{current_step.tool_name}' with args {current_step.arguments}")
                    yield "agent.failed", {"run_id": run_id, "error_code": "DUPLICATE_ACTION_DETECTED"}
                    return

                retry_count = state.retry_counts.get(current_step.id, 0)

                yield "tool.started", {
                    "step_number": current_step.id,
                    "tool_name": current_step.tool_name
                }

                # Enforce webpage read limit
                from app.tools.base import ToolResult
                if current_step.tool_name == "webpage_reader" and pages_read_count >= settings.WEB_MAX_PAGES_PER_RUN:
                    logger.warning(f"Webpage read limit reached ({pages_read_count} >= {settings.WEB_MAX_PAGES_PER_RUN}). Failing this step.")
                    result = ToolResult(
                        success=False,
                        error="RESPONSE_TOO_LARGE",
                        metadata={"duration_ms": 0}
                    )
                else:
                    if current_step.tool_name == "webpage_reader":
                        pages_read_count += 1
                    
                    # Execute step
                    result = await agent_executor.execute_step(current_step)

                duration_ms = result.metadata.get("duration_ms", 0) if result.metadata else 0

                # Observe result
                state.status = "observing"
                obs_decision = agent_observer.observe(
                    current_step,
                    result,
                    total_steps,
                    retry_count
                )

                # Persist step details in memory state with secrets redacted
                step_record = {
                    "step_number": current_step.id,
                    "tool_name": current_step.tool_name,
                    "arguments": sanitize_value(current_step.arguments),
                    "result": sanitize_value(result.data) if result.success else None,
                    "success": result.success,
                    "duration_ms": duration_ms,
                    "error_code": result.error
                }
                
                state.tool_calls.append(step_record)
                
                # Sanitize event argument and result payload to prevent leaks
                event_args = sanitize_value(current_step.arguments)
                event_res = sanitize_value(result.data) if result.data else {}
                
                # Prune content body for webpage_reader to prevent bloat in events
                if current_step.tool_name == "webpage_reader" and "content" in event_res:
                    event_res = event_res.copy()
                    event_res["content"] = "[BODY PRUNED FOR EVENTS]"

                if obs_decision.decision == "continue":
                    state.completed_steps.append(step_record)
                    state.observations.append({"step_number": current_step.id, "result": result.data})
                    
                    # Aggregate sources on success
                    if result.success:
                        if current_step.tool_name == "web_search" and result.data and "results" in result.data:
                            for r in result.data["results"]:
                                source_candidates.append({
                                    "title": r.get("title", "Untitled"),
                                    "url": r.get("url"),
                                    "domain": r.get("domain", ""),
                                    "snippet": r.get("snippet", ""),
                                    "source_type": "search_result"
                                })
                        elif current_step.tool_name == "webpage_reader" and result.data:
                            source_candidates.append({
                                "title": result.data.get("title", "Untitled Page"),
                                "url": result.data.get("url"),
                                "domain": result.data.get("domain", ""),
                                "snippet": result.data.get("content", "")[:200],
                                "source_type": "webpage"
                            })

                    yield "tool.completed", {
                        "step_number": current_step.id,
                        "tool_name": current_step.tool_name,
                        "success": True,
                        "duration_ms": duration_ms,
                        "arguments": event_args,
                        "result": event_res
                    }
                    step_idx += 1
                    state.status = "executing"
                
                elif obs_decision.decision == "complete":
                    state.completed_steps.append(step_record)
                    state.observations.append({"step_number": current_step.id, "result": result.data})
                    
                    if result.success:
                        if current_step.tool_name == "web_search" and result.data and "results" in result.data:
                            for r in result.data["results"]:
                                source_candidates.append({
                                    "title": r.get("title", "Untitled"),
                                    "url": r.get("url"),
                                    "domain": r.get("domain", ""),
                                    "snippet": r.get("snippet", ""),
                                    "source_type": "search_result"
                                })
                        elif current_step.tool_name == "webpage_reader" and result.data:
                            source_candidates.append({
                                "title": result.data.get("title", "Untitled Page"),
                                "url": result.data.get("url"),
                                "domain": result.data.get("domain", ""),
                                "snippet": result.data.get("content", "")[:200],
                                "source_type": "webpage"
                            })

                    yield "tool.completed", {
                        "step_number": current_step.id,
                        "tool_name": current_step.tool_name,
                        "success": True,
                        "duration_ms": duration_ms,
                        "arguments": event_args,
                        "result": event_res
                    }
                    step_idx += 1
                    break
                
                elif obs_decision.decision == "retry":
                    state.retry_counts[current_step.id] = retry_count + 1
                    yield "tool.failed", {
                        "step_number": current_step.id,
                        "tool_name": current_step.tool_name,
                        "success": False,
                        "duration_ms": duration_ms,
                        "arguments": event_args,
                        "error_code": result.error or "TOOL_FAILED"
                    }
                    yield "agent.retry", {
                        "step_number": current_step.id,
                        "attempt": retry_count + 2,
                        "reason_code": obs_decision.reason_code
                    }
                    state.status = "executing"
                
                elif obs_decision.decision == "fail":
                    yield "tool.failed", {
                        "step_number": current_step.id,
                        "tool_name": current_step.tool_name,
                        "success": False,
                        "duration_ms": duration_ms,
                        "arguments": event_args,
                        "error_code": result.error or "TOOL_FAILED"
                    }
                    yield "agent.failed", {
                        "run_id": run_id,
                        "error_code": result.error or "EXECUTION_FAILED"
                    }
                    return

            # Deduplicate and normalize collected sources
            deduped_map = {}
            for src in source_candidates:
                if not src.get("url"):
                    continue
                norm_url = normalize_url(src["url"])
                if norm_url not in deduped_map:
                    deduped_map[norm_url] = src
                else:
                    if src["source_type"] == "webpage":
                        deduped_map[norm_url] = src

            final_sources = []
            for idx, (norm_url, src) in enumerate(deduped_map.items(), start=1):
                final_sources.append({
                    "id": idx,
                    "title": src["title"],
                    "url": src["url"],
                    "domain": src["domain"],
                    "snippet": src["snippet"],
                    "accessed_at": datetime.now(timezone.utc).isoformat(),
                    "source_type": src["source_type"]
                })
            
            state.sources = final_sources
            if final_sources:
                yield "agent.sources.ready", {"sources": final_sources}

            # 4. Generate Final Answer grounded in observations
            state.status = "generating_final"
            
            obs_text_parts = []
            for item in state.completed_steps:
                obs_text_parts.append(
                    f"Step {item['step_number']} (Tool: {item['tool_name']}):\n"
                    f"Arguments: {json.dumps(item['arguments'])}\n"
                    f"Observation result: [UNTRUSTED USER-GENERATED CONTENT START]\n{json.dumps(item['result']) if item['success'] else 'Failed: ' + str(item['error_code'])}\n[UNTRUSTED USER-GENERATED CONTENT END]\n"
                )
            
            sources_prompt = ""
            if final_sources:
                sources_prompt = "\nAvailable Sources for Citation:\n" + "\n".join(
                    f"[{src['id']}] Title: {src['title']}\n    URL: {src['url']}\n    Snippet: {src['snippet']}"
                    for src in final_sources
                )
            
            observations_str = "\n".join(obs_text_parts) + sources_prompt
            
            system_prompt = FINAL_ANSWER_SYSTEM_PROMPT.format(
                user_message=state.user_message,
                observations=observations_str
            )
            
            # Build chat messages
            final_messages = [
                LLMMessage(role="system", content=system_prompt)
            ]
            for msg in context[:-1]:
                if msg.role != "system":
                    final_messages.append(LLMMessage(role=msg.role, content=msg.content))
            final_messages.append(LLMMessage(role="user", content=state.user_message))
            
            chat_req = ChatRequest(messages=final_messages, stream=stream)
            
            if stream:
                response_stream = await chat_service.get_chat_completion(chat_req)
                accumulated_content = []
                async for chunk in response_stream:
                    content_chunk = chunk.get("message", {}).get("content", "")
                    if content_chunk:
                        accumulated_content.append(content_chunk)
                        yield "response.chunk", {"content": content_chunk}
                state.final_response = "".join(accumulated_content)
            else:
                response = await chat_service.get_chat_completion(chat_req)
                res_content = response.get("message", {}).get("content", "")
                state.final_response = res_content
                yield "response.chunk", {"content": res_content}
                
            # Post-process citations
            valid_ids = [src["id"] for src in final_sources]
            state.final_response = clean_citations(state.final_response, valid_ids)

            state.status = "completed"
            state.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            yield "agent.completed", {
                "run_id": run_id,
                "status": "completed",
                "final_response": state.final_response,
                "sources": final_sources
            }

        except asyncio.CancelledError:
            logger.warning(f"Agent run {run_id} was cancelled.")
            yield "agent.failed", {
                "run_id": run_id,
                "error_code": "AGENT_CANCELLED"
            }
            raise
        except Exception as e:
            logger.error(f"Orchestrator error in run {run_id}: {e}", exc_info=True)
            yield "agent.failed", {
                "run_id": run_id,
                "error_code": "INTERNAL_ERROR"
            }

# Global orchestrator instance
agent_orchestrator = AgentOrchestrator()
