"""End-to-end smoke test for Creative Memory MCP Server."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.db import get_client, get_collection, create_project_collections, get_project_metadata, list_project_ids
from core.models import Project
from core.embeddings import get_embedding_function


def test_ollama_connection():
    ef = get_embedding_function()
    result = ef(["test embedding connection"])
    assert len(result) > 0, "Embedding returned empty"
    assert len(result[0]) == 768, f"Expected 768 dims, got {len(result[0])}"
    print("PASS: Ollama connection + nomic-embed-text")


def test_create_project():
    project = Project(name="Test World", content_type="novel")
    create_project_collections(project)

    ids = list_project_ids()
    assert project.id in ids, f"Project {project.id} not in {ids}"

    meta = get_project_metadata(project.id)
    assert meta is not None
    assert meta["project_name"] == "Test World"
    print(f"PASS: Project created (id={project.id})")
    return project.id


def test_save_and_search(project_id: str):
    col = get_collection(project_id, "content")

    col.add(
        ids=["test1", "test2", "test3"],
        documents=[
            "The dragon Vermithor swooped over the castle walls, breathing fire.",
            "Princess Elara studied the ancient spell books in the tower library.",
            "The blacksmith forged a blade of enchanted steel under the full moon.",
        ],
        metadatas=[
            {"tags": "action,dragon", "chapter": "3"},
            {"tags": "character,magic", "chapter": "5"},
            {"tags": "crafting,magic", "chapter": "7"},
        ],
    )

    results = col.query(
        query_texts=["fire-breathing creature attacking"],
        n_results=2,
        include=["documents", "distances"],
    )

    top = results["documents"][0][0]
    assert "dragon" in top.lower() or "Vermithor" in top
    print(f"PASS: Semantic search (top result: {top[:50]}...)")


def test_entity_upsert(project_id: str):
    col = get_collection(project_id, "entities")

    col.upsert(
        ids=["entity_kael_stormrider"],
        documents=["A tall warrior with silver hair and a scar across his left eye."],
        metadatas=[{"name": "Kael Stormrider", "entity_type": "character"}],
    )

    result = col.get(ids=["entity_kael_stormrider"], include=["documents", "metadatas"])
    assert result["documents"][0] is not None
    assert result["metadatas"][0]["name"] == "Kael Stormrider"
    print("PASS: Entity save + retrieval")


def test_lore(project_id: str):
    col = get_collection(project_id, "lore")

    col.upsert(
        ids=["lore_magic_system"],
        documents=["Magic is drawn from moonlight. Spells are stronger during full moons."],
        metadatas=[{"topic": "Magic System"}],
    )

    results = col.query(
        query_texts=["how does magic work"],
        n_results=1,
        include=["documents", "distances"],
    )

    assert "moonlight" in results["documents"][0][0].lower()
    print("PASS: Lore save + semantic retrieval")


def cleanup(project_id: str):
    client = get_client()
    for suffix in ("_content", "_entities", "_lore"):
        try:
            client.delete_collection(f"{project_id}{suffix}")
        except Exception:
            pass
    print(f"Cleaned up test project {project_id}")


if __name__ == "__main__":
    print("=== Creative Memory E2E Test ===\n")
    test_ollama_connection()
    pid = test_create_project()
    test_save_and_search(pid)
    test_entity_upsert(pid)
    test_lore(pid)
    cleanup(pid)
    print("\nAll tests passed!")
