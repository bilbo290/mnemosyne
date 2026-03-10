import os
from pathlib import Path

import chromadb

from core.embeddings import get_embedding_function
from core.models import Project

CHROMA_PATH = os.environ.get(
    "CHROMA_PATH",
    str(Path.home() / ".mnemosyne" / "chroma"),
)

_client: chromadb.ClientAPI | None = None


def get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        Path(CHROMA_PATH).mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=CHROMA_PATH)
    return _client


def get_collection(project_id: str, collection_type: str):
    """Get or create a typed collection for a project.

    collection_type: one of "content", "entities", "references"
    """
    client = get_client()
    ef = get_embedding_function()
    name = f"{project_id}_{collection_type}"
    return client.get_or_create_collection(
        name=name,
        embedding_function=ef,
    )


def create_project_collections(project: Project):
    """Create all 3 collections for a new project."""
    client = get_client()
    ef = get_embedding_function()

    client.get_or_create_collection(
        name=f"{project.id}_content",
        embedding_function=ef,
        metadata={
            "project_name": project.name,
            "content_type": project.content_type,
            "created_at": project.created_at,
        },
    )
    client.get_or_create_collection(
        name=f"{project.id}_entities",
        embedding_function=ef,
    )
    client.get_or_create_collection(
        name=f"{project.id}_references",
        embedding_function=ef,
    )


def get_project_metadata(project_id: str) -> dict | None:
    """Retrieve project metadata from the content collection."""
    client = get_client()
    ef = get_embedding_function()
    try:
        col = client.get_collection(
            name=f"{project_id}_content",
            embedding_function=ef,
        )
        return col.metadata
    except Exception:
        return None


def list_project_ids() -> list[str]:
    """Extract unique project IDs from collection names."""
    client = get_client()
    collections = client.list_collections()
    project_ids: set[str] = set()
    for name in collections:
        name_str = name if isinstance(name, str) else name.name if hasattr(name, "name") else str(name)
        for suffix in ("_content", "_entities", "_references"):
            if name_str.endswith(suffix):
                project_ids.add(name_str[: -len(suffix)])
                break
    return sorted(project_ids)
