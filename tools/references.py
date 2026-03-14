from datetime import datetime

from app import mcp
from core.db import get_collection


@mcp.tool()
def reference(
    action: str,
    project_id: str,
    topic: str = "",
    content: str = "",
) -> dict:
    """Manage reference notes (style guides, rules, facts, timelines).

    Actions:
      save — store/update a reference (needs: topic, content)
      get — look up by topic (needs: topic)
      list — show all references

    Args:
        action: save, get, or list
        project_id: Project ID
        topic: Reference topic
        content: Reference content
    """
    collection = get_collection(project_id, "references")

    if action == "save":
        rid = f"ref_{topic.lower().replace(' ', '_')}"
        collection.upsert(
            ids=[rid],
            documents=[content],
            metadatas=[{
                "topic": topic,
                "updated_at": datetime.now().isoformat(),
            }],
        )
        return {"id": rid, "topic": topic, "status": "saved"}

    if action == "get":
        rid = f"ref_{topic.lower().replace(' ', '_')}"
        hit = collection.get(ids=[rid], include=["documents", "metadatas"])
        if hit and hit["documents"] and hit["documents"][0]:
            return {
                "topic": hit["metadatas"][0].get("topic", topic),
                "content": hit["documents"][0],
            }
        if collection.count() > 0:
            s = collection.query(query_texts=[topic], n_results=1,
                                 include=["documents", "metadatas"])
            if s and s["documents"] and s["documents"][0]:
                return {
                    "topic": s["metadatas"][0][0].get("topic", "?"),
                    "content": s["documents"][0][0],
                    "match": "semantic",
                }
        return {"error": f"Reference '{topic}' not found"}

    if action == "list":
        data = collection.get(include=["metadatas"])
        if not data or not data["metadatas"]:
            return {"references": []}
        return {"references": [
            {"topic": m.get("topic", "?")} for m in data["metadatas"]
        ]}

    return {"error": f"Unknown action '{action}'. Use: save, get, list"}
