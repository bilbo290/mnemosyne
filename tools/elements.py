import uuid
from datetime import datetime

from app import mcp
from core.db import get_collection


@mcp.tool()
def element(
    action: str,
    project_id: str,
    chapter: str = "",
    description: str = "",
    element_type: str = "plot_point",
    status: str = "proposed",
    element_id: str = "",
    intent: str = "",
    entity_names: list[str] | None = None,
    notes: str = "",
) -> dict:
    """Manage chapter elements — the building blocks of a scene.

    Actions:
      add — add a beat (needs: chapter, description, element_type)
      list — show elements for a chapter (needs: chapter)
      update — change status/description (needs: element_id; optional: status, description, notes)
      remove — delete an element (needs: element_id)
      suggest — gather context to brainstorm (needs: chapter, intent; optional: entity_names)

    element_type: plot_point, character_moment, dialogue, setting, theme,
                  conflict, revelation, transition, action, emotion, foreshadowing

    Args:
        action: add, list, update, remove, or suggest
        project_id: Project ID
        chapter: Chapter label (e.g. "ch1")
        description: What this element is
        element_type: Type of beat
        status: proposed, accepted, or rejected
        element_id: Element ID (for update/remove)
        intent: What the chapter is about (for suggest)
        entity_names: Characters involved (for suggest)
        notes: Extra notes
    """
    # Coerce chapter to string (LLMs sometimes send int)
    chapter = str(chapter) if chapter else ""
    ch = chapter.lower().replace(" ", "_") if chapter else ""

    if action == "add":
        collection = get_collection(project_id, "elements")
        eid = f"elem_{uuid.uuid4().hex[:8]}"
        collection.upsert(
            ids=[eid],
            documents=[description],
            metadatas=[{
                "chapter": ch,
                "element_type": element_type,
                "status": status,
                "notes": notes,
                "created_at": datetime.now().isoformat(),
            }],
        )
        return {"id": eid, "type": element_type, "status": status}

    if action == "list":
        collection = get_collection(project_id, "elements")
        if collection.count() == 0:
            return {"elements": []}
        if ch:
            results = collection.get(
                where={"chapter": ch},
                include=["documents", "metadatas"],
            )
        else:
            results = collection.get(include=["documents", "metadatas"])
        if not results or not results["documents"]:
            return {"elements": []}
        return {"elements": [
            {
                "id": results["ids"][i],
                "desc": doc[:150],
                "type": results["metadatas"][i].get("element_type", "?"),
                "status": results["metadatas"][i].get("status", "?"),
            }
            for i, doc in enumerate(results["documents"])
        ]}

    if action == "update":
        collection = get_collection(project_id, "elements")
        hit = collection.get(ids=[element_id], include=["documents", "metadatas"])
        if not hit or not hit["ids"] or len(hit["ids"]) == 0:
            return {"error": f"Element '{element_id}' not found"}
        new_doc = description if description else hit["documents"][0]
        new_meta = dict(hit["metadatas"][0])
        if status:
            new_meta["status"] = status
        if notes:
            new_meta["notes"] = notes
        collection.update(ids=[element_id], documents=[new_doc], metadatas=[new_meta])
        return {"id": element_id, "status": new_meta["status"]}

    if action == "remove":
        collection = get_collection(project_id, "elements")
        hit = collection.get(ids=[element_id], include=["metadatas"])
        if not hit or not hit["ids"] or len(hit["ids"]) == 0:
            return {"error": f"Element '{element_id}' not found"}
        collection.delete(ids=[element_id])
        return {"id": element_id, "status": "removed"}

    if action == "suggest":
        return _suggest(project_id, ch, intent, entity_names)

    return {"error": f"Unknown action '{action}'. Use: add, list, update, remove, suggest"}


def _suggest(project_id: str, chapter: str, intent: str, entity_names: list[str] | None) -> dict:
    """Gather compact context for brainstorming."""
    result: dict = {"chapter": chapter, "elements": [], "context": [], "entities": []}

    # Existing elements
    elem_col = get_collection(project_id, "elements")
    if elem_col.count() > 0:
        data = elem_col.get(where={"chapter": chapter}, include=["documents", "metadatas"])
        if data and data["documents"]:
            result["elements"] = [
                {"id": data["ids"][i], "desc": doc[:100], "status": data["metadatas"][i].get("status", "?")}
                for i, doc in enumerate(data["documents"])
            ]

    # Relevant past content (truncated previews)
    content_col = get_collection(project_id, "content")
    if content_col.count() > 0:
        n = min(3, content_col.count())
        search = content_col.query(query_texts=[intent], n_results=n,
                                   include=["documents", "metadatas", "distances"])
        if search and search["documents"]:
            seen = set()
            for i, doc in enumerate(search["documents"][0]):
                meta = search["metadatas"][0][i]
                lbl = meta.get("parent_id", meta.get("label", ""))
                if lbl in seen:
                    continue
                seen.add(lbl)
                result["context"].append({"label": lbl, "preview": doc[:200]})

    # Entity profiles (truncated)
    if entity_names:
        ent_col = get_collection(project_id, "entities")
        for name in entity_names:
            eid = f"entity_{name.lower().replace(' ', '_')}"
            hit = ent_col.get(ids=[eid], include=["documents", "metadatas"])
            if hit and hit["documents"] and hit["documents"][0]:
                result["entities"].append({
                    "name": hit["metadatas"][0].get("name", name),
                    "details": hit["documents"][0][:200],
                })

    # References (truncated, top 2)
    ref_col = get_collection(project_id, "references")
    if ref_col.count() > 0:
        refs = ref_col.query(query_texts=[intent], n_results=2,
                             include=["documents", "metadatas"])
        if refs and refs["documents"] and refs["documents"][0]:
            result["refs"] = [
                {"topic": refs["metadatas"][0][i].get("topic", "?"), "text": doc[:150]}
                for i, doc in enumerate(refs["documents"][0])
            ]

    return result
