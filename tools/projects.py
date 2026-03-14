from app import mcp
from core.db import create_project_collections, get_collection, get_project_metadata, list_project_ids
from core.models import Project


@mcp.tool()
def project(
    action: str,
    name: str = "",
    content_type: str = "",
    project_id: str = "",
) -> dict:
    """Manage writing projects.

    Actions:
      create — make a new project (needs: name, content_type)
      list — show all projects
      summary — get counts for a project (needs: project_id)

    Args:
        action: create, list, or summary
        name: Project name (for create)
        content_type: e.g. novel, blog, documentation (for create)
        project_id: Project ID (for summary)
    """
    if action == "create":
        p = Project(name=name, content_type=content_type)
        create_project_collections(p)
        return {"id": p.id, "name": p.name, "status": "created"}

    if action == "list":
        out = []
        for pid in list_project_ids():
            meta = get_project_metadata(pid)
            if meta:
                out.append({"id": pid, "name": meta.get("project_name", "?")})
        return {"projects": out}

    if action == "summary":
        meta = get_project_metadata(project_id)
        if not meta:
            return {"error": f"Project '{project_id}' not found"}
        return {
            "id": project_id,
            "name": meta.get("project_name", "?"),
            "content": get_collection(project_id, "content").count(),
            "entities": get_collection(project_id, "entities").count(),
            "references": get_collection(project_id, "references").count(),
            "elements": get_collection(project_id, "elements").count(),
        }

    return {"error": f"Unknown action '{action}'. Use: create, list, summary"}
