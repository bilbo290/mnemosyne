from datetime import datetime

from app import mcp
from core.db import get_collection


@mcp.tool()
def save_entity(
    name: str,
    entity_type: str,
    details: str,
    project_id: str,
) -> dict:
    """Store or update a reusable entity profile in the project.

    Entities are things that recur across your content and need to stay
    consistent: people, companies, products, characters, places, concepts.

    Args:
        name: Entity name (e.g., "Jane Chen", "Acme Corp", "Kael Stormrider", "React Router")
        entity_type: What kind of entity (e.g., "person", "company", "product",
                     "character", "location", "concept", "term")
        details: Full description/profile of the entity
        project_id: The project this entity belongs to
    """
    collection = get_collection(project_id, "entities")

    entity_id = f"entity_{name.lower().replace(' ', '_')}"

    collection.upsert(
        ids=[entity_id],
        documents=[details],
        metadatas=[{
            "name": name,
            "entity_type": entity_type,
            "updated_at": datetime.now().isoformat(),
        }],
    )

    return {"id": entity_id, "name": name, "entity_type": entity_type, "status": "saved"}


@mcp.tool()
def get_entity(name: str, project_id: str) -> dict:
    """Look up an entity by name. Tries exact match, then semantic fallback.

    Args:
        name: The entity name to look up
        project_id: The project to search in
    """
    collection = get_collection(project_id, "entities")

    entity_id = f"entity_{name.lower().replace(' ', '_')}"

    results = collection.get(
        ids=[entity_id],
        include=["documents", "metadatas"],
    )

    if results and results["documents"] and len(results["documents"]) > 0:
        return {
            "name": results["metadatas"][0].get("name", name),
            "entity_type": results["metadatas"][0].get("entity_type", "unknown"),
            "details": results["documents"][0],
            "metadata": results["metadatas"][0],
        }

    # Fallback: semantic search
    if collection.count() > 0:
        search = collection.query(
            query_texts=[name],
            n_results=1,
            include=["documents", "metadatas", "distances"],
        )
        if search and search["documents"] and search["documents"][0]:
            return {
                "name": search["metadatas"][0][0].get("name", "Unknown"),
                "entity_type": search["metadatas"][0][0].get("entity_type", "unknown"),
                "details": search["documents"][0][0],
                "metadata": search["metadatas"][0][0],
                "match_type": "semantic",
                "distance": search["distances"][0][0],
            }

    return {"error": f"Entity '{name}' not found in project '{project_id}'"}


@mcp.tool()
def list_entities(project_id: str) -> list[dict]:
    """List all entities in a project with their names and types.

    Args:
        project_id: The project to list entities for
    """
    collection = get_collection(project_id, "entities")
    all_data = collection.get(include=["metadatas"])

    if not all_data or not all_data["metadatas"]:
        return []

    entities = []
    for m in all_data["metadatas"]:
        entities.append({
            "name": m.get("name", "Unknown"),
            "entity_type": m.get("entity_type", "unknown"),
            "updated_at": m.get("updated_at", ""),
        })

    entities.sort(key=lambda e: (e["entity_type"], e["name"]))
    return entities
