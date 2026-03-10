from app import mcp
from core.db import create_project_collections, get_collection, get_project_metadata, list_project_ids
from core.models import Project, ProjectSummary


@mcp.tool()
def create_project(name: str, content_type: str) -> dict:
    """Create a new writing project with memory collections.

    Args:
        name: The project name (e.g., "Q2 Blog Series", "API Documentation", "My Novel")
        content_type: What kind of content (e.g., "blog", "documentation", "novel",
                      "marketing", "article_series", "screenplay", "technical_guide")
    """
    project = Project(name=name, content_type=content_type)
    create_project_collections(project)
    return project.model_dump()


@mcp.tool()
def list_projects() -> list[dict]:
    """List all writing projects."""
    project_ids = list_project_ids()
    projects = []
    for pid in project_ids:
        meta = get_project_metadata(pid)
        if meta:
            projects.append({
                "id": pid,
                "name": meta.get("project_name", "Unknown"),
                "content_type": meta.get("content_type", "Unknown"),
                "created_at": meta.get("created_at", "Unknown"),
            })
    return projects


@mcp.tool()
def get_project_summary(project_id: str) -> dict:
    """Get a project overview: section count, entity count, reference count, total words.

    Args:
        project_id: The unique project identifier
    """
    meta = get_project_metadata(project_id)
    if not meta:
        return {"error": f"Project '{project_id}' not found"}

    content_col = get_collection(project_id, "content")
    entity_col = get_collection(project_id, "entities")
    ref_col = get_collection(project_id, "references")

    return ProjectSummary(
        project=Project(
            id=project_id,
            name=meta.get("project_name", "Unknown"),
            content_type=meta.get("content_type", "Unknown"),
            created_at=meta.get("created_at", "Unknown"),
        ),
        content_count=content_col.count(),
        entity_count=entity_col.count(),
        reference_count=ref_col.count(),
    ).model_dump()
