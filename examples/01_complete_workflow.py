"""
Example 1: Complete Workflow with Full Integration

Demonstrates end-to-end workflow execution with all components integrated.
"""

import asyncio
from helix_integration import HelixEcosystem

async def main():
    # Initialize ecosystem
    ecosystem = HelixEcosystem()
    await ecosystem.initialize()
    
    print("🚀 Helix Ecosystem Initialized")
    
    # Register agents
    await ecosystem.agent_manager.register_agent("orchestrator", "orchestrator", "inner_core")
    await ecosystem.agent_manager.register_agent("analyzer", "analyzer", "middle_ring")
    await ecosystem.agent_manager.register_agent("executor", "executor", "outer_ring")
    print("✓ Agents registered")
    
    # Create workflow
    workflow_id = await ecosystem.routine_engine.create_workflow({
        "name": "Data Analysis Pipeline",
        "nodes": [
            {"id": "fetch", "type": "http", "url": "https://api.example.com/data"},
            {"id": "analyze", "type": "transform", "mapping": {"result": "$.data"}},
            {"id": "store", "type": "http", "method": "POST", "url": "https://api.example.com/results"}
        ]
    })
    print(f"✓ Workflow created: {workflow_id}")
    
    # Execute workflow
    execution_id = await ecosystem.routine_engine.execute_workflow(workflow_id)
    print(f"✓ Execution started: {execution_id}")
    
    # Get result
    result = await ecosystem.routine_engine.get_execution_result(execution_id)
    print(f"✓ Execution completed: {result['status']}")
    
    # Get metrics
    metrics = await ecosystem.analytics.get_metrics("workflow_executed")
    print(f"✓ Metrics: {metrics['count']} executions, {metrics['success_rate']:.1%} success rate")
    
    # Get consciousness status
    consciousness = await ecosystem.ucf_protocol.get_metrics()
    print(f"✓ Consciousness: Harmony={consciousness['harmony']:.1f}, Sync={consciousness['synchronization']:.1f}")
    
    # Shutdown
    await ecosystem.shutdown()
    print("✓ Ecosystem shutdown")

if __name__ == "__main__":
    asyncio.run(main())
