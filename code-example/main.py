#!/usr/bin/env python3
import os
import sys
from typing import Iterable

from openai import OpenAI
import mlflow
from mlflow.entities import AssessmentSource, AssessmentSourceType


MODEL_DEFAULT = os.getenv("OPENAI_MODEL", "gpt-oss-20b")
MODEL_URL = os.getenv("MODEL_URL", "http://a5b3148f0995c48088e0800feaa2c651-1539933567.us-east-2.elb.amazonaws.com/demo-llm/gpt-oss-20b/v1")
SYSTEM_PROMPT = "You are an assistant that receives questions from a user using a terminal. As such, you answers are displayed in the terminal, and are expected to be mostly short, concise and not use formats like .md"
os.environ["OPENAI_API_KEY"] = "doesn't-matter"


def read_prompt_from_args_or_stdin(argv: list[str]) -> str:
    # Usage:
    #   ask.py "your question"
    #   echo "your question" | ask.py
    if len(argv) > 1:
        return " ".join(argv[1:]).strip()

    if not sys.stdin.isatty():
        return sys.stdin.read().strip()

    print("Usage: ask.py \"your question\"  (or pipe text into stdin)", file=sys.stderr)
    raise SystemExit(2)


def create_prompt():
    prompt = mlflow.genai.register_prompt(
        name="terminal-prompt",
        template=SYSTEM_PROMPT,
        # Optional: Provide Response Format to get structured output
        # esponse_format=ResponseFormat,
        # Optional: Provide a commit message to describe the changes
        # commit_message="Initial commit",
        # Optional: Specify tags for this prompt
        # tags={
        #     "author": "author@example.com",
        #     "task": "summarization",
        #     "language": "en",
        # },
    )
    return prompt


@mlflow.trace(name="Stream Text Events", span_type="CHAT_MODEL", attributes={"model": "gpt-oss-20b"})
def stream_text_events(events: Iterable[object]) -> int:
    """
    The Responses streaming API emits SSE events. We print deltas for:
      - response.output_text.delta  (partial text chunks)
    See event types in the API reference. :contentReference[oaicite:2]{index=2}
    """
    exit_code = 0
    full_response_text = ""
    try:
        for event in events:
            # In the Python SDK, events expose fields as attributes.
            etype = getattr(event, "type", None)

            if etype == "response.output_text.delta":
                delta = getattr(event, "delta", "")
                if delta:
                    full_response_text += delta
                    print(delta, end="", flush=True)

            elif etype == "response.refusal.delta":
                # Optional: if a refusal happens, you'll see it streamed too.
                delta = getattr(event, "delta", "")
                if delta:
                    print(delta, end="", flush=True)
                    exit_code = 3

            elif etype == "response.failed":
                # Print something useful if available
                resp = getattr(event, "response", None)
                err = getattr(resp, "error", None) if resp else None
                msg = getattr(err, "message", None) if err else "Response failed."
                print(f"\n[error] {msg}", file=sys.stderr)
                return 1


    except KeyboardInterrupt:
        print("\n[interrupted]", file=sys.stderr)
        return 130

    print()  # newline after streaming finishes
    return full_response_text


@mlflow.trace(name="Calling the model", span_type="CHAT_MODEL", attributes={"model": "gpt-oss-20b"})
def call_the_model(client, prompt):
    # Streaming is enabled with stream=True. :contentReference[oaichttp://afc484d866d7843fa94860d25e3baeb8-2068025677.us-east-2.elb.amazonaws.com/demo-llm/gpt-oss-20b/v1ite:4]{index=4}
    events = client.responses.create(
        model=MODEL_DEFAULT,
        input=[
            {
                "role": "system",
                "content": mlflow.genai.load_prompt(name_or_uri="prompts:/terminal-prompt@latest").format()
            },
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt}
                ]
            }
        ],
        # input=prompt,
        stream=True,
    )

    return events


@mlflow.trace(name="Calling the model with chat completions", span_type="CHAT_MODEL", attributes={"model": "gpt-oss-20b"})
def call_the_model_completions(client, prompt):
    # Streaming is enabled with stream=True. :contentReference[oaichttp://afc484d866d7843fa94860d25e3baeb8-2068025677.us-east-2.elb.amazonaws.com/demo-llm/gpt-oss-20b/v1ite:4]{index=4}
    events = client.chat.completions.create(
        model=MODEL_DEFAULT,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {"role": "user", "content": prompt},
        ],
    )

    return events.choices[0].message.content


@mlflow.trace(name="Complete Process", span_type="CHAT_MODEL", attributes={"model": "gpt-oss-20b"})
def complete_model_process(prompt, client):
    events = call_the_model(client, prompt)

    mlflow.update_current_trace(request_preview=prompt)
    span = mlflow.get_current_active_span()
    trace_id = span.trace_id

    with open('last_feedback.txt', 'w') as f:
        f.write(trace_id)

    # mlflow.update_current_trace(response_preview="This will update the response in the UI")    

    full_text = stream_text_events(events)
    return full_text


def happy_feedback():
    with open('last_feedback.txt', 'r') as f:
        trace_id = f.read().strip()

    print(trace_id)

    mlflow.log_feedback(
        trace_id=trace_id,
        name="user_satisfaction",
        value=True,
        rationale="User indicated response was helpful",
        source=AssessmentSource(source_type=AssessmentSourceType.HUMAN, source_id="user_123"),
    )

def sad_feedback():
    with open('last_feedback.txt', 'r') as f:
        trace_id = f.read().strip()

    mlflow.log_feedback(
        trace_id=trace_id,
        name="user_satisfaction",
        value=False,
        rationale="User indicated response was unhelpful",
        source=AssessmentSource(source_type=AssessmentSourceType.HUMAN, source_id="user_123"),
    )


def main() -> int:
    prompt = read_prompt_from_args_or_stdin(sys.argv)

    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set.", file=sys.stderr)
        return 2

    # Setting up mlflow
    mlflow.set_tracking_uri("https://mlflow-route-mlflow.apps.ocp.wnk5d.sandbox1583.opentlc.com")
    mlflow.set_experiment("Demo Project - gpt-oss-20b")

    if prompt == "good":
        happy_feedback()
        print("positive feedback logged")
        return 0
    elif prompt == "bad":
        sad_feedback()
        print("negative feedback logged")
        return 0

    client = OpenAI(base_url=MODEL_URL)

    # system_prompt = create_prompt()
    complete_model_process(prompt, client)


if __name__ == "__main__":
    raise SystemExit(main())