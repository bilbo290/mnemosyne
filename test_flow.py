"""Full end-to-end test: Qwen + Mnemosyne (optimized 6-tool version)."""

import json
import re
import sys
import requests

API_BASE = "http://192.168.1.50:1234/v1"
MODEL = "qwen/qwen3.5-9b"

sys.path.insert(0, ".")


# ── Tool dispatch ──

def execute_tool(name: str, args: dict) -> str:
    try:
        if name == "project":
            from tools.projects import project
            return json.dumps(project(**args), default=str)
        elif name == "entity":
            from tools.entities import entity
            return json.dumps(entity(**args), default=str)
        elif name == "reference":
            from tools.references import reference
            return json.dumps(reference(**args), default=str)
        elif name == "element":
            from tools.elements import element
            return json.dumps(element(**args), default=str)
        elif name == "content":
            from tools.content import content
            return json.dumps(content(**args), default=str)
        elif name == "canvas":
            from tools.canvas import canvas
            return json.dumps(canvas(**args), default=str)
        else:
            return json.dumps({"error": f"Unknown tool: {name}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ── Tool schemas (compact) ──

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "project",
            "description": "Manage projects. Actions: create (name, content_type), list, summary (project_id)",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["create", "list", "summary"]},
                    "name": {"type": "string"},
                    "content_type": {"type": "string"},
                    "project_id": {"type": "string"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "entity",
            "description": "Manage entities (characters, locations). Actions: save (name, entity_type, details), get (name), list",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["save", "get", "list"]},
                    "project_id": {"type": "string"},
                    "name": {"type": "string"},
                    "entity_type": {"type": "string"},
                    "details": {"type": "string"}
                },
                "required": ["action", "project_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "element",
            "description": "Manage chapter elements/beats. Actions: add (chapter, description, element_type, status), list (chapter), update (element_id, status), remove (element_id), suggest (chapter, intent, entity_names)",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["add", "list", "update", "remove", "suggest"]},
                    "project_id": {"type": "string"},
                    "chapter": {"type": "string"},
                    "description": {"type": "string"},
                    "element_type": {"type": "string"},
                    "status": {"type": "string", "enum": ["proposed", "accepted", "rejected"]},
                    "element_id": {"type": "string"},
                    "intent": {"type": "string"},
                    "entity_names": {"type": "array", "items": {"type": "string"}},
                    "notes": {"type": "string"}
                },
                "required": ["action", "project_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "content",
            "description": "Manage written content. Actions: save (text, label, order), get (label), search (query), outline, delete (label)",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["save", "get", "search", "outline", "delete"]},
                    "project_id": {"type": "string"},
                    "text": {"type": "string"},
                    "label": {"type": "string"},
                    "order": {"type": "integer"},
                    "query": {"type": "string"},
                    "n_results": {"type": "integer"}
                },
                "required": ["action", "project_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "canvas",
            "description": "Write to file instead of chat. Actions: setup (file_path), write (text, label, mode, save_to_memory), read (tail_lines), clear",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["setup", "write", "read", "clear"]},
                    "project_id": {"type": "string"},
                    "file_path": {"type": "string"},
                    "text": {"type": "string"},
                    "label": {"type": "string"},
                    "mode": {"type": "string", "enum": ["append", "overwrite"]},
                    "save_to_memory": {"type": "boolean"},
                    "tail_lines": {"type": "integer"}
                },
                "required": ["action", "project_id"]
            }
        }
    },
]

SYSTEM_PROMPT = """\
Writing assistant with persistent memory. NEVER write scenes unprompted.

WORKFLOW:
1. PLAN — call element(action=suggest) first. Suggest elements, ask user.
2. BRAINSTORM — use element(action=add) to record beats. Discuss with user.
3. WRITE — only when user says go. Use canvas(action=write) if configured, else content(action=save).

RULES:
- Never write without planning elements first.
- Never start writing until user explicitly says to.
- Keep responses concise.
"""


def strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()


def call_llm(messages: list, max_tokens: int = 1500) -> dict:
    resp = requests.post(
        f"{API_BASE}/chat/completions",
        json={"model": MODEL, "messages": messages, "tools": TOOLS,
              "tool_choice": "auto", "max_tokens": max_tokens},
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()


def chat_turn(messages: list, user_msg: str, max_tokens: int = 1500) -> list:
    messages.append({"role": "user", "content": user_msg})
    print(f"\n{'='*60}")
    print(f"USER: {user_msg}")
    print(f"{'='*60}")

    while True:
        result = call_llm(messages, max_tokens)
        choice = result["choices"][0]
        msg = choice["message"]
        usage = result.get("usage", {})

        assistant_entry = {"role": "assistant", "content": msg.get("content", "")}
        if msg.get("tool_calls"):
            assistant_entry["tool_calls"] = msg["tool_calls"]
        messages.append(assistant_entry)

        if msg.get("tool_calls") and len(msg["tool_calls"]) > 0:
            for tc in msg["tool_calls"]:
                fn_name = tc["function"]["name"]
                fn_args = json.loads(tc["function"]["arguments"])
                print(f"\n  >> {fn_name}({json.dumps(fn_args)})")
                tool_result = execute_tool(fn_name, fn_args)
                print(f"  << {tool_result[:200]}")
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": tool_result})
            continue

        text = strip_think(msg.get("content", ""))
        if text:
            print(f"\nASSISTANT: {text}")
        print(f"  [tokens: {usage.get('prompt_tokens', '?')}p + {usage.get('completion_tokens', '?')}c = {usage.get('total_tokens', '?')}t]")
        break

    return messages


def main():
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # 1. Create project
    messages = chat_turn(messages,
        "Create a sci-fi novel project called 'The Last Horizon'.")

    # 2. Save character
    messages = chat_turn(messages,
        "Save a character: Kira Vasquez. 32yo astro-engineer, pragmatic, dry humor, "
        "cybernetic left arm, survivor's guilt from losing her crew in hyperspace.")

    # 3. Plan chapter 1
    messages = chat_turn(messages,
        "Plan chapter 1: Kira wakes up alone in her crashed ship on an alien world. "
        "Two suns (red and white), breathable air, damaged ship AI speaking in fragments.")

    # 4. Accept + add more
    messages = chat_turn(messages,
        "Accept all elements. Add one more: she finds a strange symbol carved into "
        "the hull that wasn't there before the crash.")

    # 5. Write
    messages = chat_turn(messages,
        "Write chapter 1 now. Third person, past tense, literary sci-fi. ~500 words. "
        "Save with content(action=save).", max_tokens=2000)

    print(f"\n{'='*60}")
    print("FLOW COMPLETE")
    print(f"{'='*60}")

    # Print context stats
    total_chars = sum(len(json.dumps(m)) for m in messages)
    print(f"\nConversation: {len(messages)} messages, ~{total_chars} chars")


if __name__ == "__main__":
    main()
