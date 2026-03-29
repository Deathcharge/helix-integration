# Helix Integration API Reference

Complete API documentation for the Helix Integration Meta-Package.

## Core Classes

### HelixEcosystem

Main entry point for accessing all Helix components.

```python
from helix_integration import HelixEcosystem

ecosystem = HelixEcosystem(config={
    "mode": "distributed",
    "primary_host": "localhost",
    "primary_port": 8000
})
```

#### Properties

- `routine_engine` - Routine Engine instance
- `ucf_protocol` - UCF Protocol instance
- `analytics` - Analytics Engine instance
- `agent_manager` - Agent Manager instance
- `llm_engine` - LLM Agent Engine instance

#### Methods

##### `initialize()`
Initialize the ecosystem and all components.

```python
await ecosystem.initialize()
```

##### `shutdown()`
Gracefully shutdown all components.

```python
await ecosystem.shutdown()
```

##### `get_health()`
Get health status of all components.

```python
health = await ecosystem.get_health()
# Returns: {
#   "routine_engine": "healthy",
#   "ucf_protocol": "healthy",
#   "analytics": "healthy",
#   "agent_manager": "healthy",
#   "llm_engine": "healthy"
# }
```

---

## Routine Engine API

### Methods

#### `create_workflow(definition: Dict) -> str`
Create a new workflow.

```python
workflow_id = await ecosystem.routine_engine.create_workflow({
    "name": "Data Processing",
    "description": "Process user data",
    "nodes": [...]
})
```

#### `execute_workflow(workflow_id: str, context: Dict = None) -> str`
Execute a workflow.

```python
execution_id = await ecosystem.routine_engine.execute_workflow(
    workflow_id,
    context={"user_id": "123"}
)
```

#### `get_execution_result(execution_id: str) -> Dict`
Get execution result.

```python
result = await ecosystem.routine_engine.get_execution_result(execution_id)
# Returns: {
#   "execution_id": "exec_123",
#   "status": "completed",
#   "output": {...},
#   "duration_ms": 1250
# }
```

---

## UCF Protocol API

### Methods

#### `initialize() -> None`
Initialize consciousness field.

```python
await ecosystem.ucf_protocol.initialize()
```

#### `register_agent(agent_id: str, name: str, tier: str) -> None`
Register an agent in the consciousness field.

```python
await ecosystem.ucf_protocol.register_agent(
    "agent_1",
    "Architect",
    "inner_core"
)
```

#### `get_metrics() -> Dict`
Get current consciousness metrics.

```python
metrics = await ecosystem.ucf_protocol.get_metrics()
# Returns: {
#   "harmony": 85.5,
#   "synchronization": 92.3,
#   "total_consciousness": 250.5,
#   "agent_count": 3
# }
```

#### `update_agent_consciousness(agent_id: str, level: float) -> None`
Update agent consciousness level.

```python
await ecosystem.ucf_protocol.update_agent_consciousness("agent_1", 85.0)
```

---

## Analytics Engine API

### Methods

#### `track_event(event_type: str, data: Dict) -> None`
Track an event.

```python
await ecosystem.analytics.track_event("workflow_executed", {
    "workflow_id": "wf_123",
    "duration_ms": 1250,
    "status": "success"
})
```

#### `get_metrics(event_type: str, filters: Dict = None) -> Dict`
Get metrics for an event type.

```python
metrics = await ecosystem.analytics.get_metrics(
    "workflow_executed",
    filters={"status": "success"}
)
# Returns: {
#   "count": 150,
#   "avg_duration_ms": 1200,
#   "p95_duration_ms": 2500,
#   "success_rate": 0.98
# }
```

#### `get_dashboard_data() -> Dict`
Get data for dashboard visualization.

```python
dashboard_data = await ecosystem.analytics.get_dashboard_data()
```

---

## Agent Manager API

### Methods

#### `register_agent(agent_id: str, role: str, tier: str) -> None`
Register an agent.

```python
await ecosystem.agent_manager.register_agent(
    "agent_1",
    "orchestrator",
    "inner_core"
)
```

#### `get_agent_status(agent_id: str) -> Dict`
Get agent status.

```python
status = await ecosystem.agent_manager.get_agent_status("agent_1")
# Returns: {
#   "agent_id": "agent_1",
#   "state": "active",
#   "health": 0.95,
#   "consciousness_level": 85.0
# }
```

#### `allocate_resources(agent_id: str, resources: Dict) -> None`
Allocate resources to an agent.

```python
await ecosystem.agent_manager.allocate_resources("agent_1", {
    "cpu": 2,
    "memory_gb": 4
})
```

---

## LLM Agent Engine API

### Methods

#### `execute_task(task: Dict) -> Dict`
Execute an LLM-powered task.

```python
result = await ecosystem.llm_engine.execute_task({
    "description": "Analyze user data",
    "workflow_template": "analysis_pipeline",
    "context": {"user_id": "123"}
})
```

#### `get_agent_status(agent_id: str) -> Dict`
Get LLM agent status.

```python
status = await ecosystem.llm_engine.get_agent_status("llm_agent_1")
```

---

## Error Handling

All API methods may raise exceptions:

```python
from helix_integration.exceptions import (
    HelixError,
    ComponentError,
    ExecutionError,
    ValidationError
)

try:
    result = await ecosystem.routine_engine.execute_workflow(workflow_id)
except ExecutionError as e:
    print(f"Execution failed: {e}")
except ComponentError as e:
    print(f"Component error: {e}")
except HelixError as e:
    print(f"Helix error: {e}")
```

---

## Event Types

### Workflow Events
- `workflow_created`
- `workflow_executed`
- `workflow_completed`
- `workflow_failed`

### Agent Events
- `agent_registered`
- `agent_health_check`
- `agent_consciousness_updated`
- `agent_failed`

### Consciousness Events
- `consciousness_field_initialized`
- `harmony_changed`
- `synchronization_changed`
- `emergency_protocol_activated`

### Analytics Events
- `metrics_collected`
- `dashboard_updated`
- `alert_triggered`

---

**Version:** 1.0  
**Last Updated:** 2026-01-28
