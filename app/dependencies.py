# Backward-compatibility shim.
# All logic has been moved to app/services/.
# Routers that import from app.dependencies will continue to work unchanged.
# New code should import directly from the relevant service module.

from app.services.api_keys import get_active_api_key, use_api_key          # noqa: F401
from app.services.arbitrage import detect_arbitrage, calculate_potential_return  # noqa: F401
from app.services.settlement import settle_bet                              # noqa: F401
