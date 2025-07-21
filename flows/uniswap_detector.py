"""Uniswap-specific vulnerability detector workflow."""

from typing import Dict, Any, Optional, Union
from pathlib import Path

from wake_ai.templates.markdown_detector import MarkdownDetector


class UniswapDetector(MarkdownDetector):
    """Detector for Uniswap V2/V3 specific vulnerabilities and best practices."""
    
    name = "uniswap"
    
    def __init__(
        self,
        focus_version: str = "both",  # "v2", "v3", or "both"
        check_oracle_manipulation: bool = True,
        check_sandwich_protection: bool = True,
        session: Optional[Any] = None,
        model: Optional[str] = None,
        working_dir: Optional[Union[str, Path]] = None,
        execution_dir: Optional[Union[str, Path]] = None,
        **kwargs
    ):
        """Initialize Uniswap detector.
        
        Args:
            focus_version: Which Uniswap version to focus on ("v2", "v3", or "both")
            check_oracle_manipulation: Whether to check for price oracle manipulation vulnerabilities
            check_sandwich_protection: Whether to check for sandwich attack protections
        """
        self.focus_version = focus_version
        self.check_oracle_manipulation = check_oracle_manipulation
        self.check_sandwich_protection = check_sandwich_protection
        
        super().__init__(
            name=self.name,
            session=session,
            model=model,
            working_dir=working_dir,
            execution_dir=execution_dir,
            **kwargs
        )
    
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

<task>
Perform comprehensive security analysis of Uniswap protocol integrations, identifying vulnerabilities specific to V2/V3 implementations
</task>

<context>
{version_context}
This detector identifies vulnerabilities in contracts that integrate with Uniswap, including DEX aggregators, yield farms, lending protocols, and other DeFi applications.
</context>

<working_dir>
Work in the assigned directory `{{working_dir}}` to store analysis results.
</working_dir>

<steps>

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

</steps>

<validation_requirements>

**Technical Evidence Standard**:
- Every finding must reference specific Uniswap functions being called
- Include exact parameter values that could lead to exploitation
- Provide concrete scenarios showing how Uniswap integration fails

**Severity Classification**:
- **Critical**: Direct loss of funds through Uniswap manipulation
- **High**: Price manipulation leading to unfair trades or liquidations
- **Medium**: Suboptimal integration causing user losses
- **Low**: Best practice violations with minimal impact

**Common False Positives to Avoid**:
- Deadline parameters in test files
- Slippage settings in example code
- Router addresses in deployment scripts
- Mock Uniswap contracts in test suites

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
    
    metadata:
      uniswap_version: "v2"
      pattern_type: "missing_slippage_protection"
      mev_vulnerable: true
```
</output_format>"""
        
        return prompt
    
    @classmethod
    def get_cli_options(cls) -> Dict[str, Any]:
        """Return CLI options for Uniswap detector."""
        import click
        return {
            "version": {
                "param_decls": ["--version", "-v"],
                "type": click.Choice(["v2", "v3", "both"]),
                "default": "both",
                "help": "Uniswap version to focus on"
            },
            "no_oracle_check": {
                "param_decls": ["--no-oracle-check"],
                "is_flag": True,
                "help": "Skip price oracle manipulation checks"
            },
            "no_sandwich_check": {
                "param_decls": ["--no-sandwich-check"],
                "is_flag": True,
                "help": "Skip sandwich attack protection checks"
            }
        }
    
    @classmethod
    def process_cli_args(cls, **kwargs) -> Dict[str, Any]:
        """Process CLI arguments for Uniswap detector."""
        return {
            "focus_version": kwargs.get("version", "both"),
            "check_oracle_manipulation": not kwargs.get("no_oracle_check", False),
            "check_sandwich_protection": not kwargs.get("no_sandwich_check", False)
        }