"""
DrowsiGuard — System State Machine
Backbone of system operation: BOOTING -> IDLE -> VERIFYING_DRIVER -> RUNNING etc.
All state transitions are logged. Side effects are dispatched per transition.
"""
import time
from utils.logger import get_logger

logger = get_logger("state_machine")


class State:
    BOOTING = "BOOTING"
    IDLE = "IDLE"
    VERIFYING_DRIVER = "VERIFYING_DRIVER"
    RUNNING = "RUNNING"
    MISMATCH_ALERT = "MISMATCH_ALERT"
    OFFLINE_DEGRADED = "OFFLINE_DEGRADED"
    UPDATING = "UPDATING"


# Valid transitions: from_state -> set of allowed to_states
VALID_TRANSITIONS = {
    State.BOOTING: {State.IDLE},
    State.IDLE: {State.VERIFYING_DRIVER, State.UPDATING, State.OFFLINE_DEGRADED},
    State.VERIFYING_DRIVER: {State.RUNNING, State.IDLE, State.MISMATCH_ALERT},
    State.RUNNING: {State.IDLE, State.MISMATCH_ALERT, State.OFFLINE_DEGRADED, State.UPDATING},
    State.MISMATCH_ALERT: {State.IDLE, State.RUNNING},
    State.OFFLINE_DEGRADED: {State.RUNNING, State.IDLE},
    State.UPDATING: {State.IDLE, State.RUNNING},
}


class StateMachine:
    """System state machine with logging and transition callbacks."""

    def __init__(self, on_transition=None):
        self._state = State.BOOTING
        self._on_transition = on_transition
        self._history = []
        self._last_change = time.time()
        logger.info(f"StateMachine initialized in {self._state}")

    @property
    def state(self) -> str:
        return self._state

    @property
    def time_in_state(self) -> float:
        return time.time() - self._last_change

    def transition(self, new_state: str, reason: str = "") -> bool:
        """Attempt state transition. Returns True if successful."""
        if new_state == self._state:
            return True

        allowed = VALID_TRANSITIONS.get(self._state, set())
        if new_state not in allowed:
            logger.error(
                f"INVALID transition: {self._state} -> {new_state} (reason: {reason}). "
                f"Allowed: {allowed}"
            )
            return False

        old = self._state
        self._state = new_state
        self._last_change = time.time()
        self._history.append((time.time(), old, new_state, reason))

        logger.info(f"State: {old} -> {new_state} (reason: {reason})")

        if self._on_transition:
            try:
                self._on_transition(old, new_state, reason)
            except Exception as e:
                logger.error(f"Transition callback error: {e}")

        return True

    @property
    def history(self) -> list:
        return list(self._history)
