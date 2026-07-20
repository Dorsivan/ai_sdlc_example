# Claude Client - LLM Communication via /v1/messages Endpoint

A Python client for communicating with LLM endpoints using the `/v1/messages` API format (similar to Anthropic's Claude API).

## Features

- Two methods for API communication:
  - **HTTP Requests**: Plain HTTP requests using the `requests` library
  - **Anthropic SDK**: Using the official `anthropic` Python SDK
- Command-line interface for easy testing
- Support for single messages and multi-turn conversations
- Configurable endpoint and API key

## Requirements

```bash
pip install anthropic requests
```

## Configuration

The script is pre-configured with the following settings:

- **Endpoint**: `https://maas.apps.ocp.2msw7.sandbox205.opentlc.com/demo-llm/gpt-oss-20b/v1`
- **API Key**: `sk-oai-Q3co4wTvCwUJYDOI_4yV4EfrAXpjRezyP20RLMYHvt2An2WcTHOWftLtz7jp`
- **Model**: `gpt-oss-20b`

To use a different endpoint or API key, modify the constants at the top of `claude_client.py`:

```python
BASE_URL = "https://your-endpoint.com/v1"
BASE_URL_SDK = "https://your-endpoint.com"  # Without /v1 for SDK
API_KEY = "your-api-key"
```

## Usage

### Command Line

**Using HTTP requests (default):**
```bash
python claude_client.py --method http --message "What is 2+2?"
```

**Using Anthropic SDK:**
```bash
python claude_client.py --method sdk --message "What is 2+2?"
```

**Using default method (HTTP) with default message:**
```bash
python claude_client.py
```

**Just changing the method:**
```bash
python claude_client.py --method sdk
```

### Command-Line Arguments

- `--method`: Choose the communication method
  - `http` - Plain HTTP requests (default)
  - `sdk` - Anthropic SDK
- `--message`: The message to send to the LLM (default: "Hello! What is the capital of France?")

### Programmatic Usage

```python
from claude_client import chat_with_claude, chat_with_conversation

# Single message with HTTP method
response = chat_with_claude("What is the capital of France?", use_sdk=False)
print(response)

# Single message with SDK method
response = chat_with_claude("What is 2+2?", use_sdk=True)
print(response)

# Multi-turn conversation
conversation = [
    {"role": "user", "content": "Hello! My name is Alice."},
    {"role": "assistant", "content": "Hello Alice! How can I help you today?"},
    {"role": "user", "content": "What's my name?"}
]
response = chat_with_conversation(conversation, use_sdk=False)
print(response)
```

## API Methods

### `chat_with_claude(user_message, api_key=API_KEY, model="gpt-oss-20b", use_sdk=False)`

Send a single message to the LLM.

**Parameters:**
- `user_message` (str): The message to send to the LLM
- `api_key` (str): Your API key (defaults to configured key)
- `model` (str): The model to use (default: "gpt-oss-20b")
- `use_sdk` (bool): If True, use Anthropic SDK; if False, use plain HTTP requests

**Returns:**
- str: The response text from the LLM

### `chat_with_conversation(messages, api_key=API_KEY, model="gpt-oss-20b", use_sdk=False)`

Send a multi-turn conversation to the LLM.

**Parameters:**
- `messages` (list): List of message dicts with 'role' and 'content' keys
- `api_key` (str): Your API key
- `model` (str): The model to use
- `use_sdk` (bool): If True, use Anthropic SDK; if False, use plain HTTP requests

**Returns:**
- str: The response text from the LLM

## Examples

```bash
# Ask a math question using HTTP
python claude_client.py --method http --message "What is 5+3?"

# Ask about history using SDK
python claude_client.py --method sdk --message "Who wrote Romeo and Juliet?"

# Use default settings
python claude_client.py
```

## Technical Details

### HTTP Method
- Uses `Authorization: Bearer` header for authentication
- Makes POST requests to `/v1/messages` endpoint
- SSL verification disabled for compatibility

### SDK Method
- Uses official Anthropic Python SDK
- Custom headers for Bearer token authentication
- Base URL configured without `/v1` suffix (SDK adds it automatically)

---

## Anthropic to OpenAI Protocol Translator Proxy

A FastAPI-based proxy service that translates between Anthropic's `/v1/messages` API format and OpenAI's `/v1/chat/completions` API format. This allows you to use Anthropic-compatible clients with OpenAI-compatible backends.

### Features

- Receives requests in Anthropic `/v1/messages` format
- Translates to OpenAI `/v1/chat/completions` format
- Forwards to any OpenAI-compatible endpoint
- Translates responses back to Anthropic format
- Health check endpoint for monitoring
- Ready for deployment behind nginx

### Setup

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Configure the proxy:**

Edit `anthropic_to_openai_proxy.py` and set your OpenAI endpoint and API key:

```python
OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"
OPENAI_API_KEY = "your-openai-api-key-here"
```

3. **Run the proxy:**

```bash
# Development
python anthropic_to_openai_proxy.py

# Production with uvicorn
uvicorn anthropic_to_openai_proxy:app --host 0.0.0.0 --port 8000
```

The service will start on `http://0.0.0.0:8000`

### Nginx Configuration

1. **Copy the nginx configuration:**
```bash
sudo cp nginx.conf /etc/nginx/sites-available/anthropic-proxy
sudo ln -s /etc/nginx/sites-available/anthropic-proxy /etc/nginx/sites-enabled/
```

2. **Edit the configuration:**
   - Replace `your-domain.com` with your actual domain
   - Configure SSL certificates if using HTTPS

3. **Test and reload nginx:**
```bash
sudo nginx -t
sudo systemctl reload nginx
```

### Systemd Service (Optional)

To run the proxy as a system service:

1. **Create the service file:**
```bash
sudo cp systemd-service.txt /etc/systemd/system/anthropic-proxy.service
```

2. **Edit the service file:**
   - Update `WorkingDirectory` and `ExecStart` paths
   - Adjust `User` and `Group` as needed

3. **Enable and start the service:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable anthropic-proxy
sudo systemctl start anthropic-proxy
sudo systemctl status anthropic-proxy
```

### Testing the Proxy

Once running, test with the Claude client:

```python
# Update the BASE_URL in claude_client.py to point to your proxy
BASE_URL = "http://your-domain.com/v1"

# Run the client
python claude_client.py --method http --message "Hello from the proxy!"
```

Or test with curl:

```bash
curl -X POST http://localhost:8000/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-key" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "gpt-3.5-turbo",
    "max_tokens": 1024,
    "messages": [
      {"role": "user", "content": "Hello!"}
    ]
  }'
```

### API Translation Details

**Anthropic Request → OpenAI Request:**
- `messages` → `messages` (same format)
- `max_tokens` → `max_tokens`
- `temperature` → `temperature`
- `top_p` → `top_p`
- `model` → `model`

**OpenAI Response → Anthropic Response:**
- `choices[0].message.content` → `content[0].text`
- `usage.prompt_tokens` → `usage.input_tokens`
- `usage.completion_tokens` → `usage.output_tokens`
- `finish_reason: "stop"` → `stop_reason: "end_turn"`

### Endpoints

- `POST /v1/messages` - Main translation endpoint (Anthropic format)
- `GET /health` - Health check endpoint
- `GET /` - Service information

### Architecture

```
[Anthropic Client] 
    ↓ (Anthropic /v1/messages format)
[Nginx Reverse Proxy]
    ↓
[FastAPI Proxy Service]
    ↓ (translates to OpenAI format)
[OpenAI API or compatible endpoint]
    ↓ (OpenAI /v1/chat/completions response)
[FastAPI Proxy Service]
    ↓ (translates back to Anthropic format)
[Anthropic Client]
```

### Monitoring

Check service status:
```bash
# If using systemd
sudo systemctl status anthropic-proxy

# Check logs
sudo journalctl -u anthropic-proxy -f

# Health check
curl http://localhost:8000/health
```

### Security Considerations

1. **API Key Management**: Store API keys securely (environment variables, secrets manager)
2. **HTTPS**: Always use HTTPS in production (uncomment HTTPS section in nginx.conf)
3. **Rate Limiting**: Consider adding rate limiting in nginx or the application
4. **Authentication**: Add authentication middleware if exposing publicly
5. **Input Validation**: The proxy validates incoming requests automatically

### Customization

You can extend the proxy to:
- Add request/response logging
- Implement caching
- Add custom headers
- Support streaming responses
- Add retry logic
- Implement request queuing

## License

MIT
