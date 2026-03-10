from app import mcp

# Import tool modules to trigger @mcp.tool() registration
import tools.projects  # noqa: F401
import tools.content  # noqa: F401
import tools.entities  # noqa: F401
import tools.references  # noqa: F401

if __name__ == "__main__":
    mcp.run()
