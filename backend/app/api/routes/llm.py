import json
import logging
import platform
import subprocess
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.llm.schemas import (
    GenerateRequest, 
    ChatRequest, 
    GenerateResponse, 
    ChatResponse, 
    PullModelRequest,
    Message
)
from app.llm.model_router import model_router
from app.services.chat_service import chat_service

logger = logging.getLogger("app.api.routes.llm")

router = APIRouter(prefix="/llm", tags=["LLM / AI Brain"])

def detect_hardware() -> Dict[str, Any]:
    """Helper to dynamically fetch basic hardware specifications for local model recommendations."""
    hardware = {
        "cpu": "Unknown CPU",
        "gpu": [],
        "ram_gb": 16.0,
        "recommendations": []
    }
    
    # 1. Detect CPU
    try:
        hardware["cpu"] = platform.processor() or "Unknown CPU"
        if platform.system() == "Windows":
            cpu_out = subprocess.check_output("wmic cpu get name", shell=True).decode()
            lines = [line.strip() for line in cpu_out.split("\n") if line.strip()]
            if len(lines) > 1:
                hardware["cpu"] = lines[1]
    except Exception as e:
        logger.debug(f"Failed to detect CPU name: {e}")
        
    # 2. Detect RAM
    try:
        if platform.system() == "Windows":
            ram_out = subprocess.check_output("wmic ComputerSystem get TotalPhysicalMemory", shell=True).decode()
            lines = [line.strip() for line in ram_out.split("\n") if line.strip()]
            if len(lines) > 1 and lines[1].isdigit():
                hardware["ram_gb"] = round(int(lines[1]) / (1024**3), 2)
    except Exception as e:
        logger.debug(f"Failed to detect physical memory size: {e}")

    # 3. Detect GPU
    try:
        if platform.system() == "Windows":
            gpu_out = subprocess.check_output("wmic path win32_VideoController get name", shell=True).decode()
            lines = [line.strip() for line in gpu_out.split("\n") if line.strip()]
            hardware["gpu"] = lines[1:] if len(lines) > 1 else []
    except Exception as e:
        logger.debug(f"Failed to detect GPUs: {e}")
        
    # 4. Generate Recommendations
    gpu_names_lower = [g.lower() for g in hardware["gpu"]]
    has_nvidia = any("nvidia" in g for g in gpu_names_lower)
    
    if has_nvidia:
        is_low_vram = any("t400" in g or "1030" in g or "1050" in g or "1650" in g or "2gb" in g or "4gb" in g or "mobile" in g for g in gpu_names_lower)
        if is_low_vram:
            hardware["recommendations"] = [
                "llama3.2:3b (Recommended: Fits comfortably in 4GB VRAM)",
                "qwen2.5:3b (Recommended: Excellent code understanding and logic)",
                "llama3.2:1b (Extremely fast, very low resource footprint)",
                "llama3:8b (Runs, but will spill into system memory causing slow inference)"
            ]
        else:
            hardware["recommendations"] = [
                "llama3.1:8b (Recommended: Premium balanced local model)",
                "qwen2.5:7b (Recommended: Outstanding coding capabilities)",
                "llama3.2:3b (Highly responsive smaller model)"
            ]
    else:
        hardware["recommendations"] = [
            "llama3.2:3b (Recommended: Balanced intelligence/speed for CPU execution)",
            "llama3.2:1b (Recommended: Ultra-fast CPU execution)",
            "qwen2.5:1.5b (Fast multilingual/reasoning model for low-spec CPUs)"
        ]
        
    return hardware

@router.get("/status")
async def get_status():
    """Checks active provider status, system hardware specifications, and returns recommendations."""
    provider = model_router.active_provider
    is_available = await provider.check_availability()
    hardware = detect_hardware()
    
    local_models = []
    if is_available:
        local_models = await provider.get_local_models()
        
    return {
        "ollama_status": "online" if is_available else "offline",
        "base_url": settings.OLLAMA_BASE_URL,
        "default_model": settings.OLLAMA_MODEL,
        "hardware_detected": hardware,
        "installed_models": local_models
    }

@router.get("/models")
async def list_models():
    """Lists all local models currently downloaded in the active provider."""
    provider = model_router.active_provider
    is_available = await provider.check_availability()
    if not is_available:
        raise HTTPException(status_code=503, detail="Active LLM provider service is not reachable.")
        
    models = await provider.get_local_models()
    return {"models": models}

@router.post("/models/pull")
async def pull_model(payload: PullModelRequest):
    """Pulls a model using the active provider, streaming the progress."""
    provider = model_router.active_provider
    is_available = await provider.check_availability()
    if not is_available:
        raise HTTPException(status_code=503, detail="Active LLM provider service is not reachable.")

    async def progress_generator():
        try:
            stream = await provider.pull_model(payload.name)
            async for chunk in stream:
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as e:
            logger.error(f"Error pulling model {payload.name}: {e}")
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(progress_generator(), media_type="text/event-stream")

@router.post("/generate", response_model=GenerateResponse)
async def generate_text(payload: GenerateRequest):
    """
    Generates text based on a single prompt.
    Supports standard JSON response or Server-Sent Events (SSE) streaming output.
    """
    provider = model_router.active_provider
    is_available = await provider.check_availability()
    if not is_available:
        raise HTTPException(status_code=503, detail="Active LLM provider service is not reachable.")

    if payload.stream:
        async def event_generator():
            try:
                stream = await chat_service.generate_completion(payload)
                async for chunk in stream:
                    resp_chunk = {
                        "text": chunk.get("response", ""),
                        "model": chunk.get("model", payload.model or settings.OLLAMA_MODEL),
                        "done": chunk.get("done", False)
                    }
                    yield f"data: {json.dumps(resp_chunk)}\n\n"
            except Exception as e:
                logger.error(f"Streaming text generation failed: {e}")
                yield f"data: {json.dumps({'text': '', 'model': '', 'done': True, 'error': str(e)})}\n\n"
                
        return StreamingResponse(event_generator(), media_type="text/event-stream")
    else:
        try:
            raw_response = await chat_service.generate_completion(payload)
            return GenerateResponse(
                text=raw_response.get("response", ""),
                model=raw_response.get("model", payload.model or settings.OLLAMA_MODEL),
                done=raw_response.get("done", True)
            )
        except Exception as e:
            logger.error(f"Text generation failed: {e}")
            raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")

@router.post("/chat", response_model=ChatResponse)
async def chat_completion(payload: ChatRequest):
    """
    Handles multi-turn conversational exchanges with message histories.
    Supports standard JSON response or Server-Sent Events (SSE) streaming output.
    """
    provider = model_router.active_provider
    is_available = await provider.check_availability()
    if not is_available:
        raise HTTPException(status_code=503, detail="Active LLM provider service is not reachable.")

    if payload.stream:
        async def event_generator():
            try:
                stream = await chat_service.get_chat_completion(payload)
                async for chunk in stream:
                    message_chunk = chunk.get("message", {})
                    resp_chunk = {
                        "message": {
                            "role": message_chunk.get("role", "assistant"),
                            "content": message_chunk.get("content", "")
                        },
                        "model": chunk.get("model", payload.model or settings.OLLAMA_MODEL),
                        "done": chunk.get("done", False)
                    }
                    yield f"data: {json.dumps(resp_chunk)}\n\n"
            except Exception as e:
                logger.error(f"Streaming chat failed: {e}")
                yield f"data: {json.dumps({'message': {'role': 'assistant', 'content': ''}, 'model': '', 'done': True, 'error': str(e)})}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")
    else:
        try:
            raw_response = await chat_service.get_chat_completion(payload)
            message_data = raw_response.get("message", {})
            return ChatResponse(
                message=Message(
                    role=message_data.get("role", "assistant"),
                    content=message_data.get("content", "")
                ),
                model=raw_response.get("model", payload.model or settings.OLLAMA_MODEL),
                done=raw_response.get("done", True)
            )
        except Exception as e:
            logger.error(f"Chat completion failed: {e}")
            raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")
