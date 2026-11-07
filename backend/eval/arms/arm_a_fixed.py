"""Arm A: fixed checks and a due-date reminder; no customer memory."""

from __future__ import annotations

from sim.world import SimulationWorld

from .common import EvaluationArm


class ArmAPolicy(EvaluationArm):
    """Fixed baseline with only invoice-level checks and due-date timing."""

    arm = "A"
    name = "Fixed rules, no memory"

    @classmethod
    def from_world(cls, world: SimulationWorld) -> "ArmAPolicy":
        """Create a policy independent of customer profile fields."""
        return cls()

