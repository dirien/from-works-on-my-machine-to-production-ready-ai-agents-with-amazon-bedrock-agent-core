# tools.py
from strands import tool

# Mock Database
USER_DB = {
    "user_123": {
        "name": "John Doe",
        "home_location": "London, UK",
        "last_transaction": {"time": "09:00", "location": "London, UK"},
        "status": "ACTIVE"
    }
}


@tool
def get_user_profile(user_id: str) -> dict:
    """Retrieves user details and account status.

    Args:
        user_id: The unique identifier for the user (e.g., 'user_123')

    Returns:
        User profile including name, home location, last transaction, and status.
    """
    return USER_DB.get(user_id, {"error": "User not found"})


@tool
def get_recent_transactions(user_id: str) -> dict:
    """Fetches the last known transaction for the user.

    Args:
        user_id: The unique identifier for the user (e.g., 'user_123')

    Returns:
        The most recent transaction with time and location details.
    """
    user = USER_DB.get(user_id)
    if user:
        return user["last_transaction"]
    return {"error": "No history found"}


@tool
def block_credit_card(user_id: str, reason: str) -> dict:
    """Blocks the user's credit card and logs the reason.

    Use this tool when fraud is detected to immediately protect the user's account.

    Args:
        user_id: The unique identifier for the user whose card should be blocked
        reason: A detailed explanation of why the card is being blocked

    Returns:
        Confirmation of the block action with a ticket ID for tracking.
    """
    print(f"\n[ACTION] BLOCKING CARD for {user_id}. REASON: {reason}")
    return {"status": "BLOCKED", "ticket_id": "TICKET-999"}
