"""
Anthropic to OpenAI Protocol Translator Proxy

This service receives requests in Anthropic /v1/messages format,
translates them to OpenAI /v1/chat/completions format,
forwards to an OpenAI-compatible endpoint,
and translates the response back to Anthropic format.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import requests
import time
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Anthropic to OpenAI Proxy")

# Configuration
OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"
OPENAI_API_KEY = "your-openai-api-key-here"


class AnthropicMessage(BaseModel):
    role: str
    content: str


class AnthropicRequest(BaseModel):
    model: str
    messages: List[AnthropicMessage]
    max_tokens: int = 1024
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = None
    stream: Optional[bool] = False


def translate_anthropic_to_openai(anthropic_request: dict) -> dict:
    """
    Translate Anthropic /v1/messages request to OpenAI /v1/chat/completions format.
    """
    openai_request = {
        "model": anthropic_request.get("model", "gpt-3.5-turbo"),
        "messages": [],
        "max_tokens": anthropic_request.get("max_tokens", 1024),
    }

    # Add optional parameters
    if "temperature" in anthropic_request:
        openai_request["temperature"] = anthropic_request["temperature"]
    if "top_p" in anthropic_request:
        openai_request["top_p"] = anthropic_request["top_p"]
    if "stream" in anthropic_request:
        openai_request["stream"] = anthropic_request["stream"]

    # Translate messages
    for msg in anthropic_request.get("messages", []):
        openai_msg = {
            "role": msg["role"],
            "content": msg["content"]
        }
        openai_request["messages"].append(openai_msg)

    return openai_request


def translate_openai_to_anthropic(openai_response: dict, request_model: str) -> dict:
    """
    Translate OpenAI /v1/chat/completions response to Anthropic /v1/messages format.
    """
    choice = openai_response["choices"][0]
    message = choice["message"]

    anthropic_response = {
        "id": openai_response.get("id", "msg_" + str(int(time.time()))),
        "type": "message",
        "role": "assistant",
        "content": [
            {
                "type": "text",
                "text": message["content"]
            }
        ],
        "model": request_model,
        "stop_reason": "end_turn" if choice.get("finish_reason") == "stop" else choice.get("finish_reason"),
        "usage": {
            "input_tokens": openai_response["usage"].get("prompt_tokens", 0),
            "output_tokens": openai_response["usage"].get("completion_tokens", 0)
        }
    }

    return anthropic_response


@app.post("/v1/messages")
async def messages_endpoint(request: Request):
    """
    Main endpoint that receives Anthropic-format requests,
    translates to OpenAI format, forwards, and translates back.
    """
    try:
        # Parse incoming Anthropic request
        anthropic_request = await request.json()

        # Validate required fields
        if "messages" not in anthropic_request:
            raise HTTPException(status_code=400, detail="Missing 'messages' field")

        # Translate to OpenAI format
        openai_request = translate_anthropic_to_openai(anthropic_request)

        # Forward to OpenAI endpoint
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }

        response = requests.post(
            OPENAI_ENDPOINT,
            headers=headers,
            json=openai_request,
            timeout=60
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"OpenAI API error: {response.text}"
            )

        # Parse OpenAI response
        openai_response = response.json()

        # Translate back to Anthropic format
        anthropic_response = translate_openai_to_anthropic(
            openai_response,
            anthropic_request.get("model", "gpt-3.5-turbo")
        )

        return JSONResponse(content=anthropic_response)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint for nginx/monitoring."""
    return {"status": "healthy", "service": "anthropic-to-openai-proxy"}


@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "Anthropic to OpenAI Protocol Translator",
        "endpoints": {
            "/v1/messages": "Anthropic-compatible messages endpoint (translates to OpenAI)",
            "/health": "Health check endpoint"
        }
    }


if __name__ == "__main__":
    # Run with: python anthropic_to_openai_proxy.py
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
