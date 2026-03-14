from datetime import datetime

from app import mcp
from core.db import get_collection


@mcp.tool()
def entity(
    action: str,
    project_id: str,
    name: str = "",
    entity_type: str = "",
    details: str = "",
) -> dict:
    """Manage entity profiles (characters, locations, concepts).

    Actions:
      save — store/update an entity (needs: name, entity_type, details)
      get — look up by name (needs: name)
      list — show all entities

    Args:
        action: save, get, or list
        project_id: Project ID
        name: Entity name
        entity_type: character, location, concept, etc.
        details: Full description/profile
    """
    collection = get_collection(project_id, "entities")

    if action == "save":
        eid = f"entity_{name.lower().replace(' ', '_')}"
        collection.upsert(
            ids=[eid],
            documents=[details],
            metadatas=[{
                "name": name,
                "entity_type": entity_type,
                "updated_at": datetime.now().isoformat(),
            }],
        )
        return {"id": eid, "name": name, "status": "saved"}

    if action == "get":
        eid = f"entity_{name.lower().replace(' ', '_')}"
        hit = collection.get(ids=[eid], include=["documents", "metadatas"])
        if hit and hit["documents"] and hit["documents"][0]:
            return {
                "name": hit["metadatas"][0].get("name", name),
                "type": hit["metadatas"][0].get("entity_type", "?"),
                "details": hit["documents"][0],
            }
        # Semantic fallback
        if collection.count() > 0:
            s = collection.query(query_texts=[name], n_results=1,
                                 include=["documents", "metadatas"])
            if s and s["documents"] and s["documents"][0]:
                return {
                    "name": s["metadatas"][0][0].get("name", "?"),
                    "type": s["metadatas"][0][0].get("entity_type", "?"),
                    "details": s["documents"][0][0],
                    "match": "semantic",
                }
        return {"error": f"Entity '{name}' not found"}

    if action == "list":
        data = collection.get(include=["metadatas"])
        if not data or not data["metadatas"]:
            return {"entities": []}
        return {"entities": [
            {"name": m.get("name", "?"), "type": m.get("entity_type", "?")}
            for m in data["metadatas"]
        ]}

    return {"error": f"Unknown action '{action}'. Use: save, get, list"}
