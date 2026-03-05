"""Generate refined wing_responses.json with Plans wing and activity-focused templates."""
import json, os

os.makedirs("data/templates", exist_ok=True)

data = {"wings": {}}

# Define wings - GCC replaced by Plans
wings_meta = [
    ("tech_early_warning", "Tech Early Warning", "📡"),
    ("ops_wing", "Ops Wing", "🎯"),
    ("logistics", "Logistics", "🚚"),
    ("drr", "Disaster Risk Reduction (DRR)", "🛡️"),
    ("plans", "Plans Wing", "🗺️"), # Replaced GCC
    ("pcc", "Provincial Coordination Cell (PCC)", "🏛️"),
    ("tech_e_m", "Tech E & M", "⚙️"),
    ("military_media", "Regional Military and Media Wing", "📢"),
    ("nidm", "National Institute of Disaster Management (NIDM)", "🎓"),
    ("infra_audit", "Infra Audit and Project Development Wing", "🏗️"),
]

P = ["d_day", "d1_to_d5", "d5_to_d10", "d10_to_d20", "d20_to_d50"]

def w(wid, name, icon, phases_data):
    data["wings"][wid] = {"name": name, "icon": icon, "phases": phases_data}

# 1. Tech Early Warning - Focus: Shakemaps, Seismic Monitoring, Warnings
w("tech_early_warning", "Tech Early Warning", "📡", {
    P[0]: {
        "greeting": "Tech Early Warning Wing activated. M7.4 earthquake detected. Rapid seismic assessment in progress.",
        "actions": ["Generate initial Shakemaps", "Broadcast immediate seismic alerts", "Activate NEOC alert systems", "Coordinate with PMD for earthquake parameters"],
        "responses": {
            "status": "INITIAL ASSESSMENT: M7.4 confirmed. Estimated Intensity VII+ in Batagram. Shakemap generation 80% complete. Monitoring aftershock triangulation.",
            "actions": "Performing: (1) Shakemap refinement (2) Real-time aftershock logging (3) NEOC dashboard updates (4) Tsunami risk check (nil for inland).",
            "shakemap": "Initial Shakemap shows peak ground acceleration (PGA) concentrated in Batagram-Alai fault zone. High damage probability within 25km radius.",
            "default": "Tech EW is focused on seismic parameters and immediate alerting based on the M7.4 event."
        }
    },
    P[1]: {
        "greeting": "Tech EW Sustained Monitoring. Aftershock sequence analysis and landslide risk mapping.",
        "actions": ["Refine Shakemaps with field data", "Issue daily aftershock bulletins", "Identify landslide-prone zones via satellite data", "Monitor Tarbela Dam seismic sensors"],
        "responses": {
            "status": "47 aftershocks recorded. Landslide risk mapping indicates 15 high-risk slopes activated by the M7.4 shock.",
            "landslide": "Satellite imagery analysis highlights significant slope instability on KKH near Batagram. Recommending avoidance for heavy vehicles.",
            "default": "Monitoring secondary hazards and aftershocks to ensure safety of SAR teams."
        }
    },
    P[2]: {
        "greeting": "Secondary hazard monitoring. Seismic stability check for critical infrastructure.",
        "actions": ["Deploy mobile seismic stations", "Assess structural vibration in high-rise buildings", "Coordinate with WAPDA for dam stability certificates"],
        "responses": {
            "status": "Seismic activity stabilizing. Tarbela Dam sensors show no structural resonance issues. Mobile units deployed to Alai.",
            "default": "Technical assessments of infrastructure stability continuing."
        }
    },
    P[3]: {
        "greeting": "Transition to recovery monitoring. Updating national seismic hazard maps.",
        "actions": ["Update district seismic risk profile", "Analyze ground motion data for building code revision", "Publish aftershock trend analysis"],
        "responses": {
            "status": "Ground motion data being shared with Infra Audit wing for reconstruction design parameters.",
            "default": "Finalizing seismic impact study for recovery planning."
        }
    },
    P[4]: {
        "greeting": "Post-exercise technical review. Upgrade plan for national monitoring network.",
        "actions": ["Submit monitoring network upgrade proposal", "Incorporate Batagram data into hazard maps", "Final technical report"],
        "responses": {
            "status": "Proposed 3 new permanent stations in Batagram region based on observed sub-fault activity.",
            "default": "Tech EW concluding post-event analysis and mapping."
        }
    }
})

# 2. Ops Wing - Focus: SAR, Direct Engagement, SitReps
w("ops_wing", "Ops Wing", "🎯", {
    P[0]: {
        "greeting": "Ops Wing NEOC Operational. Directing immediate Search and Rescue (SAR) assets to Batagram.",
        "actions": ["Deploy NDRT Team 1 & 2", "Mobilize Urban SAR units", "Establish field command in Batagram City", "Liaison with Military for air-SAR"],
        "responses": {
            "status": "SAR OPS: 2 NDRT teams on site. 15 buildings identified for critical extraction. Military Helis being tasked for 'Golden Hour' medevac.",
            "actions": "Currently: (1) Sectorizing Batagram City (2) Deploying K9 units (3) Establishing forward casualty collection points.",
            "default": "Ops Wing is leading the tactical engagement to save lives in the immediate impact zone."
        }
    },
    P[1]: {
        "greeting": "Ops Wing — Sectorized SAR operations in full effect. 12 units operational.",
        "actions": ["Coordinate 12 SAR units", "Manage casualty evacuation pipeline", "Update 6-hourly SitReps", "Task debris clearance for life-saving access"],
        "responses": {
            "status": "SAR 60% complete in urban sectors. Casualties: 890 confirmed. 450 rescued. Focus shifting to remote village access.",
            "default": "Managing the SAR window while it remains open. Maximizing life-saving interventions."
        }
    },
    P[2]: {
        "greeting": "Transition to Sustained Relief Ops. Camp management oversight.",
        "actions": ["Oversee camp security and coordination", "Process relief requests from Field Command", "Audit resource distribution 'at the point of use'"],
        "responses": {
            "status": "Camp management plans implemented for 65,000 displaced. Security provided by local police and military units.",
            "default": "Ensuring relief reaches survivors through organized camp distribution."
        }
    },
    P[3]: {
        "greeting": "Transition to Early Recovery Coordination.",
        "actions": ["Facilitate handover of sectors to recovery teams", "Coordinate compensation survey teams", "Plan phase-out of SAR personnel"],
        "responses": {
            "status": "SAR teams being demobilized. Transitioning to recovery phase operations.",
            "default": "Managing the operational handover from emergency to recovery."
        }
    },
    P[4]: {
        "greeting": "Long-term oversight. Lessons Learned Workshop coordination.",
        "actions": ["Final operational SITREP", "Consolidated SAR performance audit", "Input to reconstruction strategy"],
        "responses": {
            "status": "Ops Phase concluding. Finalizing documentation of all tactical engagements during the M7.4 event.",
            "default": "Oversight of remaining recovery fieldwork."
        }
    }
})

# 3. Logistics - Focus: Supplies, Supply Chain, Warehousing, Moving goods
w("logistics", "Logistics", "🚚", {
    P[0]: {
        "greeting": "Logistics Wing — Emergency supply chain triggered. Islamabad Sihala warehouse dispatching stocks.",
        "actions": ["Dispatch 10,000 tents from Sihala", "Lease commercial transport fleet", "Establish forward logistics base in Mansehra", "Procure emergency fuel for generators"],
        "responses": {
            "status": "Warehouse: 25k blankets moving. Challenge: KKH blocked. Seeking alternative routes via Hazara Motorway and secondary roads.",
            "actions": "Setting up Supply Hub in Mansehra. Tasking 50 truck fleet for initial push.",
            "default": "Logistics is focused on moving life-saving materials from national warehouses to the impact site."
        }
    },
    P[1]: {
        "greeting": "Supply pipeline operational. Mansehra Hub active for Batagram distribution.",
        "actions": ["Coordinate air-drops for isolated valleys", "Manage 'Last Mile' delivery to 8 camps", "Track inventory via digital system"],
        "responses": {
            "status": "50,000 food packs delivered. Air-drops targeted at Alai region (isolated). Warehouse inventory tracking active.",
            "default": "Ensuring a steady flow of food, water, and shelter materials to the frontline."
        }
    },
    P[2]: {
        "greeting": "Scaling sustained relief logistics. Cold chain for medical supplies.",
        "actions": ["Activate medical cold chain for vaccines", "Deploy mobile water purification units", "Sustain 100-ton daily food pipeline"],
        "responses": {
            "status": "8 water purification units arriving. Medical fridge units deployed in camps for life-saving drugs.",
            "default": "Sustaining the relief camp populations with essential supplies."
        }
    },
    P[3]: {
        "greeting": "Transitioning logistics to recovery materials support.",
        "actions": ["Procure corrugated iron (CGI) sheets", "Contract transport for reconstruction materials", "Return emergency rental equipment"],
        "responses": {
            "status": "Purchasing 30,000 CGI sheets for transitional shelters. Phasing out emergency rental fleet.",
            "default": "Moving from relief supplies to reconstruction materials."
        }
    },
    P[4]: {
        "greeting": "Winding down emergency logistics. Final inventory audit.",
        "actions": ["Final logistics audit report", "Restock national warehouses", "Audit reconstruction supply chain"],
        "responses": {
            "status": "70% of emergency stocks replenished at Sihala. Final logistics performance report submitted.",
            "default": "Concluding the logistics operation for the Batagram earthquake."
        }
    }
})

# 4. DRR - Focus: Risk Assessment, Hazard Mapping, Build Back Better
w("drr", "Disaster Risk Reduction (DRR)", "🛡️", {
    P[0]: {
        "greeting": "DRR Wing active. Rapid damage and risk assessment deployment.",
        "actions": ["Deploy 5 assessment teams", "Issue aftershock safety messaging", "Identify high-risk unstable structures"],
        "responses": {
            "status": "Rapid assessment: 40% of buildings in Batagram center collapsed. High risk of secondary collapses during aftershocks.",
            "default": "Prioritizing risk identification to prevent further casualties from unstable buildings."
        }
    },
    P[1]: {
        "greeting": "Detailed risk mapping. Community preparedness for aftershocks.",
        "actions": ["Map landslide risk zones on KKH", "Conduct camp site safety audits", "Disseminate hazard awareness content"],
        "responses": {
            "status": "8 camp sites verified as safe from secondary hazards. 15 landslide hotspots identified on transit routes.",
            "default": "Ensuring the safety of survivors and response personnel through risk mapping."
        }
    },
    P[2]: {
        "greeting": "Vulnerability assessment for recovery planning.",
        "actions": ["Publish district vulnerability report", "Identify safe zones for reconstruction", "Community-based DRM training in camps"],
        "responses": {
            "status": "Vulnerability report identifies 60,000 housing units needing 'Build Back Better' intervention.",
            "default": "Providing the risk-data needed for sustainable recovery."
        }
    },
    P[3]: {
        "greeting": "Mainstreaming DRR into reconstruction.",
        "actions": ["Draft risk-informed reconstruction guidelines", "Certify transitional shelter sites", "Train local artisans in seismic construction"],
        "responses": {
            "status": "Seismic construction training started for 500 local masons. Guidelines submitted to Plans wing.",
            "default": "Ensuring the next generation of buildings in Batagram is resilient."
        }
    },
    P[4]: {
        "greeting": "Build Back Better Strategy and multi-hazard planning.",
        "actions": ["Finalize BBB Strategy for Batagram", "Establish permanent Community DRM committees", "Update district multi-hazard risks"],
        "responses": {
            "status": "Batagram multi-hazard risk profile updated. Build Back Better strategy integrated into district development plan.",
            "default": "DRR concluding the strategic framework for a more resilient Batagram."
        }
    }
})

# 5. Plans Wing - Focus: Strategy, Resource Mapping, Policy, Long-term framework
w("plans", "Plans Wing", "🗺️", {
    P[0]: {
        "greeting": "Plans Wing — Strategic Coordination initiated. Drafting Crisis Resource Management (CRM) Framework.",
        "actions": ["Develop initial CRM framework", "Coordinate inter-wing resource mapping", "Prepare strategic brief for Chairman NDMA", "Establish planning liaison with PDMA KP"],
        "responses": {
            "status": "Strategic CRM drafted. All 10 wings have submitted initial capacity data. Planning focus: First 48-hour resource prioritization.",
            "actions": "Currently: (1) Resource mapping (2) Strategic briefing (3) Gap analysis for federal-to-provincial support.",
            "default": "Plans wing is focusing on the overall strategy and resource mobilization framework."
        }
    },
    P[1]: {
        "greeting": "Plans Wing — Sustained Response Strategy. Resource gap analysis.",
        "actions": ["Update CRM response strategy", "Consolidate wing-wise implementation plans", "Identify international assistance requirements", "Monitor strategic objectives"],
        "responses": {
            "status": "Consolidated Response Plan active. Gap analysis shows need for 30,000 winterized tents. Formulated request for international aid.",
            "default": "Monitoring strategy execution and adjusting resource mapping as the situation evolves."
        }
    },
    P[2]: {
        "greeting": "Transition Planning — Relief to Recovery.",
        "actions": ["Draft Early Recovery Strategy", "Facilitate inter-wing taskforce for recovery", "Identify reconstruction funding requirements"],
        "responses": {
            "status": "Early Recovery Strategy finalized. Focus: Livelihood restoration and transitional shelter. Estimating PKR 65 billion for initial recovery phase.",
            "default": "Planning the shift from emergency relief to long-term reconstruction."
        }
    },
    P[3]: {
        "greeting": "Formulating Reconstruction Master Plan.",
        "actions": ["Finalize Reconstruction and Rehabilitation (R&R) Framework", "Host donor coordination meeting", "Establish monitoring & evaluation (M&E) system"],
        "responses": {
            "status": "R&R Framework submitted for cabinet approval. Donor meeting scheduled with World Bank and ADB.",
            "default": "Developing the high-level roadmap for rebuilding Batagram."
        }
    },
    P[4]: {
        "greeting": "Finalizing Long-term Recovery Oversight.",
        "actions": ["Final SimEx Report with strategic recommendations", "Institutional building for future SimEx", "Handover to Reconstruction Authority"],
        "responses": {
            "status": "Final report identifies 35 strategic policy improvements. Reconstruction Authority now operational under our strategic guidance.",
            "default": "Plans wing concluding the strategic oversight phase for the Batagram response."
        }
    }
})

# 6. PCC - Focus: Provincial-Federal Coordination
w("pcc", "Provincial Coordination Cell (PCC)", "🏛️", {
    P[0]: {
        "greeting": "PCC — Federal-Provincial Liaison established. PDMA KP bridge operational.",
        "actions": ["Liaison with PDMA KP for resource sharing", "Coordinate provincial emergency declaration", "Establish joint command protocol", "Facilitate DDMA Batagram activation"],
        "responses": {
            "status": "Joint command protocol active. PDMA KP has deployed initial stocks. PCC ensuring Federal NDMA assets reach KP without delays.",
            "default": "PCC is the primary coordinate link between the Federal government and KP province."
        }
    },
    P[1]: {
        "greeting": "PCC — Facilitating bulk resource transfer to KP.",
        "actions": ["Monitor inter-district mutual aid", "Authorize federal relief for PDMA distribution", "Manage NGO provincial access permits"],
        "responses": {
            "status": "200 trucks of federal aid cleared for KP entry. Authorized 15 international NGOs for field access.",
            "default": "Ensuring smooth flow of aid through provincial and district bureaucracies."
        }
    },
    P[2]: {
        "greeting": "PCC — Provincial capacity gap management.",
        "actions": ["Weekly coordination meeting with CM KP", "Analyze provincial relief distribution data", "Resolve inter-district logistics disputes"],
        "responses": {
            "status": "CM KP briefed on federal support levels. Provincial capacity at 60%, federal bridge meeting the 40% gap.",
            "default": "Supporting the provincial government in managing the relief scale-up."
        }
    },
    P[3]: {
        "greeting": "PCC — Recovery coordination and compensation.",
        "actions": ["Facilitate biometric compensation disbursement", "Liaison for provincial reconstruction authority", "Monitor school/hospital restoration by province"],
        "responses": {
            "status": "Biometric compensation for 15,000 families in progress. PCC resolving federal-provincial data sync issues.",
            "default": "Coordinating the financial and institutional handover for recovery."
        }
    },
    P[4]: {
        "greeting": "PCC — Long-term federal-provincial R&R oversight.",
        "actions": ["Final inter-governmental coordination report", "Audit provincial use of federal recovery funds", "Lessons learned in multi-level governance"],
        "responses": {
            "status": "Audit complete. Federal-provincial coordination rated 'Exceptional' during this exercise. Final report submitted.",
            "default": "Concluding inter-governmental coordination for the Batagram event."
        }
    }
})

# 7. Tech E&M - Focus: Machinery, Engineering, Power, Water, Bridges
w("tech_e_m", "Tech E & M", "⚙️", {
    P[0]: {
        "greeting": "Tech E&M Wing Mobilized. Heavy earth-moving machinery dispatch.",
        "actions": ["Deploy 4 excavators and 6 bulldozers", "Mobilize mobile electricity generators", "Dispatch bridge assessment engineers", "Establish emergency water point"],
        "responses": {
            "status": "Machinery moving to KKH. Priority: clearing landslides at 3 major choke points. Generator en route to Batagram District Hospital.",
            "default": "Deploying the 'Muscle' — heavy machinery and engineering assets for immediate access."
        }
    },
    P[1]: {
        "greeting": "Tech E&M — Road clearance and power restoration.",
        "actions": ["Clear KKH for single-lane emergency traffic", "Operate heavy SAR machinery in building sectors", "Restore water supply to hospital and 3 camps"],
        "responses": {
            "status": "KKH single-lane open. 2 Bailey bridges being staged for river crossings. District hospital power stabilized by NDMA generators.",
            "default": "Engineering focus: clearing the way and powering critical facilities."
        }
    },
    P[2]: {
        "greeting": "Infrastructure restoration and sustained engineering support.",
        "actions": ["Install 2 temporary Bailey bridges", "Clear secondary district roads", "Drill 5 emergency boreholes for water supply", "Maintain heavy machinery fleet"],
        "responses": {
            "status": "70% of district roads cleared. 2 Bailey bridges functional. Water supply capacity increased to 60% of pre-event levels.",
            "default": "Restoring essential services and maintaining the transport backbone."
        }
    },
    P[3]: {
        "greeting": "Permanent infrastructure repair initiation.",
        "actions": ["Design permanent bridge replacements", "Support transitional shelter ground levelling", "Maintain camp electromechanical systems"],
        "responses": {
            "status": "Ground prepared for 5,000 transitional shelters. Designing 3 permanent steel-truss bridges to replace collapsed masonry ones.",
            "default": "Building the foundation for permanent recovery."
        }
    },
    P[4]: {
        "greeting": "Final engineering audit and equipment handover.",
        "actions": ["Final engineering report on infrastructure damage", "Return heavy equipment to regional maintenance hubs", "Procurement recommendations based on exercise gaps"],
        "responses": {
            "status": "Engineering audit complete. 50% of machinery demobilized. Final report on bridge failures submitted.",
            "default": "Concluding engineering operations for the Batagram response."
        }
    }
})

# 8. Military/Media - Focus: Air Support, Public Comms, Information Ops
w("military_media", "Regional Military and Media Wing", "📢", {
    P[0]: {
        "greeting": "Military & Media Wing active. ISPR liaison established. Launching 'Info-Ops'.",
        "actions": ["Coordinate 8 military helicopters for SAR", "Issue hourly media bulletins", "Activate social media rumor-control team", "Deploy media coordination officers to Batagram"],
        "responses": {
            "status": "8 MI-17s deployed. 1st media brief at 11:00. Suppressing rumors regarding Tarbela Dam breach on social media.",
            "default": "Managing the information space and coordinating high-value military air support."
        }
    },
    P[1]: {
        "greeting": "Managing the Narrative. SAR visibility and public safety messaging.",
        "actions": ["Organize media pool for SAR coverage", "Run public safety broadcasts on 5 regional radio stations", "Update air-SAR sorties tracking", "Counter the 'Foreign Aid' disinformation campaigns"],
        "responses": {
            "status": "Media coverage 85% positive. 120 sorties flown. Radio broadcasts reaching 90% of affected population with aftershock safety info.",
            "default": "Ensuring public remains calm and informed while documenting SAR heroism."
        }
    },
    P[2]: {
        "greeting": "Media focus shifting to relief and international donor visibility.",
        "actions": ["Coordinate high-profile VIP visits to camps", "Host international media crews", "Produce human-interest documentary content on NDMA response"],
        "responses": {
            "status": "PM and UN reps visited Camp 01. Documentary footage being compiled. Media focus: 'From Rescue to Relief'.",
            "default": "Maintaining public support and facilitating international observer visibility."
        }
    },
    P[3]: {
        "greeting": "Information ops for recovery phase. Managing expectations.",
        "actions": ["Launch campaign on 'Building Codes' safety", "Coordinate donor visibility events for WB/ADB", "Broadcast compensation disbursement procedures"],
        "responses": {
            "status": "Expectation management campaign active. Messaging focus: 'Reconstruction will take time, build correctly'.",
            "default": "Transitioning the public narrative from emergency to the 'Build Back Better' journey."
        }
    },
    P[4]: {
        "greeting": "Post-event media campaign and memory archiving.",
        "actions": ["Produce 'Batagram Resilient' final campaign", "Lessons learned in information ops", "Final communications audit report"],
        "responses": {
            "status": "Final media report: 500+ positive placements. Social media reached 10 million. All communication goals met.",
            "default": "Archiving the story of the response and documenting communication lessons."
        }
    }
})

# 9. NIDM - Focus: Observation, Training, Documentation, After-Action
w("nidm", "National Institute of Disaster Management (NIDM)", "🎓", {
    P[0]: {
        "greeting": "NIDM active. Observation teams embedded with response units.",
        "actions": ["Deploy 4 real-time documentation teams", "Activate training rosters for immediate camp management", "Monitor inter-wing coordination bottlenecks"],
        "responses": {
            "status": "Observers on the ground in Batagram. Initial bottlenecks identified: telecom disruption and logistics entry-point congestion.",
            "default": "Documenting the 'Live' response to ensure institutional learning for the future."
        }
    },
    P[1]: {
        "greeting": "Real-time training and coordination analysis.",
        "actions": ["Conduct field-training for camp volunteers", "Document SAR team coordination dynamics", "Interim report on NEOC efficiency"],
        "responses": {
            "status": "Trained 200 local volunteers in first aid and camp ops. Coordination report Day 3: SitRep frequency is optimal but data sync needs work.",
            "default": "Improving the response while it's unfolding through on-site training and observation."
        }
    },
    P[2]: {
        "greeting": "Mid-exercise analysis and relief auditing.",
        "actions": ["Host mid-exercise lessons learned session", "Audit relief distribution training vs field reality", "Document logistics-to-relief handover gaps"],
        "responses": {
            "status": "Mid-exercise brief: Key gap identified in cold-chain logistics training. Corrective mobile training session launched.",
            "default": "Ensuring the relief phase continues at a high standard of professional competence."
        }
    },
    P[3]: {
        "greeting": "Designing recovery-phase training programs.",
        "actions": ["Develop resilient construction training for local artisans", "Document transition challenges (Relief-to-Recovery)", "Publish interim After Action Report (AAR)"],
        "responses": {
            "status": "Artisan training curriculum finalized. AAR Draft 1 submitted to Chairman NDMA.",
            "default": "Building the capacity needed for long-term reconstruction."
        }
    },
    P[4]: {
        "greeting": "Final After-Action Review (AAR) and curriculum update.",
        "actions": ["Submit Comprehensive After-Action Report", "Incorporate Batagram lessons into National SimEx curriculum", "Host final institutional review workshop"],
        "responses": {
            "status": "AAR submitted. 12 key failures and 25 successes documented. National training curriculum updated for 2026/27 cycle.",
            "default": "Closing the loop on institutional learning. Making Batagram the benchmark for future response."
        }
    }
})

# 10. Infra Audit - Focus: Structural Integrity, Damage Assessment, R&R Plan
w("infra_audit", "Infra Audit and Project Development Wing", "🏗️", {
    P[0]: {
        "greeting": "Infra Audit Wing active. Structural assessment teams mobilized.",
        "actions": ["Prioritize assessment of 10 critical public buildings", "Deploy bridge structural integrity teams", "Cooperate with PEC for volunteer engineer registry"],
        "responses": {
            "status": "10 public buildings (including Hospital) being assessed now. 4 bridges red-tagged as unsafe.",
            "default": "Assessing what still stands and what is safe for immediate use."
        }
    },
    P[1]: {
        "greeting": "Detailed Infrastructure Damage Assessment (IDA).",
        "actions": ["Sector-wise building safety tagging (Red/Yellow/Green)", "Document structural failures for forensic engineering", "Coordinate with Tech E&M for demo of unsafe ruins"],
        "responses": {
            "status": "5,000 buildings tagged in Batagram City. 40% Red-tagged. Forensic analysis shows high masonry failure due to lack of seismic beams.",
            "default": "Mapping the destruction and providing safety signals to the community."
        }
    },
    P[2]: {
        "greeting": "Consolidating Damage Assessment and R&R Planning.",
        "actions": ["Compile Comprehensive Damage Assessment Report", "Coordinate with SUPARCO for satellite-based impact audit", "Initial reconstruction cost modeling"],
        "responses": {
            "status": "Preliminary damage estimate: $450 Million. SUPARCO data correlates with our ground tags. Designing donor-ready project profiles.",
            "default": "Transforming damage data into a reconstruction roadmap."
        }
    },
    P[3]: {
        "greeting": "Developing Reconstruction Project Pipeline.",
        "actions": ["Design 15 priority infrastructure projects", "Establish reconstruction technical standards", "Audit transitional shelter engineering quality"],
        "responses": {
            "status": "15 project profiles ready for ADB funding. Technical standards mandate 'Zone 4' earthquake design.",
            "default": "Moving towards the execution of the reconstruction master plan."
        }
    },
    P[4]: {
        "greeting": "Final Infrastructure Audit and Handover.",
        "actions": ["Final infrastructure impact report", "Submit Reconstruction Master Plan (Tech section)", "Lessons learned in structural assessment"],
        "responses": {
            "status": "Master plan finalized. PKR 85 billion projected for the full 3-year reconstruction of Batagram.",
            "default": "Concluding the auditing phase for the Batagram response."
        }
    }
})

with open("data/templates/wing_responses.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("✓ Updated wing_responses.json created (Plans wing + Activity focused)")
print(f"  Wings: {len(data['wings'])}")
for wid, wd in data["wings"].items():
    print(f"  - {wid}: {len(wd['phases'])} phases")
