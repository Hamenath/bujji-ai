from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class Message(BaseModel):
    """A single chat message with a role and content."""
    role: str = Field(description="The role of the message sender (e.g., 'system', 'user', 'assistant')")
    content: str = Field(description="The text content of the message")

class GenerateRequest(BaseModel):
    """Request schema for text generation from a single prompt."""
    prompt: str = Field(..., description="The main prompt string to send to the LLM")
    model: Optional[str] = Field(default=None, description="Overrides the default configured model name")
    system_prompt: Optional[str] = Field(default=None, description="Optional system instructions/rules for the model")
    options: Optional[Dict[str, Any]] = Field(default=None, description="Additional model parameters (e.g., temperature, top_k)")
    stream: bool = Field(default=False, description="Whether to stream the response back in chunks")

class ChatRequest(BaseModel):
    """Request schema for chat conversational completion using a history of messages."""
    messages: List[Message] = Field(..., description="A sequence of dialogue messages representing chat history")
    model: Optional[str] = Field(default=None, description="Overrides the default configured model name")
    system_prompt: Optional[str] = Field(default=None, description="Optional system instructions/rules for the model")
    options: Optional[Dict[str, Any]] = Field(default=None, description="Additional model parameters (e.g., temperature, top_k)")
    stream: bool = Field(default=False, description="Whether to stream the response back in chunks")

class GenerateResponse(BaseModel):
    """Response schema for non-streaming text generation."""
    text: str = Field(..., description="The fully generated text response")
    model: str = Field(..., description="The exact model name that processed the request")
    done: bool = Field(default=True, description="Indicates if the response generation is complete")

class ChatResponse(BaseModel):
    """Response schema for non-streaming chat completion."""
    message: Message = Field(..., description="The assistant's generated chat message")
    model: str = Field(..., description="The exact model name that processed the request")
    done: bool = Field(default=True, description="Indicates if the chat completion is complete")

class PullModelRequest(BaseModel):
    """Request schema to pull a model from the Ollama library."""
    name: str = Field(..., description="The name of the model to download (e.g., 'llama3.2:3b')")
