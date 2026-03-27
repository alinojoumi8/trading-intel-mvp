import asyncio
from app.services.llm_service import generate

async def test():
    prompt = """Classify the current market regime using the following data:

Index: S&P 500
Current Price: 6556
Previous Business Cycle High: 4796
Bear Market Level (x0.80): 3837
Bull Market Confirmation Level: 4796
VIX Current: 27.0
VIX 30 Days Ago: 17.4
VIX % Change (30d): 55.5%

Return ONLY this JSON: {"market_regime": "...", "volatility_regime": "...", "trading_mode": "...", "position_size_modifier": ..., "regime_reasoning": "...", "vix_signal": "..."}"""

    result = await generate(
        prompt=prompt,
        system_prompt="You are a professional macro trader. Answer ONLY with JSON.",
        temperature=0.0,
        max_tokens=1000
    )
    print("Stage 1 result:", repr(result[:500]))

asyncio.run(test())
