# Wanny Jarvis Brain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Jarvis "Brain" with scene-aware confirmation and habit learning.

**Architecture:** Django-based models for state management and policies, AI-driven decision flow for WeChat interaction and Mijia control.

**Tech Stack:** Python, Django, MySQL, LLM (for NLU), mijiaAPI.

---

### Task 1: Core Models in `database` App

**Files:**
- Modify: `backend/apps/database/models.py`
- Create: `backend/tests/test_brain_models.py`

- [ ] **Step 1: Write tests for Brain models**
```python
import pytest
from database.models import HomeMode, HabitPolicy, ObservationCounter

@pytest.mark.django_db
def test_home_mode_creation():
    mode = HomeMode.objects.create(name="Away", is_active=True)
    assert mode.name == "Away"
    assert mode.is_active is True

@pytest.mark.django_db
def test_habit_policy_creation():
    mode = HomeMode.objects.create(name="Away")
    policy = HabitPolicy.objects.create(
        mode=mode, 
        device_did="123456", 
        property="power", 
        value="off", 
        policy="ASK"
    )
    assert policy.policy == "ASK"
```

- [ ] **Step 2: Run tests to verify they fail**
Run: `pytest backend/tests/test_brain_models.py`
Expected: FAIL (models not defined)

- [ ] **Step 3: Define models in `database/models.py`**
```python
from django.db import models

class HomeMode(models.Model):
    name = models.CharField(max_length=50, unique=True)
    is_active = models.BooleanField(default=False)
    
    def __str__(self):
        return self.name

class HabitPolicy(models.Model):
    POLICY_CHOICES = [
        ('ASK', 'Ask everytime'),
        ('ALWAYS', 'Always allow'),
        ('NEVER', 'Never allow'),
    ]
    mode = models.ForeignKey(HomeMode, on_delete=models.CASCADE)
    device_did = models.CharField(max_length=100)
    property = models.CharField(max_length=100)
    value = models.CharField(max_length=100)
    policy = models.CharField(max_length=10, choices=POLICY_CHOICES, default='ASK')

class ObservationCounter(models.Model):
    mode = models.ForeignKey(HomeMode, on_delete=models.CASCADE)
    device_did = models.CharField(max_length=100)
    property = models.CharField(max_length=100)
    target_value = models.CharField(max_length=100)
    success_count = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)
```

- [ ] **Step 4: Run migrations and verify tests pass**
Run: `python backend/manage.py makemigrations && python backend/manage.py migrate && pytest backend/tests/test_brain_models.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/apps/database/models.py backend/tests/test_brain_models.py
git commit -m "feat(database): add HomeMode, HabitPolicy and ObservationCounter models"
```

---

### Task 2: Brain Decision Logic in `brain` App

**Files:**
- Create: `backend/apps/brain/logic.py`
- Create: `backend/tests/test_brain_logic.py`

- [ ] **Step 1: Write test for decision logic**
```python
import pytest
from database.models import HomeMode, HabitPolicy, ObservationCounter
from brain.logic import BrainDecider

@pytest.mark.django_db
def test_decider_should_ask_on_first_time():
    mode = HomeMode.objects.create(name="Away", is_active=True)
    decider = BrainDecider()
    decision = decider.decide(device_did="123", property="power", current_value="on", target_value="off")
    assert decision['action'] == 'ASK'
    assert "要帮你关掉吗" in decision['message']
```

- [ ] **Step 2: Run tests to verify they fail**
Run: `pytest backend/tests/test_brain_logic.py`
Expected: FAIL (BrainDecider not defined)

- [ ] **Step 3: Implement `BrainDecider`**
```python
from database.models import HomeMode, HabitPolicy, ObservationCounter

class BrainDecider:
    def decide(self, device_did, property, current_value, target_value):
        active_mode = HomeMode.objects.filter(is_active=True).first()
        policy_obj = HabitPolicy.objects.filter(
            mode=active_mode, device_did=device_did, property=property, value=target_value
        ).first()
        
        policy = policy_obj.policy if policy_obj else 'ASK'
        
        if policy == 'ALWAYS':
            return {'action': 'EXECUTE', 'message': None}
        
        counter, _ = ObservationCounter.objects.get_or_create(
            mode=active_mode, device_did=device_did, property=property, target_value=target_value
        )
        
        if counter.success_count >= 3:
            return {
                'action': 'ASK_WITH_PITCH',
                'message': f"Sir, I see you always turn off this {property} in {active_mode} mode. Should I do it automatically from now on?"
            }
        
        return {
            'action': 'ASK',
            'message': f"Sir, the {property} is {current_value} in {active_mode} mode. Should I turn it {target_value}?"
        }
```

- [ ] **Step 4: Run tests to verify they pass**
Run: `pytest backend/tests/test_brain_logic.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/apps/brain/logic.py backend/tests/test_brain_logic.py
git commit -m "feat(brain): implement core decision logic with habit pitching"
```

---

### Task 3: Feedback Handling and Habit Learning

**Files:**
- Modify: `backend/apps/brain/logic.py`
- Create: `backend/tests/test_brain_learning.py`

- [ ] **Step 1: Write test for feedback handling**
```python
@pytest.mark.django_db
def test_handle_allow_always():
    mode = HomeMode.objects.create(name="Away", is_active=True)
    decider = BrainDecider()
    decider.handle_feedback(device_did="123", property="power", target_value="off", feedback="ALLOW_ALWAYS")
    
    policy = HabitPolicy.objects.get(mode=mode, device_did="123", property="power")
    assert policy.policy == "ALWAYS"
```

- [ ] **Step 2: Implement feedback handling in `BrainDecider`**
```python
    def handle_feedback(self, device_did, property, target_value, feedback):
        active_mode = HomeMode.objects.filter(is_active=True).first()
        if feedback == 'ALLOW_ALWAYS':
            HabitPolicy.objects.update_or_create(
                mode=active_mode, device_did=device_did, property=property, value=target_value,
                defaults={'policy': 'ALWAYS'}
            )
            ObservationCounter.objects.filter(
                mode=active_mode, device_did=device_did, property=property, target_value=target_value
            ).delete()
        elif feedback == 'ALLOW_ONCE':
            counter, _ = ObservationCounter.objects.get_or_create(
                mode=active_mode, device_did=device_did, property=property, target_value=target_value
            )
            counter.success_count += 1
            counter.save()
        elif feedback == 'DENY':
            ObservationCounter.objects.filter(
                mode=active_mode, device_did=device_did, property=property, target_value=target_value
            ).update(success_count=0)
```

- [ ] **Step 3: Run tests and verify**
Run: `pytest backend/tests/test_brain_learning.py`
Expected: PASS

- [ ] **Step 4: Commit**
```bash
git add backend/apps/brain/logic.py backend/tests/test_brain_learning.py
git commit -m "feat(brain): add feedback handling and policy update logic"
```

---

### Task 4: Integration with Monitor Service (Mocked Mijia)

**Files:**
- Create: `backend/apps/brain/service.py`
- Create: `backend/tests/test_integration.py`

- [ ] **Step 1: Create a monitor service that ties it all together**
```python
from brain.logic import BrainDecider
# Assuming a mock for Mijia or using the existing provider

class MonitorService:
    def __init__(self, api_client):
        self.api = api_client
        self.decider = BrainDecider()

    def run_check(self):
        devices = self.api.get_devices_list()
        for device in devices:
            # Simple logic for lights as example
            if 'light' in device['model'] and device['status'] == 'on':
                decision = self.decider.decide(device['did'], 'power', 'on', 'off')
                if decision['action'] == 'EXECUTE':
                    self.api.control_device(device['did'], 'power', 'off')
                elif 'ASK' in decision['action']:
                    # Trigger WeChat notification (to be implemented in comms)
                    print(f"NOTIFY WECHAT: {decision['message']}")
```

- [ ] **Step 2: Commit**
```bash
git add backend/apps/brain/service.py
git commit -m "feat(brain): add MonitorService skeleton for integration"
```
