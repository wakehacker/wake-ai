"""Donation attack detector workflow."""

from typing import Dict, Any, Optional, Union
from pathlib import Path

from wake_ai import workflow
from wake_ai.templates.simple_detector import SimpleDetector


@workflow.command(name="donation-attack")
def factory():
    """Run donation attack detector."""
    return DonationAttackDetector()


class DonationAttackDetector(SimpleDetector):
    """Detector for donation attack vulnerabilities."""

    def get_detector_prompt(self) -> str:
        """Get the donation attack detection prompt."""


        prompt = """# Donation Attack Security Analysis

1. **Identify use of `address(this).balance` or `balanceOf(address(this))`**
   - Scan for use of `.balance` or `balanceOf()` that uses `this` as the target address
   - Identify logic associated with the returned value of token balances
   - Identify what functions are expected to naturally receive tokens

2. **Analyze possible donation attack vectors**
   - Analyze possible attack vectors associated with direct token transfers without the use of contract functions that would normally be used
   - Report any logical errors and vulnerabilities that may be caused by discrepancies between the amount of tokens received through contract functions and the amount of tokens received through direct token transfers

Only report objective security vulnerabilities. Do not report any issues if the implementation meets established security best practices and does not violate known standards or introduce exploitable conditions.
"""

        return prompt
