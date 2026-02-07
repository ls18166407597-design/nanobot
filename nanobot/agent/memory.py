"""Memory system for persistent agent memory."""

from datetime import datetime
from pathlib import Path
import re

from nanobot.utils.helpers import ensure_dir, today_date


class MemoryStore:
    """
    Memory system for the agent.

    Supports daily notes (memory/YYYY-MM-DD.md) and long-term memory (MEMORY.md).
    """

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory_dir = ensure_dir(workspace / "memory")
        self.memory_file = self.memory_dir / "MEMORY.md"

    def get_today_file(self) -> Path:
        """Get path to today's memory file."""
        return self.memory_dir / f"{today_date()}.md"

    def read_today(self) -> str:
        """Read today's memory notes."""
        today_file = self.get_today_file()
        if today_file.exists():
            return today_file.read_text(encoding="utf-8")
        return ""

    def append_today(self, content: str) -> None:
        """Append content to today's memory notes."""
        today_file = self.get_today_file()

        if today_file.exists():
            existing = today_file.read_text(encoding="utf-8")
            content = existing + "\n" + content
        else:
            # Add header for new day
            header = f"# {today_date()}\n\n"
            content = header + content

        today_file.write_text(content, encoding="utf-8")

    def read_long_term(self, limit: int | None = None) -> str:
        """Read long-term memory (MEMORY.md)."""
        if self.memory_file.exists():
            if limit:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    return f.read(limit)
            return self.memory_file.read_text(encoding="utf-8")
        return ""

    def write_long_term(self, content: str) -> None:
        """Write to long-term memory (MEMORY.md)."""
        self.memory_file.write_text(content, encoding="utf-8")

    def get_recent_memories(self, days: int = 7) -> str:
        """
        Get memories from the last N days.

        Args:
            days: Number of days to look back.

        Returns:
            Combined memory content.
        """
        from datetime import timedelta

        memories = []
        today = datetime.now().date()

        for i in range(days):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            file_path = self.memory_dir / f"{date_str}.md"

            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                memories.append(content)

        return "\n\n---\n\n".join(memories)

    def list_memory_files(self) -> list[Path]:
        """List all memory files sorted by date (newest first)."""
        if not self.memory_dir.exists():
            return []

        files = list(self.memory_dir.glob("????-??-??.md"))
        return sorted(files, reverse=True)

    def search(self, query: str, top_k: int = 3) -> list[str]:
        """
        Search long-term memory using simple keyword matching (Light RAG).
        
        Args:
            query: The search query.
            top_k: Number of chunks to return.
            
        Returns:
            List of relevant memory chunks.
        """
        if not self.memory_file.exists():
            return []

        content = self.memory_file.read_text(encoding="utf-8")
        if not content:
            return []

        # Simple chunking by headers
        chunks = []
        current_chunk = []
        
        for line in content.splitlines():
            if line.startswith("#") and current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
            current_chunk.append(line)
            
        if current_chunk:
            chunks.append("\n".join(current_chunk))

        # Score chunks
        query_terms = set(re.findall(r"\w+", query.lower()))
        # Remove common stopwords to improve quality
        stopwords = {"the", "is", "at", "which", "on", "a", "an", "and", "or", "but", "to", "for", "in", "with"}
        query_terms = {t for t in query_terms if t not in stopwords and len(t) > 2}
        
        if not query_terms:
            return []

        scored_chunks = []
        for chunk in chunks:
            chunk_lower = chunk.lower()
            score = sum(1 for term in query_terms if term in chunk_lower)
            if score > 0:
                scored_chunks.append((score, chunk))

        # Sort by score desc
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        
        return [chunk for score, chunk in scored_chunks[:top_k]]

    def get_memory_context(self, query: str | None = None) -> str:
        """
        Get memory context for the agent.

        Args:
            query: Optional query to search memory with (Light RAG).

        Returns:
            Formatted memory context including long-term and recent memories.
        """
        parts = []

        # Long-term memory
        if query:
            # Light RAG mode: Search for relevant chunks
            hints = self.search(query)
            if hints:
                parts.append("## Relevant Memories (retrieved)\n" + "\n---\n".join(hints))
            else:
                 # Fallback to teaser if no hits
                long_term = self.read_long_term(limit=1000)
                if long_term:
                    parts.append("## Long-term Memory (summary)\n" + long_term)
        else:
             # Default mode: Teaser
            long_term = self.read_long_term(limit=2000)
            if long_term:
                parts.append("## Long-term Memory\n" + long_term)

        # Today's notes
        today = self.read_today()
        if today:
            parts.append("## Today's Notes\n" + today)

        return "\n\n".join(parts) if parts else ""
