"""Donation attack detector workflow."""

from typing import Dict, Any, Optional, Union
from pathlib import Path

from wake_ai import workflow
from wake_ai.templates.simple_detector import SimpleDetector


class DonationAttackDetector(SimpleDetector):
    """Detector for donation attack vulnerabilities."""

    @workflow.command(name="donation-attack")
    def cli(self):
        """Run donation attack detector."""
        pass

    def get_detector_prompt(self) -> str:
        """Get the donation attack detection prompt."""


        prompt = """# Donation Attack Security Analysis

<task>
Perform comprehensive security analysis identifying donation attack vulnerabilities.
</task>

<context>
This detector identifies vulnerabilities in contracts that use `address(this).balance` or `balanceOf(address(this))` instead of tracking the balances of tokens sent to the contracts in state variables.
</context>

<working_dir>
Work in the assigned directory `{{working_dir}}` to store analysis results.
</working_dir>

<steps>

1. **Identify use of `address(this).balance` or `balanceOf(address(this))`**
   - Scan for use of `.balance` or `balanceOf()` that uses `this` as the target address
   - Identify logic associated with the returned value of token balances
   - Identify what functions are expected to naturally receive tokens

2. **Analyze possible donation attack vectors**
   - Analyze possible attack vectors associated with direct token transfers without the use of contract functions that would normally be used
   - Report any logical errors and vulnerabilities that may be caused by discrepancies between the amount of tokens received through contract functions and the amount of tokens received through direct token transfers
</steps>

<validation_requirements>

**Technical Evidence Standard**:
- Every finding must reference specific use of `.balance` or `balanceOf()` functions
- Provide concrete scenarios showing how donation attacks can be performed
- Include what advantages the attacker gains from the donation attack

**Severity Classification**:
- **Critical**: Direct loss of funds, denial of service of core protocol functionality
- **High**: Manipulation of key protocol parameters possibly leading to loss of funds, denial of service of non-core protocol functionality
- **Medium**: Logical errors and protocol misbehaviors that do not lead to loss of funds
- **Low**: Best practice violations with minimal impact

Only report objective security vulnerabilities. Do not report any issues if the implementation meets established security best practices and does not violate known standards or introduce exploitable conditions.
</validation_requirements>

<output_format>
Create results.yaml with findings following this structure:

```yaml
detections:
  - title: "Missing slippage protection in Uniswap V2 swap"
    severity: "high"
    type: "vulnerability"
    description: |
      The swapExactTokensForTokens call in the protocol's swap function does not implement
      slippage protection, setting amountOutMin to 0. This allows MEV bots to sandwich
      attack users, extracting value through front-running and back-running.

      The vulnerability occurs in the DexAggregator contract when routing through Uniswap V2.

    location:
      target: "DexAggregator.swapTokens"
      file: "contracts/DexAggregator.sol"
      start_line: 125
      end_line: 135
      snippet: |
        function swapTokens(address tokenIn, address tokenOut, uint256 amountIn) external {
            IERC20(tokenIn).transferFrom(msg.sender, address(this), amountIn);
            IERC20(tokenIn).approve(UNISWAP_V2_ROUTER, amountIn);

            address[] memory path = new address[](2);
            path[0] = tokenIn;
            path[1] = tokenOut;

            // VULNERABLE: amountOutMin set to 0
            IUniswapV2Router02(UNISWAP_V2_ROUTER).swapExactTokensForTokens(
                amountIn,
                0, // No slippage protection!
                path,
                msg.sender,
                block.timestamp + 300
            );
        }

    recommendation: |
      Implement proper slippage protection by calculating minimum output amount:

      ```solidity
      // Add slippage parameter (e.g., 50 = 0.5%)
      function swapTokens(
          address tokenIn,
          address tokenOut,
          uint256 amountIn,
          uint256 slippageBps
      ) external {
          // ... existing code ...

          // Calculate expected output
          uint256[] memory amounts = IUniswapV2Router02(UNISWAP_V2_ROUTER)
              .getAmountsOut(amountIn, path);
          uint256 amountOutMin = amounts[1] * (10000 - slippageBps) / 10000;

          IUniswapV2Router02(UNISWAP_V2_ROUTER).swapExactTokensForTokens(
              amountIn,
              amountOutMin, // Protected against slippage
              path,
              msg.sender,
              block.timestamp + 300
          );
      }
      ```
```
</output_format>"""

        return prompt
