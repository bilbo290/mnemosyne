import re
import uuid
from datetime import datetime

from app import mcp
from core.db import get_collection


@mcp.tool()
def content(
    action: str,
    project_id: str,
    text: str = "",
    label: str = "",
    order: int | None = None,
    tags: list[str] | None = None,
    query: str = "",
    n_results: int = 5,
) -> dict:
    """Manage written content sections.

    Actions:
      save — store a section (needs: text; optional: label, order, tags)
      get — retrieve by label (needs: label)
      search — semantic search (needs: query; optional: n_results)
      outline — list all sections in order
      delete — remove a section (needs: label)

    Args:
        action: save, get, search, outline, or delete
        project_id: Project ID
        text: Content text (for save)
        label: Section label like "ch1" (for save/get/delete)
        order: Section order number (for save)
        tags: Tags for categorization (for save)
        query: Search query (for search)
        n_results: Number of search results (default 5)
    """
    collection = get_collection(project_id, "content")

    if action == "save":
        return _save(collection, project_id, text, label, order, tags)

    if action == "get":
        doc_id = f"section_{label.lower().replace(' ', '_')}"
        r = collection.get(ids=[doc_id], include=["documents", "metadatas"])
        if r and r["documents"] and r["documents"][0]:
            return {"label": label, "text": r["documents"][0],
                    "words": r["metadatas"][0].get("word_count", 0)}
        return {"error": f"Section '{label}' not found"}

    if action == "search":
        if collection.count() == 0:
            return {"results": []}
        n = min(n_results, collection.count())
        s = collection.query(query_texts=[query], n_results=n,
                             include=["documents", "metadatas", "distances"])
        if not s or not s["documents"]:
            return {"results": []}
        return {"results": [
            {
                "label": s["metadatas"][0][i].get("parent_id", s["metadatas"][0][i].get("label", "")),
                "preview": doc[:200],
                "distance": round(s["distances"][0][i], 3),
            }
            for i, doc in enumerate(s["documents"][0])
        ]}

    if action == "outline":
        data = collection.get(include=["documents", "metadatas"])
        if not data or not data["documents"]:
            return {"sections": []}
        sections = []
        for i, doc in enumerate(data["documents"]):
            m = data["metadatas"][i]
            if m.get("parent_id"):
                continue
            sections.append({
                "label": m.get("label", ""),
                "order": m.get("order", 9999),
                "words": m.get("word_count", len(doc.split())),
            })
        sections.sort(key=lambda s: s["order"])
        return {"sections": sections}

    if action == "delete":
        doc_id = f"section_{label.lower().replace(' ', '_')}"
        data = collection.get(include=["metadatas"])
        ids_del = [data["ids"][i] for i, m in enumerate(data["metadatas"])
                   if data["ids"][i] == doc_id or m.get("parent_id") == doc_id]
        if not ids_del:
            return {"error": f"Section '{label}' not found"}
        collection.delete(ids=ids_del)
        _rebuild_output_file(project_id, collection)
        return {"label": label, "status": "deleted"}

    return {"error": f"Unknown action '{action}'. Use: save, get, search, outline, delete"}


def _save(collection, project_id, text, label, order, tags):
    if order is None:
        order = collection.count() + 1
    now = datetime.now().isoformat()
    doc_id = f"section_{label.lower().replace(' ', '_')}" if label else str(uuid.uuid4())

    metadata = {
        "created_at": now,
        "tags": ",".join(tags) if tags else "",
        "label": label or "",
        "order": order,
        "word_count": len(text.split()),
    }
    collection.upsert(ids=[doc_id], documents=[text], metadatas=[metadata])
    _store_chunks(collection, doc_id, text, label or doc_id, order, tags, now)
    _rebuild_output_file(project_id, collection)
    return {"id": doc_id, "label": label, "words": metadata["word_count"], "status": "saved"}


# Keep save_content as a callable for canvas integration
def save_content(text, project_id, label=None, order=None, tags=None):
    collection = get_collection(project_id, "content")
    return _save(collection, project_id, text, label, order, tags)


def _store_chunks(collection, parent_id, text, label, order, tags, timestamp):
    data = collection.get(include=["metadatas"])
    old = [data["ids"][i] for i, m in enumerate(data["metadatas"]) if m.get("parent_id") == parent_id]
    if old:
        collection.delete(ids=old)

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paragraphs) <= 2:
        return

    chunks, current, wc = [], [], 0
    for para in paragraphs:
        current.append(para)
        wc += len(para.split())
        if wc >= 50:
            chunks.append("\n\n".join(current))
            current, wc = [], 0
    if current:
        chunks.append("\n\n".join(current))

    tag_str = ",".join(tags) if tags else ""
    for i, chunk in enumerate(chunks):
        collection.upsert(
            ids=[f"{parent_id}_chunk_{i}"],
            documents=[chunk],
            metadatas=[{
                "parent_id": parent_id, "chunk_index": i,
                "label": label, "order": order,
                "tags": tag_str, "created_at": timestamp,
            }],
        )


def _rebuild_output_file(project_id, collection):
    from pathlib import Path
    from core.db import get_project_metadata

    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)

    meta = get_project_metadata(project_id)
    project_name = meta.get("project_name", project_id) if meta else project_id

    data = collection.get(include=["documents", "metadatas"])
    if not data or not data["documents"]:
        return

    sections, total = [], 0
    for i, doc in enumerate(data["documents"]):
        m = data["metadatas"][i]
        if m.get("parent_id"):
            continue
        wc = m.get("word_count", len(doc.split()))
        total += wc
        sections.append((m.get("order", 9999), doc, wc))
    sections.sort(key=lambda s: s[0])

    safe = re.sub(r"[^\w\s-]", "", project_name).strip().lower().replace(" ", "_")
    filepath = output_dir / f"{safe}.txt"

    if filepath.exists():
        (output_dir / f".{safe}.txt.bak").write_text(filepath.read_text())

    with open(filepath, "w") as f:
        f.write(f"{project_name}\n{len(sections)} sections | {total:,} words\n{'='*60}\n")
        for i, (_, text, _) in enumerate(sections):
            f.write(f"\n{text.rstrip()}\n")
            if i < len(sections) - 1:
                f.write("\n---\n")
