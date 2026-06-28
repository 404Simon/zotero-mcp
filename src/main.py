from fastmcp import FastMCP

from zotero import (
    build_collection_tree,
    format_collection_tree,
    get_paper_metadata,
    read_paper_text,
)

mcp = FastMCP("Zotero Library")


@mcp.tool
def list_library(query: str | None = None) -> str:
    """List collections and papers in the Zotero library.
    Optionally filter by collection name, paper title, or author.
    """
    tree = build_collection_tree(query)
    return format_collection_tree(tree)


@mcp.tool
def paper_details(item_key: str) -> str:
    """Get full metadata for a paper by its item key.
    The item_key is shown in the list_library output (last part of the path).
    """
    meta = get_paper_metadata(item_key)
    if meta is None:
        return f"Paper with key '{item_key}' not found."

    lines = [
        f"Title: {meta['fields'].get('title', '(no title)')}",
        f"Type: {meta['item_type']}",
        f"Key: {meta['key']}",
        f"Added: {meta['dateAdded']}",
        f"Modified: {meta['dateModified']}",
    ]

    creators = meta["creators"]
    if creators:
        author_str = ", ".join(f"{c['firstName']} {c['lastName']}" for c in creators)
        lines.append(f"Authors: {author_str}")

    for name in (
        "date",
        "publicationTitle",
        "publisher",
        "DOI",
        "url",
        "ISBN",
        "ISSN",
        "abstractNote",
    ):
        if value := meta["fields"].get(name):
            lines.append(f"{name}: {value}")

    if meta["collections"]:
        lines.append(f"Collections: {', '.join(meta['collections'])}")

    pdfs = [a for a in meta["attachments"] if a["contentType"] == "application/pdf"]
    if pdfs:
        lines.append(f"PDF: {pdfs[0]['filename']}")

    return "\n".join(lines)


@mcp.tool
def paper_text(item_key: str) -> str:
    """Extract full text from a paper's PDF using pdftotext.
    The item_key is shown in the list_library output.
    """
    meta = get_paper_metadata(item_key)
    if meta is None:
        return f"Paper with key '{item_key}' not found."

    pdfs = [a for a in meta["attachments"] if a["contentType"] == "application/pdf"]
    if not pdfs:
        return "No PDF attachment found for this paper."

    text = read_paper_text(item_key)
    if text is None:
        return "PDF file not found on disk."
    return text.strip()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
