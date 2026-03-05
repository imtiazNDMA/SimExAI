"""Pydantic models for the SimEx AI system."""
from pydantic import BaseModel
from typing import Optional


class ChatRequest(BaseModel):
    wing_id: str
    phase_id: str
    message: str


class ChatResponse(BaseModel):
    wing_id: str
    wing_name: str
    phase_id: str
    phase_label: str
    response: str
    timestamp: str


class PhaseInfo(BaseModel):
    id: str
    label: str
    days: str
    is_active: bool = False
    is_completed: bool = False


class WingInfo(BaseModel):
    id: str
    name: str
    icon: str


class ScenarioInfo(BaseModel):
    id: str
    name: str
    type: str
    magnitude: float
    location: dict
    impact: dict
    current_phase: str


class InjectEvent(BaseModel):
    id: str
    phase_id: str
    time_offset: str
    title: str
    description: str
    severity: str
    target_wings: list[str]
    response_required: bool = False
