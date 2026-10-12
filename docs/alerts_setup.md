# Alerts setup

The dashboard has an opt-in browser sound toggle. When enabled by an operator, it plays a short tone for each newly recorded model-generated incident while the dashboard is open and able to play audio. Browser audio can be muted, throttled, or unavailable and must not be relied on as a safety alarm.

SMS/remote notifications are not implemented. The incident list only records WARNING/EMERGENCY predictions from a schema-compatible Random Forest artifact after configurable temporal confirmation/hysteresis. Since no such artifact or temporal training labels are supplied, the list should normally remain empty. Do not interpret detector boxes as alerts. Remote notification still needs provider integration, secret handling, delivery-state logging, cooldowns, and a human-response protocol before use.
