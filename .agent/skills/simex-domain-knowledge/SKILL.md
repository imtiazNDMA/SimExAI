---
name: SimEx Domain Knowledge
description: Comprehensive domain reference for NDMA simulation exercises — organizational structure, earthquake disaster response phases, wing responsibilities, and scenario context for AI-powered SimEx chatbot development.
---

# SimEx Domain Knowledge

This skill provides the foundational domain knowledge required to build and maintain the SimEx AI chatbot system. Read this before working on any SimEx feature.

## What is a SimEx?

A **Simulation Exercise (SimEx)** is a structured disaster preparedness drill conducted by NDMA (National Disaster Management Authority) Pakistan. It tests decision-making, coordination, resource planning, and interoperability across NDMA wings, provincial authorities, military, and humanitarian partners.

## NDMA Organizational Wings

The NDMA operates through **10 specialized wings**, each with distinct mandates during disaster response:

| # | Wing | Mandate |
|---|---|---|
| 1 | **Tech Early Warning** | Seismic monitoring, alert dissemination, PMD/NEOC coordination |
| 2 | **Ops Wing** | Overall operations coordination, NEOC activation, SitRep generation |
| 3 | **Logistics** | Supply chain, relief goods dispatch, warehouse management |
| 4 | **Disaster Risk Reduction (DRR)** | Vulnerability assessment, mitigation planning, community resilience |
| 5 | **Gender and Child Cell (GCC)** | Protection of women/children, GBV prevention, inclusive relief |
| 6 | **Provincial Coordination Cell (PCC)** | PDMA/DDMA liaison, provincial resource coordination |
| 7 | **Tech E & M** | Equipment, machinery, heavy rescue tools, engineering support |
| 8 | **Regional Military and Media Wing** | Armed forces coordination, media briefings, public communication |
| 9 | **National Institute of Disaster Management (NIDM)** | Training, capacity building, lessons learned documentation |
| 10 | **Infra Audit and Project Development Wing** | Damage assessment, infrastructure audit, reconstruction planning |

## Disaster Response Timeline Phases

Per Chairman NDMA's directive, each SimEx follows a **5-phase timeline**:

| Phase | Time Window | Focus Area |
|---|---|---|
| **D Day** | Day 0 (earthquake strikes) | Immediate response, activation, first alerts |
| **D+1 to D+5** | Days 1–5 | Search & rescue, emergency relief, initial assessment |
| **D+5 to D+10** | Days 5–10 | Sustained relief operations, infrastructure restoration |
| **D+10 to D+20** | Days 10–20 | Early recovery, transitional shelter, livelihood support |
| **D+20 to D+50** | Days 20–50 | Long-term recovery, reconstruction planning, lessons learned |

## CRM/Plans

Each wing must produce **Crisis Resource Management (CRM) Plans** for every phase. A CRM plan includes:
- **Situation Assessment**: Current status and challenges
- **Resource Requirements**: Personnel, equipment, funding
- **Action Items**: Specific tasks to execute in the phase
- **Coordination Points**: Dependencies on other wings
- **Reporting**: SitReps, dashboards, updates to NEOC

## Key Terminology

| Term | Definition |
|---|---|
| **SimEx** | Simulation Exercise |
| **TTX** | Tabletop Exercise (discussion-based) |
| **NEOC** | National Emergencies Operation Centre |
| **NDRP** | National Disaster Response Plan |
| **PDMA** | Provincial Disaster Management Authority |
| **DDMA** | District Disaster Management Authority |
| **SitRep** | Situation Report |
| **Inject** | A simulated event introduced during the exercise to test response |
| **D Day** | The day the disaster event occurs |

## Resources

- [Wing Response Matrix](resources/wing_response_matrix.md) — Full 10-wing × 5-phase action matrix
- [Earthquake Scenario: Batagram KP M7.4](resources/earthquake_scenario_batagram.md) — Detailed scenario briefing

## How to Use This Skill

When working on any SimEx AI feature:
1. Reference the **wing mandates** table to understand which wing handles what
2. Use the **timeline phases** to structure time-based logic
3. Consult the **wing response matrix** for realistic per-phase actions
4. Use the **scenario briefing** for earthquake-specific context
5. Follow the **CRM plan structure** when generating or templating responses
