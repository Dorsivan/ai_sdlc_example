#!/usr/bin/env python3
import sys
from typing import Iterable

from openai import OpenAI
import mlflow
from mlflow.entities import AssessmentSource, AssessmentSourceType

from config import setup_mlflow, MODEL_NAME, MODEL_URL, PROMPT_NAME


SYSTEM_INSTRUCTIONS = "You answers are displayed in the terminal, and are expected to be mostly short, concise and not use formats like .md"

mlflow.openai.autolog()


def read_prompt_from_args_or_stdin(argv: list[str]) -> str:
    if len(argv) > 1:
        return " ".join(argv[1:]).strip()

    if not sys.stdin.isatty():
        return sys.stdin.read().strip()

    print("Usage: main.py \"your question\"  (or pipe text into stdin)", file=sys.stderr)
    raise SystemExit(2)


@mlflow.trace(name="Load Prompt Template")
def load_system_prompt() -> str:
    prompt = mlflow.genai.load_prompt(
        name_or_uri=f"prompts:/{PROMPT_NAME}@production",
        cache_ttl_seconds=60,
    )
    rendered = prompt.format(role="terminal", instructions=SYSTEM_INSTRUCTIONS)
    return rendered


@mlflow.trace(name="Validate Input")
def validate_input(raw_input: str) -> str:
    cleaned = raw_input.strip()
    if not cleaned:
        raise ValueError("Empty input")
    if len(cleaned) > 2000:
        cleaned = cleaned[:2000]
    return cleaned


@mlflow.trace(name="Format Messages")
def format_messages(system_prompt: str, user_input: str) -> list[dict]:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input},
    ]
    return messages


@mlflow.trace(name="Call Model - Initial Response", span_type="CHAT_MODEL")
def call_model_initial(client, messages) -> str:
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
    )
    return response.choices[0].message.content


@mlflow.trace(name="Call Model - Refine Response", span_type="CHAT_MODEL")
def call_model_refine(client, original_question: str, initial_response: str) -> str:
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant. The user asked a question and received an initial response. "
                           "Review the response and provide a final, polished version that is concise and terminal-friendly. "
                           "If the initial response is already good, return it as-is.",
            },
            {
                "role": "user",
                "content": f"Question: {original_question}\n\nInitial response: {initial_response}\n\nProvide the final response:",
            },
        ],
    )
    return response.choices[0].message.content


@mlflow.trace(name="Post-process Output")
def postprocess_output(response_text: str) -> str:
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned
    return cleaned


@mlflow.trace(name="Display Response")
def display_response(final_text: str):
    print(final_text)
    return final_text


@mlflow.trace(name="Complete Process", span_type="CHAIN")
def complete_model_process(prompt: str, client: OpenAI) -> str:
    mlflow.update_current_trace(
        tags={
            "user_id": "cli_user",
            "request_type": "question",
        },
    )

    span = mlflow.get_current_active_span()
    trace_id = span.trace_id

    with open("last_feedback.txt", "w") as f:
        f.write(trace_id)

    system_prompt = load_system_prompt()
    validated_input = validate_input(prompt)
    messages = format_messages(system_prompt, validated_input)

    initial_response = call_model_initial(client, messages)
    refined_response = call_model_refine(client, validated_input, initial_response)

    final_output = postprocess_output(refined_response)
    display_response(final_output)

    return final_output


def happy_feedback():
    with open("last_feedback.txt", "r") as f:
        trace_id = f.read().strip()

    mlflow.log_feedback(
        trace_id=trace_id,
        name="user_satisfaction",
        value=True,
        rationale="User indicated response was helpful",
        source=AssessmentSource(source_type=AssessmentSourceType.HUMAN, source_id="user_123"),
    )


def sad_feedback():
    with open("last_feedback.txt", "r") as f:
        trace_id = f.read().strip()

    mlflow.log_feedback(
        trace_id=trace_id,
        name="user_satisfaction",
        value=False,
        rationale="User indicated response was unhelpful",
        source=AssessmentSource(source_type=AssessmentSourceType.HUMAN, source_id="user_123"),
    )


def rated_feedback(rating: int):
    with open("last_feedback.txt", "r") as f:
        trace_id = f.read().strip()

    mlflow.log_feedback(
        trace_id=trace_id,
        name="user_rating",
        value=rating,
        rationale=f"User rated response {rating}/5",
        source=AssessmentSource(source_type=AssessmentSourceType.HUMAN, source_id="user_123"),
    )


def log_expected_response(expected: str):
    with open("last_feedback.txt", "r") as f:
        trace_id = f.read().strip()

    mlflow.log_expectation(
        trace_id=trace_id,
        name="expected_response",
        value=expected,
        source=AssessmentSource(source_type=AssessmentSourceType.HUMAN, source_id="user_123"),
    )
    print(f"Logged expected response for trace {trace_id}")


def main() -> int:
    prompt = read_prompt_from_args_or_stdin(sys.argv)

    setup_mlflow()
    mlflow.genai.enable_git_model_versioning()

    if prompt == "good":
        happy_feedback()
        print("positive feedback logged")
        return 0
    elif prompt == "bad":
        sad_feedback()
        print("negative feedback logged")
        return 0
    elif prompt.startswith("rate "):
        try:
            rating = int(prompt.split(" ", 1)[1])
            rated_feedback(rating)
            print(f"rating {rating}/5 logged")
        except ValueError:
            print("Usage: main.py rate <1-5>", file=sys.stderr)
            return 1
        return 0
    elif prompt.startswith("expect "):
        expected = prompt.split(" ", 1)[1]
        log_expected_response(expected)
        return 0

    client = OpenAI(base_url=MODEL_URL)
    complete_model_process(prompt, client)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
