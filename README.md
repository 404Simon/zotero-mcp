# Zotero MCP

Read-only MCP server for your local Zotero library. Browse collections, inspect paper metadata, and extract full-text from PDFs -- all via FastMCP tools.

## Requirements

- Zotero desktop synced to `~/Zotero/zotero.sqlite`
- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- `pdftotext` (for `paper_text`) -- usually from `poppler-utils`

## Setup

```bash
uv sync
```

## Tools

### `list_library`

List all collections and papers as a formatted tree.

```text
uv run python src/main.py
```

| Argument | Type | Description |
|----------|------|-------------|
| `query` | `string` (optional) | Filter by collection name, paper title, or author (case-insensitive) |

**Examples:**

```python
# Full library
await client.call_tool("list_library", {})
# └── Bachelorarbeit (42 papers)
#     │ [book] Pro Spring Boot 3 (2024) - Felipe Gutierrez
#     ├── GraalVM (4 papers)

# Filtered
await client.call_tool("list_library", {"query": "serverless"})
# └── Serverless (8 papers)
#     [journalArticle] The rise of serverless computing (2019) - Unknown
```

### `paper_details`

Get full metadata for a paper by its item key.

| Argument | Type | Description |
|----------|------|-------------|
| `item_key` | `string` (required) | Zotero item key (shown in list_library output) |

**Example:**

```python
await client.call_tool("paper_details", {"item_key": "T3ZCDWC7"})
# Title: MMLU-Pro: A More Robust and Challenging Multi-Task Language Understanding Benchmark
# Type: preprint
# Authors: Yubo Wang, Xueguang Ma, ...
# date: 2024-11-06
# DOI: 10.48550/arXiv.2406.01574
# url: http://arxiv.org/abs/2406.01574
# abstractNote: In the age of large-scale language models...
# Collections: Studienarbeit
# PDF: Wang et al. - 2024 - MMLU-Pro A More Robust ....pdf
```

Returns: title, type, key, dates, authors, all field metadata, collection memberships, and PDF attachment info.

### `paper_text`

Extract the full text of a paper's PDF using `pdftotext`.

| Argument | Type | Description |
|----------|------|-------------|
| `item_key` | `string` (required) | Zotero item key |

**Example:**

```python
await client.call_tool("paper_text", {"item_key": "T3ZCDWC7"})
# MMLU-Pro: A More Robust and Challenging
# Multi-Task Language Understanding Benchmark
#
# Yubo Wang*, Xueguang Ma*, Ge Zhang, ...
# ...
```

## Usage

```bash
# stdio transport (default for MCP clients)
uv run python src/main.py

# fastmcp CLI
uv run fastmcp run src/main.py:mcp
```

## File structure

```text
src/
  main.py    # FastMCP server, tool definitions
  zotero.py  # SQLite queries, data models, formatting
```

The database is read directly from `~/Zotero/zotero.sqlite`. PDFs are resolved from `~/Zotero/storage/`. No API key needed.
