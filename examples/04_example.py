"""
Example 4: Integration Template

Template for building custom integration workflows.
"""

import asyncio
from helix_integration import HelixEcosystem

async def main():
    ecosystem = HelixEcosystem()
    await ecosystem.initialize()
    
    # Your integration code here
    
    await ecosystem.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
