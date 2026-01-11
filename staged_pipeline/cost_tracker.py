"""
Cost Tracker Module

Tracks API usage and costs across staged pipeline calls.
Thread-safe for async/parallel processing.
"""

from dataclasses import dataclass, field
from typing import Optional
import threading


# Pricing per 1M tokens (update as needed)
PRICING = {
    "gemini-3-pro-preview": {
        "input": 2.00,    # $2.00 per 1M input tokens (<=200k context)
        "output": 12.00,  # $12.00 per 1M output tokens (<=200k context)
    },
    "gemini-3-flash-preview": {
        "input": 0.10,    # $0.10 per 1M input tokens
        "output": 0.40,   # $0.40 per 1M output tokens
    },
    "gemini-2.5-flash-preview-05-20": {
        "input": 0.15,
        "output": 0.60,
    },
    "gemini-2.5-pro-preview-05-06": {
        "input": 1.25,
        "output": 10.00,
    },
    "gemini-2.0-flash": {
        "input": 0.10,
        "output": 0.40,
    },
    # Add more models as needed
    "default": {
        "input": 0.15,
        "output": 0.60,
    }
}


@dataclass
class APICall:
    """Record of a single API call."""
    stage: str
    model: str
    input_tokens: int
    output_tokens: int
    duration_ms: float
    cost: float


@dataclass
class CostTracker:
    """Track API usage and costs across pipeline stages.
    
    Thread-safe: Uses a reentrant lock to protect concurrent access during async processing.
    """
    
    calls: list[APICall] = field(default_factory=list)
    
    # Totals
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    total_duration_ms: float = 0.0
    
    # Thread safety lock (RLock allows nested locking from same thread)
    _lock: threading.RLock = field(default_factory=threading.RLock)
    
    def add_call(
        self,
        stage: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        duration_ms: float
    ):
        """Record an API call (thread-safe)."""
        # Calculate cost
        pricing = PRICING.get(model, PRICING["default"])
        cost_input = (input_tokens / 1_000_000) * pricing["input"]
        cost_output = (output_tokens / 1_000_000) * pricing["output"]
        cost = cost_input + cost_output
        
        # Create call record
        call = APICall(
            stage=stage,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_ms=duration_ms,
            cost=cost
        )
        
        # Thread-safe update
        with self._lock:
            self.calls.append(call)
            
            # Update totals
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.total_tokens += input_tokens + output_tokens
            self.total_cost += cost
            self.total_duration_ms += duration_ms
    
    def get_stage_summary(self) -> dict[str, dict]:
        """Get cost breakdown by stage (thread-safe)."""
        with self._lock:
            summary = {}
            for call in self.calls:
                if call.stage not in summary:
                    summary[call.stage] = {
                        "calls": 0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "cost": 0.0,
                        "duration_ms": 0.0
                    }
                summary[call.stage]["calls"] += 1
                summary[call.stage]["input_tokens"] += call.input_tokens
                summary[call.stage]["output_tokens"] += call.output_tokens
                summary[call.stage]["cost"] += call.cost
                summary[call.stage]["duration_ms"] += call.duration_ms
            return summary
    
    def format_summary(self) -> str:
        """Format a human-readable summary."""
        lines = []
        lines.append("┌─────────────────────────────────────────────────────┐")
        lines.append("│                   COST SUMMARY                      │")
        lines.append("├─────────────────────────────────────────────────────┤")
        
        stage_summary = self.get_stage_summary()
        for stage, data in stage_summary.items():
            lines.append(f"│ {stage:<20} ${data['cost']:.4f} ({data['input_tokens']:,}+{data['output_tokens']:,} tokens)")
        
        lines.append("├─────────────────────────────────────────────────────┤")
        lines.append(f"│ TOTAL: ${self.total_cost:.4f}  ({self.total_tokens:,} tokens)")
        lines.append(f"│ Time:  {self.total_duration_ms/1000:.1f}s")
        lines.append("└─────────────────────────────────────────────────────┘")
        
        return "\n".join(lines)
    
    def to_dict(self) -> dict:
        """Export as dictionary for JSON serialization (thread-safe)."""
        with self._lock:
            return {
                "total_input_tokens": self.total_input_tokens,
                "total_output_tokens": self.total_output_tokens,
                "total_tokens": self.total_tokens,
                "total_cost_usd": round(self.total_cost, 6),
                "total_duration_ms": round(self.total_duration_ms, 2),
                "stages": self.get_stage_summary(),
                "calls": [
                    {
                        "stage": c.stage,
                        "model": c.model,
                        "input_tokens": c.input_tokens,
                        "output_tokens": c.output_tokens,
                        "cost_usd": round(c.cost, 6),
                        "duration_ms": round(c.duration_ms, 2)
                    }
                    for c in self.calls
                ]
            }


# Global tracker instance
_global_tracker: Optional[CostTracker] = None


def get_tracker() -> CostTracker:
    """Get or create the global cost tracker."""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = CostTracker()
    return _global_tracker


def reset_tracker():
    """Reset the global cost tracker."""
    global _global_tracker
    _global_tracker = CostTracker()


def extract_usage_from_response(response) -> tuple[int, int]:
    """Extract token usage from a Gemini response."""
    try:
        # Try to get usage metadata from response
        if hasattr(response, 'usage_metadata'):
            usage = response.usage_metadata
            return (
                getattr(usage, 'prompt_token_count', 0),
                getattr(usage, 'candidates_token_count', 0)
            )
    except Exception:
        pass
    
    # Fallback: estimate from text length
    # Rough estimate: 1 token ≈ 4 characters
    input_estimate = 5000  # Assume ~5k for prompt + image
    output_estimate = len(response.text) // 4 if hasattr(response, 'text') else 1000
    
    return (input_estimate, output_estimate)
