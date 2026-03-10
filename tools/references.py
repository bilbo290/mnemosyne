from datetime import datetime

from app import mcp
from core.db import get_collection


@mcp.tool()
def save_reference(
    topic: str,
    content: str,
    project_id: str,
) -> dict:
    """Store a reference note for the project — facts, rules, or guidelines
    that should stay consistent across all content.

    Good for: style guides, brand voice rules, terminology definitions,
    key facts, timelines, canon rules, technical constraints.

    If a reference with the same topic exists, it will be updated.

    Args:
        topic: Reference topic (e.g., "Brand Voice", "API Naming Conventions",
               "Magic System Rules", "Character Ages", "Product Pricing")
        content: The reference content
        project_id: The project this reference belongs to
    """
    collection = get_collection(project_id, "references")

    ref_id = f"ref_{topic.lower().replace(' ', '_')}"

    collection.upsert(
        ids=[ref_id],
        documents=[content],
        metadatas=[{
            "topic": topic,
            "updated_at": datetime.now().isoformat(),
        }],
    )

    return {"id": ref_id, "topic": topic, "status": "saved"}


@mcp.tool()
def get_reference(topic: str, project_id: str) -> dict:
    """Look up a reference note by topic. Tries exact match, then semantic fallback.

    Args:
        topic: The reference topic to look up
        project_id: The project to search in
    """
    collection = get_collection(project_id, "references")

    ref_id = f"ref_{topic.lower().replace(' ', '_')}"

    results = collection.get(
        ids=[ref_id],
        include=["documents", "metadatas"],
    )

    if results and results["documents"] and len(results["documents"]) > 0:
        return {
            "topic": results["metadatas"][0].get("topic", topic),
            "content": results["documents"][0],
            "metadata": results["metadatas"][0],
        }

    # Fallback: semantic search
    if collection.count() > 0:
        search = collection.query(
            query_texts=[topic],
            n_results=1,
            include=["documents", "metadatas", "distances"],
        )
        if search and search["documents"] and search["documents"][0]:
            return {
                "topic": search["metadatas"][0][0].get("topic", "Unknown"),
                "content": search["documents"][0][0],
                "metadata": search["metadatas"][0][0],
                "match_type": "semantic",
                "distance": search["distances"][0][0],
            }

    return {"error": f"Reference '{topic}' not found in project '{project_id}'"}


@mcp.tool()
def list_references(project_id: str) -> list[dict]:
    """List all reference notes in a project.

    Args:
        project_id: The project to list references for
    """
    collection = get_collection(project_id, "references")
    all_data = collection.get(include=["metadatas"])

    if not all_data or not all_data["metadatas"]:
        return []

    refs = []
    for m in all_data["metadatas"]:
        refs.append({
            "topic": m.get("topic", "Unknown"),
            "updated_at": m.get("updated_at", ""),
        })

    refs.sort(key=lambda r: r["topic"])
    return refs
