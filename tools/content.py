import re
import uuid
from datetime import datetime

from app import mcp
from core.db import get_collection


@mcp.tool()
def save_content(
    text: str,
    project_id: str,
    label: str | None = None,
    order: int | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Save a section of content to project memory.

    The text is embedded for semantic search AND written to the project's
    single output file so the full document lives in one place.

    To **replace** an existing section, pass the same label — the old
    version will be overwritten in both memory and the output file.

    Args:
        text: The content to store (a paragraph, section, chapter, post, etc.)
        project_id: The project to store it under
        label: Optional label to identify this section (e.g., "intro", "ch3",
               "pricing_section"). Reusing a label replaces the previous version.
        order: Optional integer for ordering sections in the output file.
               Lower numbers come first. Defaults to auto-increment.
        tags: Optional tags for categorization (e.g., ["draft", "pricing"])
    """
    collection = get_collection(project_id, "content")

    if order is None:
        order = collection.count() + 1

    now = datetime.now().isoformat()

    if label:
        doc_id = f"section_{label.lower().replace(' ', '_')}"
    else:
        doc_id = str(uuid.uuid4())

    doc_metadata: dict = {
        "created_at": now,
        "tags": ",".join(tags) if tags else "",
        "label": label or "",
        "order": order,
        "word_count": len(text.split()),
    }

    collection.upsert(
        ids=[doc_id],
        documents=[text],
        metadatas=[doc_metadata],
    )

    # Store paragraph-level chunks for better semantic search
    _store_chunks(collection, doc_id, text, label or doc_id, order, tags, now)

    # Rebuild the single output file
    _rebuild_output_file(project_id, collection)

    return {
        "id": doc_id,
        "project_id": project_id,
        "label": label,
        "order": order,
        "word_count": doc_metadata["word_count"],
        "status": "saved",
    }


@mcp.tool()
def get_content(project_id: str, label: str) -> dict:
    """Retrieve the full text of a section by its label.

    Use this after search_memory returns a chunk — to get the complete
    section that chunk belongs to.

    Args:
        project_id: The project to look in
        label: The section label (e.g., "intro", "ch3")
    """
    collection = get_collection(project_id, "content")
    doc_id = f"section_{label.lower().replace(' ', '_')}"

    results = collection.get(
        ids=[doc_id],
        include=["documents", "metadatas"],
    )

    if results and results["documents"] and results["documents"][0]:
        m = results["metadatas"][0]
        return {
            "label": m.get("label", label),
            "order": m.get("order", None),
            "word_count": m.get("word_count", 0),
            "tags": m.get("tags", ""),
            "text": results["documents"][0],
        }

    return {"error": f"Section '{label}' not found in project '{project_id}'"}


@mcp.tool()
def delete_content(project_id: str, label: str) -> dict:
    """Remove a section from the project by its label.

    Deletes the section and its paragraph chunks from memory,
    then rebuilds the output file.

    Args:
        project_id: The project the section belongs to
        label: The label of the section to delete
    """
    collection = get_collection(project_id, "content")
    doc_id = f"section_{label.lower().replace(' ', '_')}"

    all_data = collection.get(include=["metadatas"])
    ids_to_delete = []
    for i, m in enumerate(all_data["metadatas"]):
        aid = all_data["ids"][i]
        if aid == doc_id or m.get("parent_id") == doc_id:
            ids_to_delete.append(aid)

    if not ids_to_delete:
        return {"error": f"Section '{label}' not found"}

    collection.delete(ids=ids_to_delete)
    _rebuild_output_file(project_id, collection)

    return {"label": label, "deleted_items": len(ids_to_delete), "status": "deleted"}


@mcp.tool()
def search_memory(
    query: str,
    project_id: str,
    n_results: int = 5,
) -> list[dict]:
    """Semantically search project memory for relevant content.

    Searches paragraph-level chunks for precise matches. Returns the
    matching text along with which section it belongs to.

    Args:
        query: Natural language search query (e.g., "pricing comparison",
               "the battle scene", "onboarding flow explanation")
        project_id: The project to search within
        n_results: Number of results to return (default: 5)
    """
    collection = get_collection(project_id, "content")

    if collection.count() == 0:
        return []

    actual_n = min(n_results, collection.count())

    results = collection.query(
        query_texts=[query],
        n_results=actual_n,
        include=["documents", "metadatas", "distances"],
    )

    output = []
    if results and results["documents"]:
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            output.append({
                "text": doc,
                "label": meta.get("parent_id", meta.get("label", "")),
                "order": meta.get("order", None),
                "distance": results["distances"][0][i] if results["distances"] else None,
            })

    return output


@mcp.tool()
def outline(project_id: str) -> list[dict]:
    """Get the document outline — a table of contents of all sections in order.

    Returns each section's label, order, word count, and opening line.

    Args:
        project_id: The project to outline
    """
    collection = get_collection(project_id, "content")
    all_data = collection.get(include=["documents", "metadatas"])

    if not all_data or not all_data["documents"]:
        return []

    sections = []
    for i, doc in enumerate(all_data["documents"]):
        m = all_data["metadatas"][i]
        if m.get("parent_id"):
            continue  # skip chunks
        first_line = doc.strip().split("\n")[0][:100]
        sections.append({
            "label": m.get("label", ""),
            "order": m.get("order", 9999),
            "word_count": m.get("word_count", len(doc.split())),
            "tags": m.get("tags", ""),
            "opening": first_line,
        })

    sections.sort(key=lambda s: (s["order"], s["label"]))
    return sections


@mcp.tool()
def prepare_context(
    project_id: str,
    intent: str,
    entity_names: list[str] | None = None,
    reference_topics: list[str] | None = None,
    n_results: int = 3,
) -> dict:
    """Gather all relevant context before writing — in one call.

    This is the recommended tool to call before writing new content.
    It returns:
    - The most recent section (for continuity)
    - Semantically relevant past sections
    - Entity profiles (people, products, characters, etc.)
    - Reference notes (style guides, rules, key facts)

    Args:
        project_id: The project to pull context from
        intent: What you're about to write (e.g., "blog post about our new pricing",
                "next chapter where the hero enters the cave")
        entity_names: Entities that will appear (people, products, characters, etc.)
        reference_topics: Reference topics to look up (style guide, terminology, etc.)
        n_results: How many relevant past sections to retrieve (default: 3)
    """
    from core.db import get_collection as _get_col

    result: dict = {
        "intent": intent,
        "latest_section": None,
        "relevant_sections": [],
        "entities": [],
        "references": [],
    }

    content_col = _get_col(project_id, "content")

    if content_col.count() > 0:
        # Find the most recent section (highest order, not a chunk)
        all_data = content_col.get(include=["documents", "metadatas"])
        full_sections = []
        for i, doc in enumerate(all_data["documents"]):
            m = all_data["metadatas"][i]
            if not m.get("parent_id"):
                full_sections.append((m.get("order", 0), m.get("label", ""), doc))
        if full_sections:
            full_sections.sort(key=lambda s: s[0])
            last = full_sections[-1]
            result["latest_section"] = {
                "label": last[1],
                "order": last[0],
                "text": last[2],
            }

        # Semantic search for relevant content
        actual_n = min(n_results, content_col.count())
        search = content_col.query(
            query_texts=[intent],
            n_results=actual_n,
            include=["documents", "metadatas", "distances"],
        )
        if search and search["documents"]:
            seen = set()
            for i, doc in enumerate(search["documents"][0]):
                meta = search["metadatas"][0][i]
                lbl = meta.get("parent_id", meta.get("label", ""))
                if lbl in seen:
                    continue
                seen.add(lbl)
                result["relevant_sections"].append({
                    "text": doc,
                    "label": lbl,
                    "distance": search["distances"][0][i],
                })

    # Retrieve entities
    if entity_names:
        entity_col = _get_col(project_id, "entities")
        for name in entity_names:
            eid = f"entity_{name.lower().replace(' ', '_')}"
            hit = entity_col.get(ids=[eid], include=["documents", "metadatas"])
            if hit and hit["documents"] and hit["documents"][0]:
                result["entities"].append({
                    "name": hit["metadatas"][0].get("name", name),
                    "entity_type": hit["metadatas"][0].get("entity_type", ""),
                    "details": hit["documents"][0],
                })
            elif entity_col.count() > 0:
                fuzzy = entity_col.query(
                    query_texts=[name], n_results=1,
                    include=["documents", "metadatas", "distances"],
                )
                if fuzzy and fuzzy["documents"] and fuzzy["documents"][0]:
                    result["entities"].append({
                        "name": fuzzy["metadatas"][0][0].get("name", "Unknown"),
                        "entity_type": fuzzy["metadatas"][0][0].get("entity_type", ""),
                        "details": fuzzy["documents"][0][0],
                        "match_type": "semantic",
                    })

    # Retrieve references
    if reference_topics:
        ref_col = _get_col(project_id, "references")
        for topic in reference_topics:
            rid = f"ref_{topic.lower().replace(' ', '_')}"
            hit = ref_col.get(ids=[rid], include=["documents", "metadatas"])
            if hit and hit["documents"] and hit["documents"][0]:
                result["references"].append({
                    "topic": hit["metadatas"][0].get("topic", topic),
                    "content": hit["documents"][0],
                })
            elif ref_col.count() > 0:
                fuzzy = ref_col.query(
                    query_texts=[topic], n_results=1,
                    include=["documents", "metadatas", "distances"],
                )
                if fuzzy and fuzzy["documents"] and fuzzy["documents"][0]:
                    result["references"].append({
                        "topic": fuzzy["metadatas"][0][0].get("topic", "Unknown"),
                        "content": fuzzy["documents"][0][0],
                        "match_type": "semantic",
                    })

    return result


# ── Internal helpers ──


def _store_chunks(collection, parent_id: str, text: str, label: str, order: int, tags: list[str] | None, timestamp: str):
    """Split content into paragraph chunks for better semantic search."""
    # Remove old chunks
    all_data = collection.get(include=["metadatas"])
    old_chunk_ids = [
        all_data["ids"][i]
        for i, m in enumerate(all_data["metadatas"])
        if m.get("parent_id") == parent_id
    ]
    if old_chunk_ids:
        collection.delete(ids=old_chunk_ids)

    # Split into paragraphs
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    if len(paragraphs) <= 2:
        return

    # Group short paragraphs (min ~50 words per chunk)
    chunks = []
    current = []
    wc = 0
    for para in paragraphs:
        current.append(para)
        wc += len(para.split())
        if wc >= 50:
            chunks.append("\n\n".join(current))
            current = []
            wc = 0
    if current:
        chunks.append("\n\n".join(current))

    tag_str = ",".join(tags) if tags else ""
    for i, chunk in enumerate(chunks):
        chunk_id = f"{parent_id}_chunk_{i}"
        collection.upsert(
            ids=[chunk_id],
            documents=[chunk],
            metadatas=[{
                "parent_id": parent_id,
                "chunk_index": i,
                "label": label,
                "order": order,
                "tags": tag_str,
                "created_at": timestamp,
            }],
        )


def _rebuild_output_file(project_id: str, collection):
    """Rebuild the single output .txt file from all sections in order."""
    from pathlib import Path
    from core.db import get_project_metadata

    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)

    meta = get_project_metadata(project_id)
    project_name = meta.get("project_name", project_id) if meta else project_id

    all_data = collection.get(include=["documents", "metadatas"])
    if not all_data or not all_data["documents"]:
        return

    sections = []
    total_words = 0
    for i, doc in enumerate(all_data["documents"]):
        m = all_data["metadatas"][i]
        if m.get("parent_id"):
            continue
        order = m.get("order", 9999)
        wc = m.get("word_count", len(doc.split()))
        total_words += wc
        sections.append((order, doc, wc))

    sections.sort(key=lambda s: s[0])

    safe_name = re.sub(r"[^\w\s-]", "", project_name).strip().lower().replace(" ", "_")
    filepath = output_dir / f"{safe_name}.txt"

    # Keep a backup before overwriting
    if filepath.exists():
        backup = output_dir / f".{safe_name}.txt.bak"
        backup.write_text(filepath.read_text())

    with open(filepath, "w") as f:
        f.write(f"{project_name}\n")
        f.write(f"{len(sections)} sections | {total_words:,} words\n")
        f.write("=" * 60 + "\n")

        for i, (order, text, wc) in enumerate(sections):
            f.write("\n")
            f.write(text.rstrip() + "\n")
            if i < len(sections) - 1:
                f.write("\n---\n")
