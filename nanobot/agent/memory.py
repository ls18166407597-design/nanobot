"""Memory system for persistent agent memory."""

from datetime import datetime
from pathlib import Path
import re
import math
from collections import Counter

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
        Search long-term memory using hybrid lexical retrieval (Light RAG).
        
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

        chunks = self._split_chunks(content)
        if not chunks:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # Build per-chunk stats for BM25-like lexical scoring.
        chunk_tokens = [self._tokenize(c) for c in chunks]
        token_counts = [Counter(toks) for toks in chunk_tokens]
        doc_lens = [sum(c.values()) for c in token_counts]
        avg_len = sum(doc_lens) / max(1, len(doc_lens))

        # Document frequency
        df: Counter[str] = Counter()
        for toks in chunk_tokens:
            for t in set(toks):
                df[t] += 1

        n_docs = len(chunks)
        scored_chunks: list[tuple[float, str]] = []
        query_set = set(query_tokens)
        k1 = 1.2
        b = 0.75
        for i, chunk in enumerate(chunks):
            bm25 = 0.0
            for t in query_set:
                f = token_counts[i].get(t, 0)
                if f <= 0:
                    continue
                idf = math.log(1 + (n_docs - df[t] + 0.5) / (df[t] + 0.5))
                denom = f + k1 * (1 - b + b * (doc_lens[i] / max(1.0, avg_len)))
                bm25 += idf * ((f * (k1 + 1)) / max(1e-9, denom))

            # Add fuzzy semantic proxy via char-trigram jaccard
            # so paraphrased wording still gets non-zero score.
            fuzzy = self._char_ngram_jaccard(query, chunk, n=3)
            score = bm25 + 0.6 * fuzzy
            if score > 0:
                scored_chunks.append((score, chunk))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        return [chunk for _, chunk in scored_chunks[:top_k]]

    def _split_chunks(self, content: str) -> list[str]:
        chunks = []
        current_chunk = []
        for line in content.splitlines():
            if line.startswith("#") and current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
            current_chunk.append(line)
        if current_chunk:
            chunks.append("\n".join(current_chunk))
        return chunks

    def _tokenize(self, text: str) -> list[str]:
        text = text.lower()
        # English/number tokens
        en_tokens = re.findall(r"[a-z0-9_+-]{2,}", text)
        # CJK contiguous blocks (lightweight, no external deps)
        zh_blocks = re.findall(r"[\u4e00-\u9fff]{2,}", text)
        zh_tokens: list[str] = []
        for blk in zh_blocks:
            # Keep block itself + bigrams for better recall on wording changes
            zh_tokens.append(blk)
            if len(blk) > 2:
                zh_tokens.extend(blk[i : i + 2] for i in range(len(blk) - 1))

        stop_en = {
            "the", "is", "at", "which", "on", "a", "an", "and", "or", "but", "to", "for", "in", "with",
            "that", "this", "from", "are", "was", "were", "be", "as", "by", "it", "of",
        }
        stop_zh = {"这个", "那个", "我们", "你们", "他们", "以及", "然后", "就是", "可以", "需要", "一下", "一个"}
        tokens = [t for t in (en_tokens + zh_tokens) if t not in stop_en and t not in stop_zh]
        return tokens

    def _char_ngram_jaccard(self, query: str, doc: str, n: int = 3) -> float:
        def grams(s: str) -> set[str]:
            s = re.sub(r"\s+", "", s.lower())
            if len(s) < n:
                return {s} if s else set()
            return {s[i : i + n] for i in range(len(s) - n + 1)}

        gq = grams(query)
        gd = grams(doc[:2000])  # keep cost bounded
        if not gq or not gd:
            return 0.0
        inter = len(gq & gd)
        union = len(gq | gd)
        return inter / union if union else 0.0

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
