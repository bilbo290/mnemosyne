# Mnemosyne

A persistent memory server for AI writing assistants, built on the [Model Context Protocol (MCP)](https://modelcontextprotocol.io). Mnemosyne gives LLMs long-term memory across conversations so they can write consistent, context-aware content for novels, blog series, documentation, and more.

## How It Works

Mnemosyne stores three types of information per project:

- **Content** — Sections of writing (chapters, posts, pages) stored with semantic embeddings for search and an output file for the full document.
- **Entities** — Reusable profiles for recurring things: characters, people, companies, places, concepts. Keeps descriptions consistent across content.
- **References** — Facts, rules, and guidelines (style guides, canon rules, timelines, terminology) that should stay consistent everywhere.

All data is stored locally using [ChromaDB](https://www.trychroma.com/) with sentence-transformer embeddings for semantic search.

## Tools

| Tool | Description |
|---|---|
| `create_project` | Create a new writing project |
| `list_projects` | List all projects |
| `get_project_summary` | Get section/entity/reference counts |
| `save_content` | Save or replace a content section |
| `get_content` | Retrieve a section by label |
| `search_memory` | Semantic search across content |
| `outline` | View all sections in order with word counts |
| `delete_content` | Remove a section |
| `prepare_context` | Fetch latest content, entities, and references in one call |
| `save_entity` | Store or update an entity profile |
| `get_entity` / `list_entities` | Look up entities |
| `save_reference` | Store a reference note |
| `get_reference` / `list_references` | Look up references |

## Setup

### Requirements

- Python 3.11+

### Install

```bash
git clone https://github.com/bilbo290/mnemosyne.git
cd mnemosyne
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run

```bash
python server.py
```

### Connect to a Client

Mnemosyne is a standard MCP server — any MCP-compatible client can use it. Add the following to your client's MCP config, replacing the path with your actual install location:

```json
{
  "mcpServers": {
    "mnemosyne": {
      "command": "python",
      "args": ["/ABSOLUTE/PATH/TO/mnemosyne/server.py"],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

#### Claude Desktop / Claude Code

- **Claude Desktop**: Add the config above to `claude_desktop_config.json`
- **Claude Code**: Add the config above to your project's `.mcp.json` or `~/.claude/mcp.json`

#### LM Studio

LM Studio has built-in MCP support (v0.3.17+). Open the **Program** tab in the sidebar, click **Install > Edit mcp.json**, and paste the config above. LM Studio will auto-load the server when you save. Make sure you're using a model that supports tool calling.

See the [LM Studio MCP docs](https://lmstudio.ai/docs/app/mcp) for more details.

#### Ollama

Ollama doesn't natively support MCP, but you can connect it using a bridge:

- **[mcp-client-for-ollama](https://github.com/jonigl/mcp-client-for-ollama)** — Interactive TUI that connects Ollama models to MCP servers. Install with `pip install mcp-client-for-ollama`, then point it at your config file.
- **[ollama-mcp-bridge](https://github.com/jonigl/ollama-mcp-bridge)** — Extends the Ollama API with MCP tool integration, so existing Ollama-based apps gain tool calling transparently.

Both approaches require an Ollama model with tool calling support (e.g., `llama3.2`, `qwen2.5`).

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `CHROMA_PATH` | `~/.mnemosyne/chroma` | Where ChromaDB stores data |

## License

MIT
