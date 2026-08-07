"""Agent Memory Integration Module.

This module provides the core `MemoryEnabledAgent` which wires together all components
of the memory subsystem as required by the Copperleaf Kitchens Architecture:
1. Short-Term Memory is initialized with an overflow callback.
2. The overflow callback directly routes evicted items to the Promote-or-Drop Router.
3. The Consolidation Engine is called periodically to convert episodic events into semantic facts.
"""

from typing import Any, List, Optional

from memory.consolidation import SemanticConsolidationEngine
from memory.episodic import EpisodicMemory
from memory.router import PromoteOrDropRouter
from memory.semantic import SemanticMemory
from memory.short_term import ShortTermMemory, ShortTermMemoryItem


class MemoryEnabledAgent:
    """An AI Agent that seamlessly integrates all levels of the Memory Architecture."""

    def __init__(self, stm_capacity: int = 10, consolidation_batch_size: int = 5) -> None:
        """Initialize the agent with its memory subsystems."""
        self.episodic = EpisodicMemory()
        self.semantic = SemanticMemory()
        
        # Initialize Router and Consolidation Engine
        self.router = PromoteOrDropRouter(episodic_memory=self.episodic)
        self.consolidation_engine = SemanticConsolidationEngine(
            episodic_memory=self.episodic,
            semantic_memory=self.semantic
        )

        self.consolidation_batch_size = consolidation_batch_size
        self._turn_count = 0

        # Initialize Short-Term Memory and WIRE the overflow callback to the Router
        self.short_term = ShortTermMemory(capacity=stm_capacity)
        self.short_term.set_overflow_callback(self._handle_memory_overflow)

    def _handle_memory_overflow(self, overflow_items: List[ShortTermMemoryItem]) -> None:
        """Callback triggered automatically when Short-Term Memory hits capacity.

        This routes evicted items directly to the Promote-or-Drop Router, ensuring
        valuable context isn't lost when it falls out of the sliding window.
        """
        self.router.handle_overflow(overflow_items)

    def receive_message(self, content: str, role: str = "user", metadata: Optional[dict[str, Any]] = None) -> None:
        """Simulate the agent receiving or generating a message in a conversation turn."""
        if role == "user":
            self.short_term.add_user_message(content, metadata)
        elif role == "assistant":
            self.short_term.add_assistant_message(content, metadata=metadata)
        elif role == "tool":
            # For tool observations, we add an item manually
            item = ShortTermMemoryItem(role=role, content=content, metadata=metadata or {})
            self.short_term.add_item(item)
            
        self._turn_count += 1

        # Periodically trigger consolidation of episodic events into semantic facts
        if self._turn_count % self.consolidation_batch_size == 0:
            self._trigger_consolidation()

    def _trigger_consolidation(self) -> None:
        """Periodically run the semantic consolidation engine in the background."""
        result = self.consolidation_engine.run_consolidation()
        if result.processed_event_ids:
            print(f"[AGENT BACKGROUND TASK] Consolidation complete. "
                  f"Processed {len(result.processed_event_ids)} events, "
                  f"Created {result.created_facts_count} facts, "
                  f"Superseded {result.updated_facts_count} facts, "
                  f"Contradictions {result.contradictions_count}")


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

    print("\nAgent memory subsystems after conversation:")
    print(f"STM Buffer Size: {agent.short_term.size}")
    print(f"STM Overflow Count: {agent.short_term.total_overflow_count}")
    print(f"Episodic Events: {agent.episodic.total_count}")
    print(f"Active Semantic Facts: {len(agent.semantic.get_all_active_facts())}")
