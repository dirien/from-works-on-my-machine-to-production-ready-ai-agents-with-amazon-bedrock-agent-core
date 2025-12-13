# server.py - MCP Risk Scoring Server for Fraud Detection
"""
MCP Server providing risk scoring tools for fraud detection.
Deployed to AgentCore Runtime and accessed via AgentCore Gateway.

Tools:
- calculate_risk_score: Calculates fraud risk score based on transaction patterns
- get_fraud_indicators: Retrieves known fraud indicators for a user
- check_merchant_reputation: Checks merchant risk rating and fraud history
"""

from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server for stateless HTTP transport
# AgentCore Runtime MCP protocol expects endpoint at 0.0.0.0:8000/mcp
# Using exact configuration pattern from AWS documentation
mcp = FastMCP(
    host="0.0.0.0",
    stateless_http=True,
)

# =============================================================================
# Mock Database - Risk Profiles and Merchant Data
# =============================================================================

# User risk profiles (simulating a risk assessment database)
USER_RISK_PROFILES = {
    "user_123": {  # John Doe - has some fraud indicators
        "name": "John Doe",
        "risk_level": "medium",
        "indicators": ["velocity_alert_2024_03", "address_mismatch_flag"],
        "typical_amount_range": (50, 200),
        "typical_merchants": ["grocery", "restaurant", "transit"],
        "chargeback_count": 1,
        "account_age_days": 730,
    },
    "user_456": {  # Jane Smith - clean profile
        "name": "Jane Smith",
        "risk_level": "low",
        "indicators": [],
        "typical_amount_range": (100, 500),
        "typical_merchants": ["department_store", "restaurant", "online_shopping"],
        "chargeback_count": 0,
        "account_age_days": 1825,
    },
    "user_789": {  # Bob Wilson - velocity concerns
        "name": "Bob Wilson",
        "risk_level": "medium",
        "indicators": ["high_velocity_pattern", "multiple_devices"],
        "typical_amount_range": (200, 1000),
        "typical_merchants": ["electronics", "business_services", "hotel"],
        "chargeback_count": 2,
        "account_age_days": 365,
    },
    "user_321": {  # Alice Chen - new account, some flags
        "name": "Alice Chen",
        "risk_level": "medium",
        "indicators": ["new_account", "rapid_spending_increase"],
        "typical_amount_range": (50, 300),
        "typical_merchants": ["food_delivery", "retail", "entertainment"],
        "chargeback_count": 0,
        "account_age_days": 90,
    },
}

# Merchant reputation database
MERCHANT_REPUTATION = {
    # High-risk merchants
    "cryptoexchange123": {
        "name": "CryptoExchange123",
        "category": "cryptocurrency",
        "risk_rating": "HIGH",
        "fraud_reports": 47,
        "chargeback_rate": 0.15,
        "verified": False,
    },
    "quickcashadvance": {
        "name": "QuickCashAdvance",
        "category": "financial_services",
        "risk_rating": "HIGH",
        "fraud_reports": 89,
        "chargeback_rate": 0.22,
        "verified": False,
    },
    "luxuryoutlet_online": {
        "name": "LuxuryOutlet Online",
        "category": "retail",
        "risk_rating": "HIGH",
        "fraud_reports": 156,
        "chargeback_rate": 0.18,
        "verified": False,
    },
    # Medium-risk merchants
    "gaming_topup_store": {
        "name": "Gaming TopUp Store",
        "category": "digital_goods",
        "risk_rating": "MEDIUM",
        "fraud_reports": 12,
        "chargeback_rate": 0.05,
        "verified": True,
    },
    "overseas_electronics": {
        "name": "Overseas Electronics",
        "category": "electronics",
        "risk_rating": "MEDIUM",
        "fraud_reports": 8,
        "chargeback_rate": 0.04,
        "verified": True,
    },
    # Low-risk merchants (well-known)
    "amazon": {
        "name": "Amazon",
        "category": "retail",
        "risk_rating": "LOW",
        "fraud_reports": 2,
        "chargeback_rate": 0.001,
        "verified": True,
    },
    "whole_foods": {
        "name": "Whole Foods Market",
        "category": "grocery",
        "risk_rating": "LOW",
        "fraud_reports": 0,
        "chargeback_rate": 0.0005,
        "verified": True,
    },
    "starbucks": {
        "name": "Starbucks",
        "category": "food_beverage",
        "risk_rating": "LOW",
        "fraud_reports": 0,
        "chargeback_rate": 0.0003,
        "verified": True,
    },
    "hilton_hotels": {
        "name": "Hilton Hotels",
        "category": "hotel",
        "risk_rating": "LOW",
        "fraud_reports": 1,
        "chargeback_rate": 0.0008,
        "verified": True,
    },
}


def normalize_merchant_name(name: str) -> str:
    """Normalize merchant name for lookup."""
    return name.lower().replace(" ", "_").replace("-", "_")


def calculate_amount_anomaly_score(amount: float, typical_range: tuple) -> int:
    """Calculate anomaly score based on amount vs typical range."""
    min_typical, max_typical = typical_range

    if min_typical <= amount <= max_typical:
        return 0  # Normal
    elif amount < min_typical:
        # Below typical - slightly unusual but not high risk
        ratio = min_typical / max(amount, 1)
        return min(int(ratio * 5), 15)
    else:
        # Above typical - potentially risky
        ratio = amount / max_typical
        if ratio <= 1.5:
            return 10
        elif ratio <= 3:
            return 25
        elif ratio <= 5:
            return 40
        elif ratio <= 10:
            return 60
        else:
            return 80  # Very high anomaly


# =============================================================================
# MCP Tools
# =============================================================================

@mcp.tool()
def calculate_risk_score(user_id: str, amount: float, merchant: str, location: str) -> dict:
    """
    Calculate fraud risk score (0-100) based on transaction patterns.

    Analyzes the transaction against user's historical patterns, merchant risk,
    and amount anomalies to produce a comprehensive risk score.

    Args:
        user_id: The unique identifier for the user (e.g., 'user_123')
        amount: Transaction amount in USD
        merchant: Merchant name where transaction occurred
        location: Location of the transaction

    Returns:
        Dictionary with risk score (0-100), risk factors identified, and recommendation
    """
    factors = []
    score = 0

    # Get user profile
    user_profile = USER_RISK_PROFILES.get(user_id)
    if not user_profile:
        return {
            "score": 50,
            "factors": ["unknown_user"],
            "recommendation": "REVIEW",
            "details": "User not found in risk database - manual review recommended"
        }

    # Factor 1: Base risk from user profile
    base_risk = {"low": 5, "medium": 15, "high": 30}.get(user_profile["risk_level"], 10)
    score += base_risk
    if user_profile["risk_level"] != "low":
        factors.append(f"user_risk_level_{user_profile['risk_level']}")

    # Factor 2: Existing fraud indicators
    indicator_count = len(user_profile["indicators"])
    if indicator_count > 0:
        indicator_score = min(indicator_count * 8, 25)
        score += indicator_score
        factors.append(f"existing_indicators_{indicator_count}")

    # Factor 3: Amount anomaly
    amount_score = calculate_amount_anomaly_score(amount, user_profile["typical_amount_range"])
    if amount_score > 0:
        score += amount_score
        factors.append("amount_anomaly")

    # Factor 4: Merchant risk
    merchant_key = normalize_merchant_name(merchant)
    merchant_data = MERCHANT_REPUTATION.get(merchant_key)
    if merchant_data:
        merchant_risk = {"LOW": 0, "MEDIUM": 15, "HIGH": 35}.get(merchant_data["risk_rating"], 10)
        score += merchant_risk
        if merchant_data["risk_rating"] != "LOW":
            factors.append(f"merchant_risk_{merchant_data['risk_rating'].lower()}")
        if not merchant_data["verified"]:
            score += 10
            factors.append("unverified_merchant")
    else:
        # Unknown merchant
        score += 20
        factors.append("unknown_merchant")

    # Factor 5: Chargeback history
    if user_profile["chargeback_count"] > 0:
        chargeback_score = min(user_profile["chargeback_count"] * 10, 25)
        score += chargeback_score
        factors.append(f"chargeback_history_{user_profile['chargeback_count']}")

    # Factor 6: New account
    if user_profile["account_age_days"] < 180:
        score += 10
        factors.append("new_account")

    # Cap score at 100
    score = min(score, 100)

    # Determine recommendation
    if score < 30:
        recommendation = "APPROVE"
    elif score < 60:
        recommendation = "REVIEW"
    else:
        recommendation = "BLOCK"

    return {
        "score": score,
        "factors": factors,
        "recommendation": recommendation,
        "user_name": user_profile["name"],
        "details": f"Risk assessment for ${amount:.2f} at {merchant} in {location}"
    }


@mcp.tool()
def get_fraud_indicators(user_id: str) -> dict:
    """
    Get known fraud indicators and history for a user.

    Retrieves all fraud-related flags, alerts, and historical patterns
    associated with the user's account.

    Args:
        user_id: The unique identifier for the user (e.g., 'user_123')

    Returns:
        Dictionary with indicators list, overall risk level, and account details
    """
    user_profile = USER_RISK_PROFILES.get(user_id)

    if not user_profile:
        return {
            "user_id": user_id,
            "found": False,
            "indicators": [],
            "risk_level": "unknown",
            "message": "User not found in fraud indicator database"
        }

    # Build detailed indicator descriptions
    indicator_details = []
    for indicator in user_profile["indicators"]:
        if "velocity" in indicator:
            indicator_details.append({
                "code": indicator,
                "type": "velocity",
                "description": "High transaction velocity detected - multiple transactions in short timeframe",
                "severity": "medium"
            })
        elif "address" in indicator:
            indicator_details.append({
                "code": indicator,
                "type": "identity",
                "description": "Billing/shipping address mismatch detected",
                "severity": "low"
            })
        elif "device" in indicator:
            indicator_details.append({
                "code": indicator,
                "type": "device",
                "description": "Multiple devices used for account access",
                "severity": "medium"
            })
        elif "new_account" in indicator:
            indicator_details.append({
                "code": indicator,
                "type": "account_age",
                "description": "Account created recently - limited history",
                "severity": "low"
            })
        elif "spending" in indicator:
            indicator_details.append({
                "code": indicator,
                "type": "behavior",
                "description": "Rapid increase in spending patterns detected",
                "severity": "medium"
            })
        else:
            indicator_details.append({
                "code": indicator,
                "type": "other",
                "description": f"Fraud indicator: {indicator}",
                "severity": "medium"
            })

    return {
        "user_id": user_id,
        "user_name": user_profile["name"],
        "found": True,
        "risk_level": user_profile["risk_level"],
        "indicators": indicator_details,
        "indicator_count": len(indicator_details),
        "chargeback_history": {
            "count": user_profile["chargeback_count"],
            "risk_factor": "high" if user_profile["chargeback_count"] > 1 else "low"
        },
        "account_age_days": user_profile["account_age_days"],
        "typical_spending": f"${user_profile['typical_amount_range'][0]}-${user_profile['typical_amount_range'][1]}"
    }


@mcp.tool()
def check_merchant_reputation(merchant_name: str) -> dict:
    """
    Check merchant risk rating and fraud history.

    Queries the merchant reputation database to assess the risk level
    of transacting with a specific merchant.

    Args:
        merchant_name: Name of the merchant to check

    Returns:
        Dictionary with merchant details, risk rating, fraud reports, and verification status
    """
    merchant_key = normalize_merchant_name(merchant_name)
    merchant_data = MERCHANT_REPUTATION.get(merchant_key)

    if not merchant_data:
        return {
            "merchant_name": merchant_name,
            "found": False,
            "risk_rating": "UNKNOWN",
            "message": "Merchant not found in reputation database",
            "recommendation": "Proceed with caution - unknown merchant",
            "verified": False
        }

    # Build risk assessment
    risk_factors = []
    if merchant_data["risk_rating"] == "HIGH":
        risk_factors.append("High-risk merchant category")
    if merchant_data["fraud_reports"] > 20:
        risk_factors.append(f"Elevated fraud reports ({merchant_data['fraud_reports']})")
    if merchant_data["chargeback_rate"] > 0.05:
        risk_factors.append(f"High chargeback rate ({merchant_data['chargeback_rate']*100:.1f}%)")
    if not merchant_data["verified"]:
        risk_factors.append("Merchant not verified")

    # Determine recommendation
    if merchant_data["risk_rating"] == "LOW":
        recommendation = "Safe to proceed - trusted merchant"
    elif merchant_data["risk_rating"] == "MEDIUM":
        recommendation = "Proceed with standard verification"
    else:
        recommendation = "Additional verification strongly recommended"

    return {
        "merchant_name": merchant_data["name"],
        "found": True,
        "category": merchant_data["category"],
        "risk_rating": merchant_data["risk_rating"],
        "fraud_reports": merchant_data["fraud_reports"],
        "chargeback_rate": f"{merchant_data['chargeback_rate']*100:.2f}%",
        "verified": merchant_data["verified"],
        "risk_factors": risk_factors,
        "recommendation": recommendation
    }


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
