"""Agent Memory Integration Module.

This module provides the core `MemoryEnabledAgent` which wires together all components
of the memory subsystem as required by the Copperleaf Kitchens Architecture:
1. Short-Term Memory is initialized with an overflow callback.
2. The overflow callback directly routes evicted items to the Promote-or-Drop Router.
3. The Consolidation Engine is called periodically to convert episodic events into semantic facts.
4. Context strategy (Sliding Window by default) formats the context window on each turn.
5. SelfRAGVerifier post-processes every agent response for relevance and grounding.
6. AgenticRAGOrchestrator enriches context with RAG-retrieved knowledge on every turn.
"""

from typing import Any, Dict, List, Optional

from memory.consolidation import SemanticConsolidationEngine
from memory.episodic import EpisodicMemory
from memory.router import PromoteOrDropRouter
from memory.scratchpad import Scratchpad
from memory.semantic import SemanticMemory
from memory.short_term import ShortTermMemory, ShortTermMemoryItem
from memory.verification import SelfRAGVerifier, VerificationResult
from context_eval.sliding_window import SlidingWindowStrategy, BaseContextStrategy


class MemoryEnabledAgent:
    """An AI Agent that seamlessly integrates all levels of the Memory Architecture.

    Integrates:
    - Short-Term Memory (STM) with rolling FIFO overflow routing
    - Promote-or-Drop Router (evicted STM → Episodic store)
    - Scratchpad working memory for active task state
    - Semantic Consolidation Engine (Episodic → Semantic facts)
    - Context Window Strategy (default: Sliding Window)
    - Self-RAG Verifier (IS_REL + IS_SUP checks on every response)
    - Agentic RAG Orchestrator (knowledge retrieval loop)
    """

    def __init__(
        self,
        stm_capacity: int = 10,
        consolidation_batch_size: int = 5,
        context_strategy: Optional[BaseContextStrategy] = None,
        relevance_threshold: float = 0.4,
        support_threshold: float = 0.4,
        enable_rag: bool = True,
    ) -> None:
        """Initialize the agent with its memory subsystems.

        Args:
            stm_capacity: Maximum items held in Short-Term Memory before overflow.
            consolidation_batch_size: Number of turns between consolidation passes.
            context_strategy: Context window strategy (defaults to SlidingWindowStrategy).
            relevance_threshold: IS_REL threshold for Self-RAG verifier.
            support_threshold: IS_SUP threshold for Self-RAG verifier.
            enable_rag: If True, AgenticRAGOrchestrator is wired into context building.
        """
        # ── Memory Subsystems ────────────────────────────────────────
        self.episodic = EpisodicMemory()
        self.semantic = SemanticMemory()
        self.scratchpad = Scratchpad()

        # ── Router and Consolidation Engine ──────────────────────────
        self.router = PromoteOrDropRouter(episodic_memory=self.episodic)
        self.consolidation_engine = SemanticConsolidationEngine(
            episodic_memory=self.episodic,
            semantic_memory=self.semantic,
        )

        self.consolidation_batch_size = consolidation_batch_size
        self._turn_count = 0

        # ── Short-Term Memory with overflow callback ──────────────────
        self.short_term = ShortTermMemory(capacity=stm_capacity)
        self.short_term.set_overflow_callback(self._handle_memory_overflow)

        # ── Context Window Strategy ───────────────────────────────────
        self.context_strategy: BaseContextStrategy = (
            context_strategy or SlidingWindowStrategy(default_turn_window=10)
        )

        # ── Self-RAG Verifier ─────────────────────────────────────────
        self.verifier = SelfRAGVerifier(
            relevance_threshold=relevance_threshold,
            support_threshold=support_threshold,
        )

        # ── Agentic RAG Orchestrator (lazy-init to avoid import cost) ──
        self._enable_rag = enable_rag
        self._rag_orchestrator = None

    # ─────────────────────────────────────────────────────────────────
    # RAG Orchestrator (lazy initialization)
    # ─────────────────────────────────────────────────────────────────

    @property
    def rag_orchestrator(self):
        """Lazy-initialize the AgenticRAGOrchestrator."""
        if self._rag_orchestrator is None and self._enable_rag:
            from rag.agentic_rag import AgenticRAGOrchestrator
            self._rag_orchestrator = AgenticRAGOrchestrator(
                verifier=self.verifier,
                top_k=5,
                max_retry_attempts=1,
            )
        return self._rag_orchestrator

    # ─────────────────────────────────────────────────────────────────
    # STM Overflow Handler
    # ─────────────────────────────────────────────────────────────────

    def _handle_memory_overflow(self, overflow_items: List[ShortTermMemoryItem]) -> None:
        """Callback triggered automatically when Short-Term Memory hits capacity.

        Routes evicted items directly to the Promote-or-Drop Router, ensuring
        valuable context isn't lost when it falls out of the sliding window.
        """
        self.router.handle_overflow(overflow_items)

    # ─────────────────────────────────────────────────────────────────
    # Core Message Interface
    # ─────────────────────────────────────────────────────────────────

    def receive_message(
        self,
        content: str,
        role: str = "user",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Simulate the agent receiving or generating a message in a conversation turn."""
        if role == "user":
            self.short_term.add_user_message(content, metadata)
        elif role == "assistant":
            self.short_term.add_assistant_message(content, metadata=metadata)
        elif role == "tool":
            item = ShortTermMemoryItem(role=role, content=content, metadata=metadata or {})
            self.short_term.add_item(item)

        self._turn_count += 1

        # Periodically trigger consolidation of episodic events into semantic facts
        if self._turn_count % self.consolidation_batch_size == 0:
            self._trigger_consolidation()

    # ─────────────────────────────────────────────────────────────────
    # Context Window Building
    # ─────────────────────────────────────────────────────────────────

    def build_context(
        self,
        max_tokens: int = 3000,
        query: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Build the formatted context window for the next LLM call.

        Steps:
        1. Pull recent messages from Short-Term Memory.
        2. Apply context window strategy (Sliding Window / Masking / etc.).
        3. Optionally prepend RAG-retrieved knowledge as a system message.
        4. Inject active Scratchpad state.

        Args:
            max_tokens: Hard token budget for the context window.
            query: Optional query for RAG enrichment (uses last user message if None).

        Returns:
            List of message dicts ready to be sent to the LLM.
        """
        # 1. Pull raw messages from STM
        raw_messages = [
            {"role": item.role, "content": item.content}
            for item in self.short_term.get_history()
        ]

        # 2. Apply context window strategy
        formatted_messages, _metrics = self.context_strategy.format_context(
            messages=raw_messages,
            max_tokens=max_tokens,
            scratchpad=self.scratchpad if self.scratchpad.goal else None,
        )

        # 3. RAG enrichment (prepend as system message if results found)
        if self._enable_rag and self.rag_orchestrator is not None:
            rag_query = query or (
                next(
                    (m["content"] for m in reversed(raw_messages) if m.get("role") == "user"),
                    None,
                )
            )
            if rag_query:
                rag_result = self.rag_orchestrator.run(rag_query)
                if rag_result.relevant_chunks:
                    rag_system_msg = {
                        "role": "system",
                        "content": rag_result.answer_context,
                    }
                    formatted_messages.insert(0, rag_system_msg)

        return formatted_messages

    # ─────────────────────────────────────────────────────────────────
    # Self-RAG Verification
    # ─────────────────────────────────────────────────────────────────

    def verify_response(
        self,
        query: str,
        answer: str,
        recalled_memories: Optional[List[Any]] = None,
    ) -> VerificationResult:
        """Run Self-RAG verification on a candidate agent response.

        Checks:
        - IS_REL: Are the recalled memories relevant to the query?
        - IS_SUP: Is the answer grounded in the recalled memories?

        Args:
            query: The user query the answer is responding to.
            answer: The candidate LLM-generated answer to verify.
            recalled_memories: Context items to check grounding against.
                               If None, uses active semantic facts.

        Returns:
            VerificationResult with relevance and support scores.
        """
        if recalled_memories is None:
            recalled_memories = [
                f"{f.subject} {f.predicate}: {f.value}"
                for f in self.semantic.get_all_active_facts()
            ]

        return self.verifier.verify_memory_recall(
            query=query,
            answer=answer,
            recalled_memories=recalled_memories,
        )

    # ─────────────────────────────────────────────────────────────────
    # Background Consolidation
    # ─────────────────────────────────────────────────────────────────

    def _trigger_consolidation(self) -> None:
        """Periodically run the semantic consolidation engine in the background."""
        result = self.consolidation_engine.run_consolidation()
        if result.processed_event_ids:
            print(
                f"[AGENT BACKGROUND TASK] Consolidation complete. "
                f"Processed {len(result.processed_event_ids)} events, "
                f"Created {result.created_facts_count} facts, "
                f"Superseded {result.updated_facts_count} facts, "
                f"Contradictions {result.contradictions_count}"
            )


if __name__ == "__main__":
    # Smoke test for the agent integration wiring
    print("Initializing MemoryEnabledAgent...")
    agent = MemoryEnabledAgent(stm_capacity=3, consolidation_batch_size=5)

    print("\nSimulating conversation (STM Capacity = 3)...")
    messages = [
        ("user", "My manager is Mona Farid. I work at Branch 1."),
        ("assistant", "Noted. I've updated your preferences."),
        ("user", "We use Apex Fresh Logistics for emergency produce."),
        ("assistant", "Understood. Apex Fresh Logistics is your preferred supplier."),
        ("tool", '{"status": "success", "supplier_id": "APX-9982"}'),
        ("user", "Wait, actually corporate just mandated GreenRoute Wholesale instead."),
        ("assistant", "I will update the branch preferences to GreenRoute Wholesale."),
    ]

    for role, content in messages:
        print(f" -> Adding {role.upper()} message...")
        agent.receive_message(content, role=role)

    # Test Self-RAG verification
    query = "What is Branch 1's preferred emergency produce supplier?"
    answer = "Branch 1 uses GreenRoute Wholesale for emergency produce."
    verification = agent.verify_response(query, answer)
    print(f"\nSelf-RAG Verification: grounded={verification.is_supported}, "
          f"support_score={verification.support_score:.2f}")

    print("\nAgent memory subsystems after conversation:")
    print(f"STM Buffer Size: {agent.short_term.size}")
    print(f"STM Overflow Count: {agent.short_term.total_overflow_count}")
    print(f"Episodic Events: {agent.episodic.total_count}")
    print(f"Active Semantic Facts: {len(agent.semantic.get_all_active_facts())}")
