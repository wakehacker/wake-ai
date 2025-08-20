"""Uniswap-specific vulnerability detector workflow."""

from typing import Dict, Any, Optional, Union
from pathlib import Path

from wake_ai import workflow
from wake_ai.templates.simple_detector import SimpleDetector

import rich_click as click


@workflow.command(name="uniswap")
@click.option("--focus-version", "-f", type=click.Choice(["v2", "v3", "both"]), default="both", help="Uniswap version to focus on")
@click.option("--no-oracle-check", is_flag=True, help="Skip price oracle manipulation checks")
@click.option("--no-sandwich-check", is_flag=True, help="Skip sandwich attack protection checks")
def factory(focus_version: str, no_oracle_check: bool, no_sandwich_check: bool):
    """Run Uniswap integration detector."""
    detector = UniswapDetector()
    detector.focus_version = focus_version
    detector.check_oracle_manipulation = not no_oracle_check
    detector.check_sandwich_protection = not no_sandwich_check
    return detector


class UniswapDetector(SimpleDetector):
    """Detector for Uniswap V2/V3 specific vulnerabilities and best practices."""

    focus_version: str
    check_oracle_manipulation: bool
    check_sandwich_protection: bool

    def get_detector_prompt(self) -> str:
        """Get the Uniswap-specific detection prompt."""
        version_context = ""
        if self.focus_version == "v2":
            version_context = "Focus specifically on Uniswap V2 patterns and interfaces."
        elif self.focus_version == "v3":
            version_context = "Focus specifically on Uniswap V3 patterns including concentrated liquidity."
        else:
            version_context = "Check for both Uniswap V2 and V3 patterns."

        prompt = f"""# Uniswap Integration Security Analysis

This detector identifies vulnerabilities in contracts that integrate with Uniswap, including DEX aggregators, yield farms, lending protocols, and other DeFi applications.
{version_context}

1. **Initialize and identify Uniswap integrations**
   - Scan for Uniswap interface imports (IUniswapV2*, IUniswapV3*)
   - Identify router, factory, and pair/pool interactions
   - Map out which Uniswap version(s) are being used
   - Note any custom implementations of Uniswap functionality

2. **Core integration vulnerability analysis**

   a) **Reserve and token ordering issues**
      - Verify correct token0/token1 ordering in all operations
      - Check getReserves() usage matches token order
      - Validate sqrt price calculations for V3
      - Ensure consistent token ordering across the protocol

   b) **Slippage and deadline protection**
      - Verify all swaps implement slippage protection
      - Check that amountOutMin is properly calculated
      - Ensure deadlines are not set too far in future (max ~20 minutes)
      - Validate slippage parameters cannot be manipulated by attackers

3. **Liquidity provider vulnerabilities**

   a) **LP token manipulation**
      - Check for first depositor inflation attacks
      - Verify proper handling of LP token minting/burning
      - Analyze rounding in liquidity calculations
      - Test edge cases with very small/large liquidity amounts

   b) **Impermanent loss considerations**
      - Verify protocols account for IL in their calculations
      - Check for proper LP share valuation methods
"""

        if self.check_oracle_manipulation:
            prompt += """
4. **Price oracle security analysis**

   a) **TWAP implementation review**
      - Verify TWAP window is sufficient (minimum 10-30 minutes)
      - Check for single-block price manipulation vulnerabilities
      - Analyze oracle update mechanisms and frequency
      - Ensure cumulative price variables are properly tracked

   b) **Oracle manipulation vectors**
      - Test for flash loan price manipulation
      - Check for sandwich attack vulnerabilities
      - Verify price bounds and sanity checks
      - Analyze multi-hop price calculations
"""

        prompt += """
5. **Flash loan and callback security**

   a) **Callback function protection**
      - Verify uniswapV2Call has proper access controls
      - Check uniswapV3FlashCallback sender validation
      - Ensure callbacks cannot be called directly
      - Validate flash loan fee calculations

   b) **Reentrancy analysis**
      - Check for reentrancy in flash loan logic
      - Verify state changes follow CEI pattern
      - Test cross-function reentrancy scenarios
      - Analyze external call sequences

6. **Protocol-specific vulnerability patterns**
"""

        if self.focus_version in ["v3", "both"]:
            prompt += """
   a) **Uniswap V3 specific issues**
      - Verify tick math calculations and boundaries
      - Check for liquidity range manipulation
      - Validate NFT position manager interactions
      - Ensure proper handling of concentrated liquidity
      - Test edge cases at tick boundaries
"""

        if self.check_sandwich_protection:
            prompt += """
   b) **MEV and sandwich protection**
      - Identify transactions vulnerable to sandwiching
      - Check for commit-reveal patterns where needed
      - Analyze slippage tolerance settings
      - Verify private mempool usage for sensitive operations
"""

        prompt += """
7. **Integration best practices audit**

   a) **Address and configuration management**
      - Check for hardcoded addresses (router, factory)
      - Verify addresses are configurable or use registry
      - Ensure multi-chain compatibility considerations

   b) **Error handling and validation**
      - Verify all external calls check return values
      - Analyze revert reasons and error messages
      - Check for proper event emissions
      - Validate input parameters thoroughly

**Common False Positives to Avoid**:
- Deadline parameters in test files
- Slippage settings in example code
- Router addresses in deployment scripts
- Mock Uniswap contracts in test suites

Only report objective security vulnerabilities. Do not report any issues if the implementation meets established security best practices and does not violate known standards or introduce exploitable conditions.
"""

        return prompt
