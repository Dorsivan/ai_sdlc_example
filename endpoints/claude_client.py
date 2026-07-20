import anthropic
import requests
import json
import os
import argparse

# Custom endpoint configuration
BASE_URL = "https://maas.apps.ocp.2msw7.sandbox205.opentlc.com/demo-llm/gpt-oss-20b/v1"
BASE_URL_SDK = "https://maas.apps.ocp.2msw7.sandbox205.opentlc.com/demo-llm/gpt-oss-20b"
API_KEY = "sk-oai-Q3co4wTvCwUJYDOI_4yV4EfrAXpjRezyP20RLMYHvt2An2WcTHOWftLtz7jp"

def chat_with_claude(user_message, api_key=API_KEY, model="gpt-oss-20b", use_sdk=False):
    """
    Send a message to the LLM using the /v1/messages endpoint.

    Args:
        user_message: The message to send to the LLM
        api_key: Your API key (defaults to configured key)
        model: The model to use
        use_sdk: If True, use anthropic SDK; if False, use plain HTTP requests

    Returns:
        The response text from the LLM
    """
    if use_sdk:
        # Method 1: Using Anthropic SDK
        client = anthropic.Anthropic(
            api_key=api_key,
            base_url=BASE_URL_SDK,
            default_headers={
                "Authorization": f"Bearer {api_key}"
            }
        )

        message = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[
                {"role": "user", "content": user_message}
            ]
        )

        return message.content[0].text
    else:
        # Method 2: Using plain HTTP requests
        url = f"{BASE_URL}/messages"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        payload = {
            "model": model,
            "max_tokens": 1024,
            "messages": [
                {"role": "user", "content": user_message}
            ]
        }

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()

        result = response.json()
        return result["content"][0]["text"]


def chat_with_conversation(messages, api_key=API_KEY, model="gpt-oss-20b", use_sdk=False):
    """
    Send a multi-turn conversation to the LLM.

    Args:
        messages: List of message dicts with 'role' and 'content' keys
        api_key: Your API key
        model: The model to use
        use_sdk: If True, use anthropic SDK; if False, use plain HTTP requests

    Returns:
        The response text from the LLM
    """
    if use_sdk:
        # Method 1: Using Anthropic SDK
        client = anthropic.Anthropic(
            api_key=api_key,
            base_url=BASE_URL_SDK,
            default_headers={
                "Authorization": f"Bearer {api_key}"
            }
        )

        message = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=messages
        )

        return message.content[0].text
    else:
        # Method 2: Using plain HTTP requests
        url = f"{BASE_URL}/messages"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        payload = {
            "model": model,
            "max_tokens": 1024,
            "messages": messages
        }

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()

        result = response.json()
        return result["content"][0]["text"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Chat with LLM using /v1/messages endpoint')
    parser.add_argument('--method', type=str, choices=['sdk', 'http'], default='http',
                        help='Method to use: "sdk" for Anthropic SDK, "http" for plain HTTP requests (default: http)')
    parser.add_argument('--message', type=str, default='Hello! What is the capital of France?',
                        help='Message to send to the LLM')

    args = parser.parse_args()

    use_sdk = (args.method == 'sdk')
    method_name = "Anthropic SDK" if use_sdk else "HTTP Requests"

    print(f"=== Using {method_name} ===")

    try:
        response = chat_with_claude(args.message, use_sdk=use_sdk)
        print(f"Response: {response}")
    except Exception as e:
        print(f"Error: {e}")
