# MedSafe Optimization Framework - Quick Start Guide

**Version:** 1.0.0
**Last Updated:** 2025-11-28

---

## 🚀 Quick Start (5 Minutes)

### Step 1: Import the Optimizer

```python
# In your agent file (e.g., backend/app/langgraph_agents/clinical_agent.py)
from backend.app.optimization import get_optimizer

optimizer = get_optimizer()
```

### Step 2: Add Execution Tracking

```python
# Wrap your agent's process function
@optimizer.track_execution("clinical_agent")
async def process(state: MedSafeState) -> Dict[str, Any]:
    """Your agent logic here"""
    # ... existing code
    return updates
```

### Step 3: Add Response Caching (Optional)

```python
# For expensive operations that can be cached
@optimizer.cache_response(ttl=1800)  # 30 minutes
async def find_drug_interactions(drug_name: str):
    # ... expensive database/LLM operation
    return results
```

### Step 4: View Metrics

```python
# At the end of your workflow
optimizer.print_report()
```

That's it! Your agent is now optimized with performance tracking.

---

## 📊 Viewing Real-Time Metrics

### Option 1: Console Output

```python
from backend.app.optimization import get_optimizer
from backend.app.optimization.monitoring import get_performance_monitor

# Get metrics
optimizer = get_optimizer()
monitor = get_performance_monitor()

# Print reports
optimizer.print_report()
monitor.print_dashboard()
```

### Option 2: API Endpoint (Recommended)

Add to your FastAPI routes:

```python
# In backend/app/routers/monitoring.py (create this file)
from fastapi import APIRouter
from backend.app.optimization import get_optimizer
from backend.app.optimization.monitoring import (
    get_performance_monitor,
    get_cost_tracker
)

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])

@router.get("/metrics")
async def get_metrics():
    """Get all optimization metrics"""
    return {
        'optimizer': get_optimizer().get_metrics(),
        'performance': get_performance_monitor().get_metrics(),
        'costs': get_cost_tracker().get_cost_report(),
    }

@router.get("/dashboard")
async def get_dashboard():
    """Get monitoring dashboard data"""
    monitor = get_performance_monitor()
    monitor.print_dashboard()  # Console output
    return monitor.get_metrics()
```

Then register in `main.py`:

```python
from backend.app.routers.monitoring import router as monitoring_router
app.include_router(monitoring_router)
```

Access at: `http://localhost:9001/api/v1/monitoring/metrics`

---

## 🎯 Common Use Cases

### Use Case 1: Track Agent Performance

```python
# Before
async def process(state):
    # Do work
    return result

# After
@optimizer.track_execution("my_agent")
async def process(state):
    # Do work
    return result
```

### Use Case 2: Cache Expensive Operations

```python
# Before
def get_drug_interactions(drug_name: str):
    # Expensive database query
    return db.query(...).all()

# After
@optimizer.cache_response(ttl=3600)  # Cache for 1 hour
def get_drug_interactions(drug_name: str):
    # Expensive database query
    return db.query(...).all()
```

### Use Case 3: Parallel Execution

```python
# Before (Sequential)
result1 = await agent1.process(state)
result2 = await agent2.process(state)
result3 = await agent3.process(state)

# After (Parallel)
results = await optimizer.parallel_execute([
    agent1.process(state),
    agent2.process(state),
    agent3.process(state),
])
result1, result2, result3 = results
```

### Use Case 4: Database Query Profiling

```python
from backend.app.optimization.db_optimizer import get_db_optimizer

db_optimizer = get_db_optimizer()

# Profile a specific query
@db_optimizer.track_query("find_interactions")
def get_interactions(db, drug_name):
    return db.query(Interaction).filter(...).all()

# View query statistics
db_optimizer.print_query_report()
```

### Use Case 5: Monitor Request Performance

```python
from backend.app.optimization.monitoring import get_performance_monitor

monitor = get_performance_monitor()

@app.post("/api/analyze")
async def analyze(data):
    start_time = time.time()

    try:
        result = await process_analysis(data)
        elapsed = time.time() - start_time
        monitor.record_request(elapsed, error=False)
        return result

    except Exception as e:
        elapsed = time.time() - start_time
        monitor.record_request(elapsed, error=True)
        raise
```

---

## 📈 Understanding Metrics

### Execution Metrics

```python
{
    'total_execution_time': 4.23,  # Total time in seconds
    'avg_agent_time': 0.85,        # Average per agent
    'agent_execution_times': {
        'triage_agent': 0.45,
        'clinical_agent': 1.82,
        'document_agent': 1.96
    }
}
```

### Cache Metrics

```python
{
    'cache_hit_rate': '65.00%',    # Percentage of cache hits
    'cache_hits': 130,              # Number of hits
    'cache_misses': 70,             # Number of misses
}
```

**Good cache hit rate:** > 50%
**Excellent cache hit rate:** > 70%

### Database Metrics

```python
{
    'db_queries_count': 15,         # Total queries executed
    'db_total_time': 0.234,         # Total DB time in seconds
}
```

**Avg query time:** `db_total_time / db_queries_count`

### Cost Metrics

```python
{
    'total_cost': 0.00,             # Total $ spent
    'total_tokens_used': 15234,     # Total tokens
    'tokens_by_agent': {
        'clinical_agent': 8520,
        'reflection_agent': 6714
    }
}
```

---

## 🔍 Troubleshooting

### Issue: Metrics not showing up

**Solution:**
```python
# Make sure you're getting the singleton instance
from backend.app.optimization import get_optimizer
optimizer = get_optimizer()

# Not this:
# optimizer = AgentOptimizer()  # Creates new instance!
```

### Issue: Cache not working

**Check:**
1. Is caching enabled? `optimizer.enabled = True`
2. Are you passing consistent arguments?
3. Is TTL appropriate? (default: 1800s)

```python
# Debug cache stats
cache_stats = optimizer.response_cache.stats()
print(cache_stats)
```

### Issue: Slow queries not detected

**Check slow query threshold:**
```python
from backend.app.optimization.db_optimizer import get_db_optimizer

db_optimizer = get_db_optimizer()
db_optimizer.slow_query_threshold = 0.5  # 500ms threshold
```

---

## 📚 Advanced Features

### Custom Cache Keys

```python
@optimizer.cache_response(cache_key="custom_key_123", ttl=3600)
async def my_function():
    # ... logic
    pass
```

### Context Manager for Query Profiling

```python
with db_optimizer.profile_query("Complex aggregation"):
    results = db.query(...).join(...).group_by(...).all()
```

### Connection Pool Monitoring

```python
from backend.app.optimization.db_optimizer import ConnectionPoolMonitor

# Check pool health
is_healthy = ConnectionPoolMonitor.check_pool_health()

# Print stats
ConnectionPoolMonitor.print_pool_stats()
```

### Bulk Database Operations

```python
from backend.app.optimization.db_optimizer import BatchOperations

# Bulk insert
records = [{'name': 'Drug A', ...}, {'name': 'Drug B', ...}]
count = BatchOperations.bulk_insert(db, Document, records)

# Chunked processing
for chunk in BatchOperations.chunked_query(db, query, chunk_size=500):
    process_chunk(chunk)
```

---

## 🎨 Best Practices

### 1. Track All Agents
```python
# ✅ Good
@optimizer.track_execution("agent_name")
async def process(state):
    ...

# ❌ Bad
async def process(state):
    # No tracking!
    ...
```

### 2. Cache Stable Operations
```python
# ✅ Good - Cache database lookups
@optimizer.cache_response(ttl=3600)
def get_drug_info(drug_name):
    return db.query(...).first()

# ❌ Bad - Don't cache user-specific data
@optimizer.cache_response()  # Don't cache this!
def get_user_session(user_id):
    return current_user_session
```

### 3. Use Appropriate TTL
```python
# Frequent changes: 5-15 minutes
@optimizer.cache_response(ttl=600)

# Stable data: 1-24 hours
@optimizer.cache_response(ttl=3600)

# Static data: > 24 hours
@optimizer.cache_response(ttl=86400)
```

### 4. Monitor Regularly
```python
# Print reports after each workflow
optimizer.print_report()
monitor.print_dashboard()

# Or set up periodic reports
import schedule
schedule.every(1).hour.do(lambda: monitor.print_dashboard())
```

---

## 📊 Sample Output

### Optimizer Report

```
================================================================================
📊 PERFORMANCE OPTIMIZATION REPORT
================================================================================

⏱️  EXECUTION TIMES:
   Total: 4.23s
   Average per agent: 0.85s

   By Agent:
   - document_agent: 1.96s
   - clinical_agent: 1.82s
   - triage_agent: 0.45s

🤖 LLM USAGE:
   Total tokens: 15,234
   Total calls: 3

   By Agent:
   - clinical_agent: 8,520 tokens
   - reflection_agent: 6,714 tokens

💾 CACHING:
   Hit rate: 65.00%
   Hits: 130
   Misses: 70

🗄️  DATABASE:
   Queries: 15
   Total time: 0.23s
   Avg per query: 0.015s

⚡ COORDINATION:
   Parallel executions: 2
   Sequential executions: 4
================================================================================
```

### Monitoring Dashboard

```
================================================================================
📊 REAL-TIME PERFORMANCE DASHBOARD
================================================================================

⏰ UPTIME:
   2.34 hours

📈 REQUESTS:
   Total: 456
   Errors: 3
   Error rate: 0.66%

⏱️  RESPONSE TIMES:
   Average: 4.12s
   P50: 3.89s
   P95: 8.45s
   P99: 12.34s
   Max: 15.67s

✅ SLA COMPLIANCE:
   avg_response_time: ✅ PASS
   p95_response_time: ✅ PASS
   p99_response_time: ✅ PASS
   uptime: ✅ PASS
   confidence: ✅ PASS
================================================================================
```

---

## 🔗 Related Documentation

- [Multi-Agent Optimization Report](./MULTI_AGENT_OPTIMIZATION_REPORT.md) - Comprehensive analysis
- [MedSafe Architecture](../architecture/MEDSAFE_ARCHITECTURE_SUMMARY.md) - System overview
- [API Documentation](http://localhost:9001/docs) - FastAPI auto-generated docs

---

## 💡 Tips

1. **Start Small:** Enable tracking on one agent first, validate, then expand
2. **Monitor First:** Collect metrics for a week before optimizing
3. **Iterate:** Use metrics to guide optimization decisions
4. **Alert Smartly:** Don't create too many alerts - focus on critical issues
5. **Document:** Keep notes on what optimizations worked

---

**Questions?** Check the comprehensive report or create an issue on GitHub.

**Version:** 1.0.0
**Author:** Multi-Agent Optimization Tool
**Date:** 2025-11-28
